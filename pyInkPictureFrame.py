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
import signal

from pyInkDisplay import PyInkDisplay, EPDNotFoundError
from pySugarAlarm import PiSugarAlarm
from utils import fetchImageFromUrl

# Global variables for signal handler access
displayManager = None
alarmManager = None

def signalHandler(sig, frame):
    """
    Signal handler for SIGINT (Ctrl+C) and SIGTERM to ensure clean GPIO shutdown.
    Cleans up display and alarm managers before exiting.
    """
    logging.info(f"Signal {sig} received. Performing cleanup...")
    if displayManager:
        displayManager.closeDisplay()
        logging.info("Display cleaned up.")
    # PiSugar alarm manager doesn't require explicit GPIO cleanup in this setup, but add if needed
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
    Supports console logging only.
    """
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(module)s:%(funcName)s - %(message)s'
    )
    logging.info("Console logging enabled.")

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
        logging.info("Next EPD update scheduled in %d minutes (%d seconds).", alarmMinutes, secondsInFuture)
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
        logging.info("Attempting to set PiSugar alarm for %d minutes (%d seconds) in the future.", alarmMinutes, secondsInFuture)
        alarmManager.setAlarm(secondsInFuture=secondsInFuture)
        logging.info("PiSugar alarm setting process completed.")

        if not keepRunningOnPower:
            break

        logging.info("Attempting to fetch updated image from URL: %s", imageUrl)
        updatedImage = fetchImageFromUrl(imageUrl)
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
    global displayManager, alarmManager  # Allow signal handler access

    # Set up signal handlers for clean shutdown
    signal.signal(signal.SIGINT, signalHandler)  # Ctrl+C
    signal.signal(signal.SIGTERM, signalHandler)  # Termination signal

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

    try:
        displayManager = PyInkDisplay(epd_type=merged["epd"])
        logging.info("Attempting to fetch image from URL: %s", merged["url"])
        image = fetchImageFromUrl(merged["url"])

        # Note: fetchImageFromUrl now returns a default image on failure, so this always succeeds
        logging.info("Image fetched successfully (or fallback used). Displaying on EPD.")
        displayManager.displayImage(image)
        logging.info("Image displayed on EPD.")

        alarmManager = PiSugarAlarm()
        secondsInFuture = merged["alarmMinutes"] * 60
        logging.info("Attempting to set PiSugar alarm for %d minutes (%d seconds) in the future.", merged["alarmMinutes"], secondsInFuture)
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
                logging.error("Error during shutdown: %s", e)
        else:
            logging.info("Skipping shutdown due to --noShutdown flag.")

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

if __name__ == "__main__":
    pyInkPictureFrame()