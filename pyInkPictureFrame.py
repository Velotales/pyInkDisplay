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

pyInkPictureFrame.py

This is the main entry point for the pyInkPictureFrame project. It parses arguments, loads configuration, sets up logging,
initializes the display and alarm managers, and orchestrates picture frame operation.
"""

import argparse
import logging
import sys
import subprocess
import yaml
import time

from pyInkDisplay import PyInkDisplay, EPDNotFoundError
from pySugarAlarm import PiSugarAlarm

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
        print(f"Failed to load config file {configPath}: {e}")
        return {}

def parseArguments():
    """
    Sets up and parses command-line arguments for pyInkPictureFrame.
    """
    argParser = argparse.ArgumentParser(description='EPD Image Display and PiSugar Alarm Setter')
    argParser.add_argument('-e', '--epd', type=str, help="The type of EPD driver to use")
    argParser.add_argument('-u', '--url', type=str, help="URL of the remote image to display on the EPD")
    argParser.add_argument('-a', '--alarmMinutes', type=int, help="Number of minutes in the future to set the PiSugar alarm (default: 20)")
    argParser.add_argument('--noShutdown', action='store_true', help="Do not shut down the computer after setting the alarm. For testing.")
    argParser.add_argument('-c', '--config', type=str, help="Path to YAML config file with settings")
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
        "logging": "logging"
    }
    for arg, configKey in argToConfig.items():
        argVal = getattr(args, arg, None)
        configVal = config.get(configKey)
        if arg == "noShutdown":
            merged[arg] = argVal if argVal is not None else bool(configVal)
        elif arg == "alarmMinutes":
            merged[arg] = argVal if argVal is not None else (int(configVal) if configVal is not None else 20)
        elif arg == "logging":
            merged[arg] = configVal  # Only from config
        else:
            merged[arg] = argVal if argVal is not None else configVal
    return merged

def setupLogging(loggingConfig):
    """
    Configures logging for the application.
    Supports both console logging and Loki logging (via loki-logger-handler).
    """
    if not loggingConfig or loggingConfig.get("type", "console").lower() == "console":
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s [%(module)s]:[%(funcName)s] - %(message)s'
        )
        logging.info("Console logging enabled.")
        return

    if loggingConfig.get("type", "").lower() == "loki":
        try:
            from loki_logger_handler.loki_logger_handler import LokiLoggerHandler
        except ImportError:
            print("loki-logger-handler is not installed. Please install with 'pip install loki-logger-handler'")
            sys.exit(1)

        url = loggingConfig.get("url")
        if not url:
            print("Loki logging selected, but no 'url' provided in config.")
            sys.exit(1)

        level = getattr(logging, loggingConfig.get("level", "INFO").upper(), logging.INFO)

        handler = LokiLoggerHandler(
            url=url,
            labels=loggingConfig.get("labels", {}),
            label_keys=loggingConfig.get("label_keys", {}),
            timeout=loggingConfig.get("timeout", 10),
            auth=(
                loggingConfig.get("username"),
                loggingConfig.get("password")
            ) if loggingConfig.get("username") and loggingConfig.get("password") else None
        )
        formatter = logging.Formatter('%(asctime)s - %(levelname)s [%(module)s]:[%(funcName)s] - %(message)s')
        handler.setFormatter(formatter)
        logger = logging.getLogger()
        logger.setLevel(level)
        logger.addHandler(handler)
        logging.info(f"Loki logging enabled to {url} with labels {loggingConfig.get('labels', {})}.")
    else:
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s [%(module)s]:[%(funcName)s] - %(message)s'
        )
        logging.warning("Unknown logging type in config; defaulting to console logging.")
        
def continuousEpdUpdateLoop(displayManager, alarmManager, imageUrl, alarmMinutes):
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
        logging.info(f"Next EPD update scheduled in {alarmMinutes} minutes ({secondsInFuture} seconds).")
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
    Main function to display image on EPD and set PiSugar alarm.
    """
    args = parseArguments()
    config = loadConfig(args.config) if args.config else {}
    merged = mergeArgsAndConfig(args, config)
    setupLogging(merged.get("logging"))

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
            except Exception as e:
                logging.error(f"Error during shutdown: {e}")
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