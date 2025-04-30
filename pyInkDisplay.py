import requests
import os
import sys
import argparse
import logging
import time
from omni_epd import displayfactory, EPDNotFoundError
from PIL import Image
from io import BytesIO


def list_displays():
    """Lists valid EPD display options."""
    validDisplays = displayfactory.list_supported_displays()
    print("\n".join(map(str, validDisplays)))



def fetch_image(url):
    """
    Downloads an image from a URL and returns it as a PIL Image object.

    Args:
        url (str): The URL to fetch the image from.

    Returns:
        PIL.Image.Image: The downloaded image as a PIL Image object, or None on error.
    """
    try:
        # Send a GET request to the URL
        response = requests.get(url)
        response.raise_for_status()  # Raise an exception for bad status codes

        # Create a PIL Image object from the downloaded content
        image = Image.open(BytesIO(response.content))
        logging.info("PIL Image object created from URL.")
        return image

    except requests.exceptions.RequestException as e:
        logging.error(f"Error fetching image from {url}: {e}")
        return None
    except Exception as e:
        logging.error(f"An unexpected error occurred: {e}")
        return None


def render_image(epd, image):
    """
    Displays the given image on the EPD.

    Args:
        epd: The EPD driver object.
        image (PIL.Image.Image): The image to display.
    """
    try:
        logging.info(f"Image size: {image.size}")
        # Resize the image
        image = image.resize((epd.width, epd.height))
    except Exception as e:
        logging.error(f"Error resizing image: {e}")
        sys.exit()

    # prepare the epd, write the image, and close
    logging.info(f"EPD mode: {epd.mode}")
    logging.info(f"EPD palette_filter: {epd.palette_filter}")
    logging.info(f"EPD max_colors: {epd.max_colors}")
    logging.info('Preparing display')
    epd.prepare()

    logging.info('Clearing display')
    epd.clear()
    logging.info('Writing to display')
    epd.display(image)
    epd.sleep()
    try:
        epd.close()
    except Exception as e:
        logging.error(f"Error closing EPD: {e}") # Log, but don't sys.exit() here.



def main():
    """Main function to parse arguments, load display, and show image."""
    # Set up logging
    logging.basicConfig(level=logging.INFO,
                        format='%(asctime)s - %(levelname)s - %(message)s')

    logging.info('Starting')

    # Parse arguments
    parser = argparse.ArgumentParser(description='EPD Test Utility')
    mutex_group = parser.add_mutually_exclusive_group(required=True)
    mutex_group.add_argument('-l', '--list', action='store_true',
                                help="List valid EPD display options")
    mutex_group.add_argument('-e', '--epd',
                                help="The type of EPD driver to test")
    mutex_group2 = parser.add_mutually_exclusive_group(required=False)
    mutex_group2.add_argument('-i', '--image', type=str,
                                help="Path to an image file to draw on the display")
    mutex_group2.add_argument('-r', '--remote', type=str,
                                help="URL of remote image to show")

    args = parser.parse_args()

    if args.list:
        # list valid displays and exit
        list_displays()
        sys.exit()

    try:
        epd = displayfactory.load_display_driver(args.epd)
    except EPDNotFoundError:
        logging.error(f"Couldn't find EPD driver: {args.epd}")
        sys.exit()
    except Exception as e:
        logging.error(f"Error loading EPD driver: {e}")
        sys.exit()

    if args.image:
        try:
            image = Image.open(args.image)
            render_image(epd, image) #show image once
        except FileNotFoundError:
            logging.error(f"Image file not found: {args.image}")
            sys.exit()
        except Exception as e:
            logging.error(f"Error opening image file: {e}")
            sys.exit()
    elif args.remote:
        url = args.remote
        while True: #loop until user exits
            image = fetch_image(url)
            if image:
                render_image(epd, image)
            time.sleep(60) #wait 60 seconds
    else:
        logging.info("No image source provided. Exiting.")
        sys.exit()

    logging.info('Exiting')



if __name__ == "__main__":
    main()
