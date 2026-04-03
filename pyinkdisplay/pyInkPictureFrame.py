"""
MIT License

Copyright (c) 2025 Velotales

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

import paho.mqtt.client as mqtt
import yaml  # type: ignore[import-untyped]

from .mqttDiscovery import publishHaBatteryDiscovery
from .pyInkDisplay import EPDNotFoundError, PyInkDisplay
from .pySugarAlarm import PiSugarAlarm
from .updater import check_and_apply_update
from .utils import fetchImageFromUrl

# Global variables for signal handler access
displayManager = None
alarmManager = None


def signalHandler(sig, frame):
    """
    Signal handler for SIGINT (Ctrl+C) and SIGTERM.
    Ensures clean GPIO shutdown and cleans up managers.
    """
    logging.info("Signal %s received. Performing cleanup...", sig)
    if displayManager:
        displayManager.closeDisplay()
        logging.info("Display cleaned up.")
    # PiSugar alarm manager doesn't require explicit GPIO cleanup; add if needed
    logging.info("Exiting gracefully.")
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


def setupLogging(loggingConfig):
    """
    Configures logging for the application.
    Supports console logging only.
    """
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(module)s:%(funcName)s - %(message)s",
    )
    logging.info("Console logging enabled.")


def publishBatteryLevel(alarmManager, mqttConfig):
    """
    Publishes the PiSugar battery level to the configured MQTT broker.
    """
    try:
        batteryLevel = alarmManager.get_battery_level()
    except Exception as e:
        logging.error("Failed to get battery level for MQTT publish: %s", e)
        return
    if not mqttConfig:
        logging.warning("No MQTT config provided, skipping battery publish.")
        return
    try:
        client = mqtt.Client()
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
    logging.info(
        "Battery mode: setting alarm for %d minutes (%d seconds).",
        alarmMinutes,
        secondsInFuture,
    )
    alarmManager.setAlarm(secondsInFuture=secondsInFuture)
    publishBatteryLevel(alarmManager, mqttConfig)

    if not noShutdown:
        logging.info("Battery mode complete. Shutting down now.")
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

    Args:
        displayManager: The display manager object.
        alarmManager: The PiSugar alarm manager object.
        imageUrl (str): The URL to fetch images from.
        alarmMinutes (int): The interval in minutes for updating.
    """
    secondsInFuture = alarmMinutes * 60
    keepRunningOnPower = True
    while keepRunningOnPower:
        logging.info(
            "Next EPD update scheduled in %d minutes (%d seconds).",
            alarmMinutes,
            secondsInFuture,
        )
        remainingSleepTime = secondsInFuture
        checkInterval = 5

        while remainingSleepTime > 0 and keepRunningOnPower:
            sleepChunk = min(remainingSleepTime, checkInterval)
            time.sleep(sleepChunk)
            remainingSleepTime -= sleepChunk

            if not alarmManager.isSugarPowered():
                logging.info(
                    (
                        "PiSugar power detected as disconnected during sleep. "
                        "Exiting continuous update loop."
                    )
                )
                keepRunningOnPower = False
                break

        secondsInFuture = alarmMinutes * 60
        logging.info(
            (
                "Attempting to set PiSugar alarm for %d minutes "
                "(%d seconds) in the future."
            ),
            alarmMinutes,
            secondsInFuture,
        )
        alarmManager.setAlarm(secondsInFuture=secondsInFuture)
        logging.info("PiSugar alarm setting process completed.")

        # Publish battery level to MQTT after each update
        publishBatteryLevel(alarmManager, mqttConfig)

        if not keepRunningOnPower:
            break

        logging.info("Attempting to fetch updated image from URL: %s", imageUrl)
        updatedImage = fetchImageFromUrl(imageUrl)
        if updatedImage:
            logging.info("Updated image fetched successfully. Displaying on EPD.")
            displayManager.displayImage(updatedImage)
            logging.info("Updated image displayed on EPD.")
        else:
            logging.warning(
                "Failed to fetch updated image. Retrying after next interval."
            )

        if not alarmManager.isSugarPowered():
            logging.info(
                (
                    "PiSugar power detected as disconnected. "
                    "Exiting continuous update loop."
                )
            )
            keepRunningOnPower = False
            break


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

    setupLogging(merged.get("logging"))

    # Publish Home Assistant MQTT discovery if MQTT is configured
    if mqttConfig:
        publishHaBatteryDiscovery(mqttConfig)

    if not merged.get("epd"):
        logging.error("EPD type must be specified via --epd or in the config file.")
        sys.exit(1)
    if not merged.get("url"):
        logging.error("Image URL must be specified via --url or in the config file.")
        sys.exit(1)

    try:

        displayManager = PyInkDisplay(epd_type=merged["epd"])
        logging.info("Attempting to fetch image from URL: %s", merged["url"])
        image = fetchImageFromUrl(merged["url"])

        # Note: fetchImageFromUrl now returns a default image on failure.
        # Therefore, this call always succeeds.
        logging.info(
            "Image fetched successfully (or fallback used). Displaying on EPD."
        )
        displayManager.displayImage(image)
        logging.info("Image displayed on EPD.")

        alarmManager = PiSugarAlarm()

        if alarmManager.isSugarPowered():
            logging.info("PiSugar is powered. Publishing battery level.")
            publishBatteryLevel(alarmManager, mqttConfig)
            logging.info("Checking for updates...")
            updated = check_and_apply_update()
            if updated:
                # Service is restarting — exit cleanly
                logging.info("Update applied. Service is restarting.")
                return
            continuousEpdUpdateLoop(
                displayManager,
                alarmManager,
                merged["url"],
                merged["alarmMinutes"],
                mqttConfig,
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
        sys.exit(1)
    except Exception as e:
        logging.error("An unexpected error occurred during EPD display: %s", e)
        sys.exit(1)
    finally:
        if displayManager:
            displayManager.closeDisplay()
            logging.info("EPD display closed.")


__all__ = ["pyInkPictureFrame", "runBatteryMode"]

if __name__ == "__main__":
    pyInkPictureFrame()
