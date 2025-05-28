import argparse
import logging
import sys
import time

# Import the classes from their new respective files (lower camelCase file names)
from pyInkDisplay import PyInkDisplay       
from pySugarAlarm import PiSugarAlarm, PiSugarConnectionError, PiSugarError 


def pyInkPictureFrame():
    """
    Main function to parse arguments, display image on EPD, and set PiSugar alarm.
    """
    # Global logging configuration for the entire script
    logging.basicConfig(level=logging.INFO,
                        format='%(asctime)s - %(levelname)s - %(funcName)s - %(message)s')

    parser = argparse.ArgumentParser(description='EPD Image Display and PiSugar Alarm Setter')
    parser.add_argument('-e', '--epd', type=str, required=True,
                        help="The type of EPD driver to use (e.g., 'waveshare_2in13_V2')")
    parser.add_argument('-u', '--url', type=str, required=True,
                        help="URL of the remote image to display on the EPD")
    parser.add_argument('-a', '--alarm_minutes', type=int, default=20,
                        help="Number of minutes in the future to set the PiSugar alarm (default: 20)")

    args = parser.parse_args()

    # --- EPD Display Logic ---
    displayManager = None
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

    # --- PiSugar Alarm Logic ---
    alarmManager = None
    try:
        alarmManager = PiSugarAlarm()
        secondsInFuture = args.alarm_minutes * 60
        logging.info(f"Attempting to set PiSugar alarm for {args.alarm_minutes} minutes ({secondsInFuture} seconds) in the future.")
        alarmManager.setAlarm(secondsInFuture=secondsInFuture)
        logging.info("PiSugar alarm setting process completed.")
    except (PiSugarConnectionError, PiSugarError) as e:
        logging.error(f"PiSugar alarm error: {e}")
        sys.exit(1)
    except Exception as e:
        logging.error(f"An unexpected error occurred during PiSugar alarm setup: {e}")
        sys.exit(1)


if __name__ == "__main__":
    pyInkPictureFrame()