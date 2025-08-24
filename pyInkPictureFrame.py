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
import sys
import time
import os
import subprocess
import yaml  # New import for YAML config support

from pyInkDisplay import PyInkDisplay, EPDNotFoundError
from pySugarAlarm import PiSugarAlarm, PiSugarConnectionError, PiSugarError

def loadConfig(configPath):
    """
    Loads YAML config from the given path.
    """
    try:
        with open(configPath, "r") as f:
            config = yaml.safe_load(f)
            if config is None:
                return {}
            return config
    except Exception as e:
        logging.error(f"Failed to load config file {configPath}: {e}")
        return {}

def mergeArgsAndConfig(args, config):
    """
    Merges command-line arguments and config file values.
    Command-line arguments take precedence over config file values.
    """
    merged = {}

    # Map of arg name to config key
    argToConfig = {
        "epd": "epd",
        "url": "url",
        "alarmMinutes": "alarmMinutes",
        "noShutdown": "noShutdown"
    }

    # For backwards compatibility, accept both snake_case and camelCase in config
    def getConfigValue(config, key):
        if key in config:
            return config[key]
        snakeKey = ''.join(['_' + c.lower() if c.isupper() else c for c in key]).lstrip('_')
        return config.get(snakeKey)

    for arg, configKey in argToConfig.items():
        argVal = getattr(args, arg, None)
        configVal = getConfigValue(config, configKey)
        # Use arg if it's set, else config, else fallback for booleans
        if arg == "noShutdown":
            merged[arg] = argVal if argVal is not None else bool(configVal)
        elif arg == "alarmMinutes":
            merged[arg] = argVal if argVal is not None else (int(configVal) if configVal is not None else 20)
        else:
            merged[arg] = argVal if argVal is not None else configVal

    return merged

def continuousEpdUpdateLoop(displayManager, alarmManager, imageUrl, alarmMinutes):
    """
    Continuously update the e-ink display at the specified interval while power is present.
    """
    secondsInFuture = alarmMinutes * 60
    keepRunningOnPower = True
    while keepRunningOnPower:
        logging.info(f"Next EPD update scheduled in {alarmMinutes} minutes ({secondsInFuture} seconds).")
        # Sleep in smaller chunks and check power status frequently
        remainingSleepTime = secondsInFuture
        checkInterval = 5

        while remainingSleepTime > 0 and keepRunningOnPower:
            sleepChunk = min(remainingSleepTime, checkInterval)
            time.sleep(sleepChunk)
            remainingSleepTime -= sleepChunk

            if not alarmManager.isSugarPowered():
                logging.info("PiSugar power detected as disconnected during sleep. Exiting continuous update loop.")
                keepRunningOnPower = False
                break

        # Set alarm for the next interval
        secondsInFuture = alarmMinutes * 60
        logging.info(f"Attempting to set PiSugar alarm for {alarmMinutes} minutes ({secondsInFuture} seconds) in the future.")
        alarmManager.setAlarm(secondsInFuture=secondsInFuture)
        logging.info("PiSugar alarm setting process completed.")

        if not keepRunningOnPower:
            break

        logging.info(f"Attempting to fetch updated image from URL: {imageUrl}")
        updatedImage = displayManager.fetchImageFromUrl(imageUrl)
        if updatedImage:
            logging.info("Updated image fetched successfully. Displaying on EPD.")
            displayManager.displayImage(updatedImage)
            logging.info("Updated image displayed on EPD.")
        else:
            logging.warning("Failed to fetch updated image. Retrying after next interval.")

        if not alarmManager.isSugarPowered():
            logging.info("PiSugar power detected as disconnected. Exiting continuous update loop.")
            keepRunningOnPower = False
            break

def pyInkPictureFrame():
    """
    Main function to parse arguments, display image on EPD, and set PiSugar alarm.
    """
    logging.basicConfig(level=logging.INFO,
                        format='%(asctime)s - %(levelname)s [%(module)s]:[%(funcName)s] - %(message)s')

    argParser = argparse.ArgumentParser(description='EPD Image Display and PiSugar Alarm Setter')
    argParser.add_argument('-e', '--epd', type=str,
                        help="The type of EPD driver to use (e.g., 'waveshare_2in13_V2')")
    argParser.add_argument('-u', '--url', type=str,
                        help="URL of the remote image to display on the EPD")
    argParser.add_argument('-a', '--alarmMinutes', type=int,
                        help="Number of minutes in the future to set the PiSugar alarm (default: 20)")
    argParser.add_argument('--noShutdown', action='store_true',
                        help="Do not shut down the computer after setting the alarm. For testing.")
    argParser.add_argument('-c', '--config', type=str,
                        help="Path to YAML config file with settings")

    args = argParser.parse_args()

    # Load config file if provided
    config = {}
    if args.config:
        config = loadConfig(args.config)

    # Merge CLI args and config file (CLI args take precedence)
    merged = mergeArgsAndConfig(args, config)

    # Required checks
    if not merged.get("epd"):
        logging.error("EPD type must be specified via --epd or in the config file.")
        sys.exit(1)
    if not merged.get("url"):
        logging.error("Image URL must be specified via --url or in the config file.")
        sys.exit(1)

    displayManager = None
    alarmManager = None

    try:
        displayManager = PyInkDisplay(epd_type=merged["epd"])
        logging.info(f"Attempting to fetch image from URL: {merged['url']}")
        image = displayManager.fetchImageFromUrl(merged["url"])

        if image:
            logging.info("Image fetched successfully. Displaying on EPD.")
            displayManager.displayImage(image)
            logging.info("Image displayed on EPD.")
        else:
            logging.error("Failed to fetch image. Skipping EPD display.")
            sys.exit(1)

        alarmManager = PiSugarAlarm()
        secondsInFuture = merged["alarmMinutes"] * 60
        logging.info(f"Attempting to set PiSugar alarm for {merged['alarmMinutes']} minutes ({secondsInFuture} seconds) in the future.")
        alarmManager.setAlarm(secondsInFuture=secondsInFuture)
        logging.info("PiSugar alarm setting process completed.")

        if alarmManager.isSugarPowered():
            logging.info("PiSugar is currently powered. Entering continuous EPD update mode.")
            continuousEpdUpdateLoop(displayManager, alarmManager, merged["url"], merged["alarmMinutes"])

        elif not merged["noShutdown"]:
            logging.info("All tasks completed. Shutting down the system...")
            try:
                if not alarmManager.isSugarPowered():
                    subprocess.run(["sudo", "shutdown", "+1"], check=True)
                    logging.info("Shutdown command issued successfully.")
            except subprocess.CalledProcessError as e:
                logging.error(f"Shutdown command failed with exit code {e.returncode}: {e}")
                logging.error("Ensure the script is run with 'sudo' and 'poweroff' command is available.")
            except FileNotFoundError:
                logging.error("The 'sudo' or 'poweroff' command was not found. Ensure they are in your system's PATH.")
            except Exception as e:
                logging.error(f"An unexpected error occurred during shutdown: {e}")
        else:
            logging.info("Skipping shutdown due to --noShutdown flag.")

    except (EPDNotFoundError, RuntimeError) as e:
        logging.error(f"EPD display error: {e}")
        sys.exit(1)
    except Exception as e:
        logging.error(f"An unexpected error occurred during EPD display: {e}")
        sys.exit(1)
    finally:
        if displayManager:
            displayManager.closeDisplay()
            logging.info("EPD display closed.")

if __name__ == "__main__":
    pyInkPictureFrame()