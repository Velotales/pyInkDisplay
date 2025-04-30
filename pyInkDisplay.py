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
        logging.info(f"{fetch_image.__name__}: PIL Image object created from URL.")
        return image

    except requests.exceptions.RequestException as e:
        logging.error(f"{fetch_image.__name__}: Error fetching image from {url}: {e}")
        return None
    except Exception as e:
        logging.error(f"{fetch_image.__name__}: An unexpected error occurred: {e}")
        return None



def render_image(epd, image):
    """
    Displays the given image on the EPD.

    Args:
        epd: The EPD driver object.
        image (PIL.Image.Image): The image to display.
    """
    try:
        logging.info(f"{render_image.__name__}: Image size: {image.size}")
        # Resize the image
        image = image.resize((epd.width, epd.height))
    except Exception as e:
        logging.error(f"{render_image.__name__}: Error resizing image: {e}")
        return  # Log the error and return, don't exit.

    # prepare the epd, write the image, and close
    logging.info(f'{render_image.__name__}: Preparing display')
    epd.prepare()

    logging.info(f'{render_image.__name__}: Clearing display')
    epd.clear()
    logging.info(f'{render_image.__name__}: Writing to display')
    epd.display(image)
    epd.sleep()
    try:
        epd.close()
    except Exception as e:
        logging.error(f"{render_image.__name__}: Error closing EPD: {e}")  # Log, but don't sys.exit() here.



def main():
    """Main function to parse arguments, load display, and show image."""
    # Set up logging
    logging.basicConfig(level=logging.INFO,
                        format='%(asctime)s - %(levelname)s - %(message)s')

    logging.info(f'{main.__name__}: Starting')

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
    parser.add_argument('-t', '--time', type=int,
                             help="Time between updates in seconds. If provided with -r, the image will update repeatedly.")

    args = parser.parse_args()

    if args.list:
        # list valid displays and exit
        list_displays()
        sys.exit()

    epd = None  # Initialize epd outside the try block
    try:
        epd = displayfactory.load_display_driver(args.epd)
    except EPDNotFoundError:
        logging.error(f"{main.__name__}: Couldn't find EPD driver: {args.epd}")
        sys.exit()
    except Exception as e:
        logging.error(f"{main.__name__}: Error loading EPD driver: {e}")
        sys.exit()

    logging.info(f"{render_image.__name__}: EPD mode: {epd.mode}")
    logging.info(f"{render_image.__name__}: EPD palette_filter: {epd.palette_filter}")
    logging.info(f"{render_image.__name__}: EPD max_colors: {epd.max_colors}")

    try:  # Put the main logic in a try block for cleanup
        if args.image:
            try:
                image = Image.open(args.image)
                render_image(epd, image)  # show image once
            except FileNotFoundError:
                logging.error(f"{main.__name__}: Image file not found: {args.image}")
                sys.exit()
            except Exception as e:
                logging.error(f"{main.__name__}: Error opening image file: {e}")
                sys.exit()
        elif args.remote:
            url = args.remote
            if args.time is not None:
                while True:  # loop until user exits
                    image = fetch_image(url)
                    if image:
                        render_image(epd, image)
                    logging.info(f"{main.__name__}: Time to refresh: {args.time}")
                    time.sleep(args.time)  # wait user specified time
            else:
                # Fetch and display once, then exit
                image = fetch_image(url)
                render_image(epd, image)
                logging.info(f"{main.__name__}: Displayed remote image once. Exiting.")
        else:
            logging.info(f"{main.__name__}: No image source provided. Exiting.")
            sys.exit()

    finally:  # Use a finally block to ensure cleanup
        if epd:
            try:
                epd.close()  # Ensure the display is closed
                logging.info(f"{main.__name__}: EPD display closed.")
            except Exception as e:
                logging.error(f"{main.__name__}: Error closing EPD: {e}")

    logging.info(f'{main.__name__}: Exiting')


if __name__ == "__main__":
    main()
