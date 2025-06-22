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
import subprocess # Import the subprocess module

# Import the classes from their new respective files (lower camelCase file names)
from pyInkDisplay import PyInkDisplay, EPDNotFoundError
from pySugarAlarm import PiSugarAlarm, PiSugarConnectionError, PiSugarError

def pyInkPictureFrame():
    """
    Main function to parse arguments, display image on EPD, and set PiSugar alarm.
    """
    # Global logging configuration for the entire script
    logging.basicConfig(level=logging.INFO,
                        format='%(asctime)s - %(levelname)s - %(funcName)s - %(message)s')

    argParser = argparse.ArgumentParser(description='EPD Image Display and PiSugar Alarm Setter') # Renamed parser to argParser
    argParser.add_argument('-e', '--epd', type=str, required=True,
                        help="The type of EPD driver to use (e.g., 'waveshare_2in13_V2')")
    argParser.add_argument('-u', '--url', type=str, required=True,
                        help="URL of the remote image to display on the EPD")
    argParser.add_argument('-a', '--alarm_minutes', type=int, default=20,
                        help="Number of minutes in the future to set the PiSugar alarm (default: 20)")
    argParser.add_argument('--no-shutdown', action='store_true',
                        help="Do not shut down the computer after setting the alarm. For testing.")


    args = argParser.parse_args() # Use argParser to parse arguments

    # --- EPD Display Logic ---
    displayManager = None
    alarmManager = None

    try:
        displayManager = PyInkDisplay(epd_type=args.epd)
        logging.info(f"Attempting to fetch image from URL: {args.url}")
        image = displayManager.fetchImageFromUrl(args.url)

        if image:
            logging.info("Image fetched successfully. Displaying on EPD.")
            displayManager.displayImage(image)
            logging.info("Image displayed on EPD.")
        else:
            logging.error("Failed to fetch image. Skipping EPD display.")
            sys.exit(1)

        alarmManager = PiSugarAlarm()
        secondsInFuture = args.alarm_minutes * 60
        logging.info(f"Attempting to set PiSugar alarm for {args.alarm_minutes} minutes ({secondsInFuture} seconds) in the future.")
        alarmManager.setAlarm(secondsInFuture=secondsInFuture)
        logging.info("PiSugar alarm setting process completed.")

        if alarmManager.isSugarPowered():
            logging.info("PiSugar is currently powered. Entering continuous EPD update mode.")
            # If powered, keep updating the e-ink image at the same interval
            keepRunningOnPower = True
            while keepRunningOnPower:
                logging.info(f"Next EPD update scheduled in {args.alarm_minutes} minutes ({secondsInFuture} seconds).")
                
                # Sleep in smaller chunks and check power status frequently
                remainingSleepTime = secondsInFuture
                checkInterval = 5
                
                while remainingSleepTime > 0 and keepRunningOnPower:
                    sleepChunk = min(remainingSleepTime, checkInterval)
                    time.sleep(sleepChunk)
                    remainingSleepTime -= sleepChunk

                    # Check power status during the sleep interval
                    if not alarmManager.isSugarPowered():
                        logging.info("PiSugar power detected as disconnected during sleep. Exiting continuous update loop.")
                        keepRunningOnPower = False
                        break

                # If power was disconnected during sleep, break outer loop immediately
                if not keepRunningOnPower: 
                    break
                                    
                logging.info(f"Attempting to fetch updated image from URL: {args.url}")
                updatedImage = displayManager.fetchImageFromUrl(args.url)
                if updated_image:
                    logging.info("Updated image fetched successfully. Displaying on EPD.")
                    displayManager.displayImage(updatedImage)
                    logging.info("Updated image displayed on EPD.")
                else:
                    logging.warning("Failed to fetch updated image. Retrying after next interval.")
                
                # Re-check power status in case it changes (e.g., power disconnected)
                if not alarmManager.isSugarPowered():
                    logging.info("PiSugar power detected as disconnected. Exiting continuous update loop.")
                    keepRunningOnPower = False
                    break # Exit loop to potentially shut down


        # --- Shutdown Command ---
        elif not args.no_shutdown:
            logging.info("All tasks completed. Shutting down the system...")
            try:
                # If the PiSugar is powered, don't shutdown
                if not alarmManager.isSugarPowered():
                    subprocess.run(["sudo", "shutdown", "+5"], check=True)
                    logging.info("Shutdown command issued successfully.")
            except subprocess.CalledProcessError as e:
                logging.error(f"Shutdown command failed with exit code {e.returncode}: {e}")
                logging.error("Ensure the script is run with 'sudo' and 'poweroff' command is available.")
            except FileNotFoundError:
                logging.error("The 'sudo' or 'poweroff' command was not found. Ensure they are in your system's PATH.")
            except Exception as e:
                logging.error(f"An unexpected error occurred during shutdown: {e}")
        else:
            logging.info("Skipping shutdown due to --no-shutdown flag.")

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
