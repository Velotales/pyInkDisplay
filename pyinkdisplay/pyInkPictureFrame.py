"""
MIT License

Copyright (c) 2025 - 2026 Velotales

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.


"""

import argparse
import logging
import signal
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone

import paho.mqtt.client as mqtt
import yaml  # type: ignore[import-untyped]

from .pyInkDisplay import EPDNotFoundError, PyInkDisplay
from .pyLoggingConfig import setupLogging
from .pyMqttDiscovery import (
    publishHaBatteryDiscovery,
    publishHaTelemetry,
    publishHaTelemetryDiscovery,
)
from .pyNotifications import notifyIfConfigured
from .pySugarAlarm import PiSugarAlarm
from .pyUpdater import (
    applyUpdate,
    checkAndApplyUpdate,
    getCurrentTag,
    getLatestTag,
    restartService,
)
from .pyUtils import fetchFallbackImage, fetchImageFromUrl

# Global variables for signal handler access
displayManager = None
alarmManager = None


def isInQuietHours(now, quietConfig):
    """Return True if now falls inside the configured quiet window."""
    if not quietConfig:
        return False
    start = datetime.strptime(quietConfig["start"], "%H:%M").time()
    end = datetime.strptime(quietConfig["end"], "%H:%M").time()
    current = now.time().replace(second=0, microsecond=0)
    if start > end:  # spans midnight (e.g. 22:00-07:00)
        return current >= start or current < end
    return start <= current < end


def secondsUntilQuietEnd(now, quietConfig):
    """Return seconds from now until the end of the quiet window."""
    end_time = datetime.strptime(quietConfig["end"], "%H:%M").time()
    end_dt = now.replace(
        hour=end_time.hour, minute=end_time.minute, second=0, microsecond=0
    )
    if end_dt <= now:
        end_dt += timedelta(days=1)
    return int((end_dt - now).total_seconds())


def signalHandler(sig, frame):
    """
    Signal handler for SIGINT (Ctrl+C) and SIGTERM.
    Ensures clean GPIO shutdown and cleans up managers.
    """
    logging.info("Signal %s received. Performing cleanup...", sig)
    if displayManager:
        displayManager.closeDisplay()
        logging.info("Display cleaned up.")
    if alarmManager:
        alarmManager.close()
    logging.info("Exiting gracefully.")
    logging.shutdown()
    sys.exit(0)


def loadConfig(configPath):
    """
    Loads YAML config from the given path.

    Args:
        configPath (str): The path to the YAML config file.

    Returns:
        dict: The loaded configuration as a dictionary.
    """
    try:
        with open(configPath, "r") as f:
            config = yaml.safe_load(f)
            return config if config else {}
    except Exception as e:
        print(f"Failed to load config file {configPath}: {e}")  # noqa: B950
        return {}


def parseArguments():
    """
    Sets up and parses command-line arguments for pyInkPictureFrame.
    """
    argParser = argparse.ArgumentParser(
        description="EPD Image Display and PiSugar Alarm Setter"
    )
    argParser.add_argument(
        "-e", "--epd", type=str, help="The type of EPD driver to use"
    )
    argParser.add_argument(
        "-u", "--url", type=str, help="URL of the remote image to display on the EPD"
    )
    argParser.add_argument(
        "-a",
        "--alarmMinutes",
        type=int,
        help="Number of minutes in the future to set the PiSugar alarm (default: 20)",
    )
    argParser.add_argument(
        "--noShutdown",
        action="store_true",
        help="Do not shut down the computer after setting the alarm. For testing.",
    )
    argParser.add_argument(
        "-c", "--config", type=str, help="Path to YAML config file with settings"
    )
    return argParser.parse_args()


def mergeArgsAndConfig(args, config):
    """
    Merges command-line arguments and config file values.
    Command-line arguments take precedence over config file values.

    Args:
        args: Parsed command-line arguments.
        config (dict): Configuration dictionary.

    Returns:
        dict: Merged configuration.
    """
    merged = {}
    argToConfig = {
        "epd": "epd",
        "url": "url",
        "alarmMinutes": "alarmMinutes",
        "noShutdown": "noShutdown",
        "logging": "logging",
    }
    for arg, configKey in argToConfig.items():
        argVal = getattr(args, arg, None)
        configVal = config.get(configKey)
        if arg == "noShutdown":
            merged[arg] = argVal if argVal is not None else bool(configVal)
        elif arg == "alarmMinutes":
            merged[arg] = (
                argVal
                if argVal is not None
                else (int(configVal) if configVal is not None else 20)
            )
        elif arg == "logging":
            merged[arg] = configVal  # Only from config
        else:
            merged[arg] = argVal if argVal is not None else configVal
    return merged


def publishBatteryLevel(alarmManager, mqttConfig):
    """
    Publishes the PiSugar battery level to the configured MQTT broker.
    """
    try:
        batteryLevel = alarmManager.getBatteryLevel()
    except Exception as e:
        logging.error("Failed to get battery level for MQTT publish: %s", e)
        return
    if not mqttConfig:
        logging.warning("No MQTT config provided, skipping battery publish.")
        return
    try:
        client = mqtt.Client(protocol=mqtt.MQTTv5)
        if mqttConfig.get("username"):
            client.username_pw_set(
                mqttConfig.get("username"), mqttConfig.get("password", "")
            )
        client.connect(
            mqttConfig.get("host", "localhost"), int(mqttConfig.get("port", 1883)), 60
        )
        topic = mqttConfig.get("topic", "homeassistant/sensor/pisugar_battery/state")
        client.publish(topic, str(batteryLevel), retain=True)
        client.disconnect()
        logging.info(
            "Published battery level %s%% to MQTT topic %s",
            batteryLevel,
            topic,
        )
    except Exception as e:
        logging.error("Failed to publish battery level to MQTT: %s", e)


def runBatteryMode(alarmManager, alarmMinutes, mqttConfig, noShutdown):
    """
    One-shot battery cycle: set alarm, publish battery level, shut down immediately.

    Args:
        alarmManager: PiSugarAlarm instance.
        alarmMinutes (int): Minutes until next RTC wake alarm.
        mqttConfig (dict or None): MQTT configuration dict.
        noShutdown (bool): If True, skip the shutdown command (for testing).
    """
    secondsInFuture = alarmMinutes * 60
    wake_at = datetime.now() + timedelta(seconds=secondsInFuture)
    alarm_ok = False
    try:
        alarmManager.setAlarm(secondsInFuture=secondsInFuture)
        alarm_ok = True
    except Exception as e:
        logging.error(
            "Failed to set RTC alarm: %s. Shutting down without alarm"
            " — device will not auto-wake.",
            e,
        )
    publishBatteryLevel(alarmManager, mqttConfig)

    if not noShutdown:
        if alarm_ok:
            logging.info(
                "Shutting down — next wake at %s (%d min).",
                wake_at.strftime("%H:%M"),
                alarmMinutes,
            )
        else:
            logging.info("Shutting down — no wake alarm set.")
        try:
            subprocess.run(["sudo", "shutdown", "now"], check=True)
        except Exception as e:
            logging.error("Error during shutdown: %s", e)
            # Shutdown failed; process continues running — device stays alive
    else:
        logging.info("Skipping shutdown due to --noShutdown flag.")


def continuousEpdUpdateLoop(
    displayManager, alarmManager, imageUrl, alarmMinutes, mqttConfig=None
):
    """
    Continuously update the e-ink display at the specified interval while power is present.

    Returns True if the loop exited due to power loss (caller should run battery shutdown),
    False otherwise.

    Args:
        displayManager: The display manager object.
        alarmManager: The PiSugar alarm manager object.
        imageUrl (str): The URL to fetch images from.
        alarmMinutes (int): The interval in minutes for updating.
    """
    secondsInFuture = alarmMinutes * 60
    while True:
        sleep_until = datetime.now() + timedelta(seconds=secondsInFuture)
        logging.info(
            "Sleeping %d min until %s.",
            alarmMinutes,
            sleep_until.strftime("%H:%M"),
        )
        remainingSleepTime = secondsInFuture
        checkInterval = 5

        while remainingSleepTime > 0:
            sleepChunk = min(remainingSleepTime, checkInterval)
            time.sleep(sleepChunk)
            remainingSleepTime -= sleepChunk

            if not alarmManager.isSugarPowered():
                logging.info(
                    "Power disconnected during sleep. Transitioning to battery mode."
                )
                return True

        secondsInFuture = alarmMinutes * 60

        try:
            battery_str = f"{alarmManager.getBatteryLevel():.1f}%"
        except Exception:
            battery_str = "N/A"
        logging.info("── Update ── battery: %s", battery_str)

        logging.info("Fetching image...")
        updatedImage = fetchImageFromUrl(imageUrl)
        if updatedImage:
            logging.info("Displaying on EPD...")
            displayManager.displayImage(updatedImage)
            logging.info("EPD updated.")
            imageFetchStatus = "success"
        else:
            logging.warning("Image fetch failed. Will retry after next interval.")
            imageFetchStatus = "failure"

        if mqttConfig:
            try:
                batteryLevel = alarmManager.getBatteryLevel()
            except Exception:
                batteryLevel = None
            telemetry = {
                "battery_level": batteryLevel,
                "last_update_time": datetime.now(timezone.utc).isoformat(),
                "image_fetch_status": imageFetchStatus,
                "power_mode": "usb",
                "software_version": getCurrentTag() or "unknown",
                "update_available": False,
            }
            publishHaTelemetry(mqttConfig, telemetry)

        if not alarmManager.isSugarPowered():
            try:
                battery_str = f"{alarmManager.getBatteryLevel()}%"
            except Exception:
                battery_str = "unknown"
            logging.info(
                "Power disconnected after update (battery: %s). Transitioning to battery mode.",
                battery_str,
            )
            return True

    return False


def pyInkPictureFrame():
    """
    Main function to display image on EPD and set PiSugar alarm.
    """
    global displayManager, alarmManager  # Allow signal handler access

    # Set up signal handlers for clean shutdown
    signal.signal(signal.SIGINT, signalHandler)  # Ctrl+C
    signal.signal(signal.SIGTERM, signalHandler)  # Termination signal

    args = parseArguments()
    config = loadConfig(args.config) if args.config else {}
    merged = mergeArgsAndConfig(args, config)
    mqttConfig = config.get("mqtt") if config else None

    updaterConfig = config.get("updater", {}) if config else {}
    updaterEnabled = updaterConfig.get("enabled", True)
    forceRevert = updaterConfig.get("force_revert", False)
    appriseConfig = config.get("apprise") if config else None
    fallbackFile = config.get("fallback_file") if config else None
    iotdConfig = config.get("image_of_the_day") if config else None
    quietConfig = config.get("quiet_hours") if config else None

    loggingConfig = config.get("logging", {}) if config else {}
    setupLogging(loggingConfig)

    # Publish Home Assistant MQTT discovery if MQTT is configured
    if mqttConfig:
        publishHaBatteryDiscovery(mqttConfig)
        publishHaTelemetryDiscovery(mqttConfig)

    if not merged.get("epd"):
        logging.error("EPD type must be specified via --epd or in the config file.")
        sys.exit(1)
    if not merged.get("url"):
        logging.error("Image URL must be specified via --url or in the config file.")
        sys.exit(1)

    try:
        alarmManager = PiSugarAlarm()
        powerMode = "usb" if alarmManager.isSugarPowered() else "battery"
        try:
            batteryLevel = alarmManager.getBatteryLevel()
        except Exception:
            batteryLevel = None

        logging.info(
            "Starting | version: %s | power: %s | battery: %s | interval: %d min",
            getCurrentTag() or "dev",
            powerMode,
            f"{batteryLevel:.1f}%" if isinstance(batteryLevel, (int, float)) else "N/A",
            merged["alarmMinutes"],
        )

        now = datetime.now()
        if isInQuietHours(now, quietConfig):
            sleep_seconds = secondsUntilQuietEnd(now, quietConfig)
            wake_time = now + timedelta(seconds=sleep_seconds)
            logging.info(
                "Quiet hours active — sleeping until %s (%d minutes).",
                wake_time.strftime("%H:%M"),
                sleep_seconds // 60,
            )
            alarmManager.setAlarm(secondsInFuture=sleep_seconds)
            return

        displayManager = PyInkDisplay(epd_type=merged["epd"])
        logging.info("Fetching image...")
        image = fetchImageFromUrl(merged["url"])
        imageFetchStatus = "success"
        if image is None:
            imageFetchStatus = "failure"
            logging.warning("Image fetch failed — using fallback.")
            notifyIfConfigured(
                appriseConfig,
                "pyInkDisplay: Image Fetch Failed",
                f"Failed to fetch image from {merged['url']}",
            )
            image = fetchFallbackImage(
                fallback_file=fallbackFile, iotd_config=iotdConfig
            )
        logging.info("Displaying on EPD...")
        displayManager.displayImage(image)
        logging.info("EPD updated.")

        try:
            batteryLevel = alarmManager.getBatteryLevel()
        except Exception:
            pass  # keep startup value

        telemetry = {
            "battery_level": batteryLevel,
            "last_update_time": datetime.now(timezone.utc).isoformat(),
            "image_fetch_status": imageFetchStatus,
            "power_mode": powerMode,
            "software_version": getCurrentTag() or "unknown",
            # update_available: computed after check_and_apply_update below;
            # always False here (USB path updates telemetry before the check)
            "update_available": False,
        }

        if mqttConfig:
            publishHaTelemetry(mqttConfig, telemetry)

        batteryThreshold = (
            appriseConfig.get("battery_alert_threshold", 0) if appriseConfig else 0
        )
        if (
            batteryLevel is not None
            and batteryThreshold
            and batteryLevel < batteryThreshold
        ):
            notifyIfConfigured(
                appriseConfig,
                "pyInkDisplay: Low Battery",
                f"Battery level is {batteryLevel}% (threshold: {batteryThreshold}%)",
            )

        if alarmManager.isSugarPowered():
            logging.info("PiSugar is powered. Entering continuous update loop.")
            # force_revert intentionally bypasses the is_dev_mode() check in
            # check_and_apply_update — it is designed to escape dev mode
            if forceRevert:
                logging.info("force_revert is set. Reverting to latest release tag.")
                latestTag = getLatestTag()
                if latestTag:
                    applyUpdate(latestTag)
                    restartService()
                    logging.info("Reverted to %s. Service is restarting.", latestTag)
                    return
                else:
                    logging.warning(
                        "force_revert set but no tags found — skipping revert."
                    )
            elif updaterEnabled:
                logging.info("Checking for updates...")
                updated = checkAndApplyUpdate()
                if not updated:
                    logging.info("Up to date (%s).", getCurrentTag() or "dev")
                if updated:
                    notifyIfConfigured(
                        appriseConfig,
                        "pyInkDisplay: Update Applied",
                        "Updated to latest release. Service is restarting.",
                    )
                    logging.info("Update applied. Service is restarting.")
                    return
            else:
                logging.info("Auto-update is disabled via config.")
            power_lost = continuousEpdUpdateLoop(
                displayManager,
                alarmManager,
                merged["url"],
                merged["alarmMinutes"],
                mqttConfig,
            )
            if power_lost:
                logging.info("PiSugar is on battery. Running one-shot battery mode.")
                runBatteryMode(
                    alarmManager,
                    merged["alarmMinutes"],
                    mqttConfig,
                    merged["noShutdown"],
                )
        else:
            logging.info("PiSugar is on battery. Running one-shot battery mode.")
            runBatteryMode(
                alarmManager,
                merged["alarmMinutes"],
                mqttConfig,
                merged["noShutdown"],
            )

    except (EPDNotFoundError, RuntimeError) as e:
        logging.error("EPD display error: %s", e)
        notifyIfConfigured(appriseConfig, "pyInkDisplay: EPD Error", str(e))
        sys.exit(1)
    except Exception as e:
        logging.error("An unexpected error occurred during EPD display: %s", e)
        notifyIfConfigured(appriseConfig, "pyInkDisplay: Unexpected Error", str(e))
        sys.exit(1)
    finally:
        if displayManager:
            displayManager.closeDisplay()
            logging.info("EPD display closed.")


__all__ = [
    "pyInkPictureFrame",
    "runBatteryMode",
    "isInQuietHours",
    "secondsUntilQuietEnd",
]

if __name__ == "__main__":
    pyInkPictureFrame()
