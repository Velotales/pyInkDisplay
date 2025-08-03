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
import logging
from omni_epd import displayfactory, EPDNotFoundError
from PIL import Image
from io import BytesIO

logger = logging.getLogger(__name__)

class PyInkDisplay:
    """
    A class to manage and display images on E-Paper displays (EPD) using omni_epd.
    It supports fetching images from local files or remote URLs and handling display operations.
    """

    def __init__(self, epd_type: str = None):
        """
        Initializes the PyInkDisplay.

        Args:
            epd_type (str, optional): The type of EPD driver to load. If None, the display
                                      driver will need to be loaded separately using loadDisplayDriver.
        """
        self.epd = None
        logger.info(f"Initializing PyInkDisplay.")

        if epd_type:
            self.loadDisplayDriver(epd_type)

    @staticmethod
    def listSupportedDisplays():
        """Lists valid EPD display options supported by omni_epd."""
        valid_displays = displayfactory.list_supported_displays()
        print("\n".join(map(str, valid_displays)))

    def loadDisplayDriver(self, epd_type: str):
        """
        Loads the EPD display driver.

        Args:
            epd_type (str): The type of EPD driver to load (e.g., 'waveshare_2in13_V2').

        Raises:
            EPDNotFoundError: If the specified EPD driver is not found.
            Exception: For other errors during driver loading.
        """
        try:
            self.epd = displayfactory.load_display_driver(epd_type)
            logger.info(f"EPD driver '{epd_type}' loaded successfully.")
            logger.info(f"EPD mode: {self.epd.mode}")
            logger.info(f"EPD palette_filter: {self.epd.palette_filter}")
            logger.info(f"EPD max_colors: {self.epd.max_colors}")
        except EPDNotFoundError:
            logger.error(f"Couldn't find EPD driver: {epd_type}")
            raise
        except Exception as e:
            logger.error(f"Error loading EPD driver: {e}")
            raise

    @staticmethod
    def fetchImageFromUrl(url: str) -> Image.Image | None:
        """
        Downloads an image from a URL and returns it as a PIL Image object.

        Args:
            url (str): The URL to fetch the image from.

        Returns:
            PIL.Image.Image: The downloaded image as a PIL Image object, or None on error.
        """
        try:
            response = requests.get(url)
            response.raise_for_status()
            image = Image.open(BytesIO(response.content))
            logger.info(f"PIL Image object created from URL.")
            return image
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching image from {url}: {e}")
            return None
        except Exception as e:
            logger.error(f"An unexpected error occurred: {e}")
            return None

    def displayImage(self, image: Image.Image):
        """
        Displays the given PIL Image object on the EPD.

        Args:
            image (PIL.Image.Image): The image to display.

        Raises:
            RuntimeError: If the EPD driver has not been loaded.
        """
        if not self.epd:
            logger.error(f"EPD driver not loaded. Call loadDisplayDriver first.")
            raise RuntimeError("EPD driver not loaded.")

        try:
            logger.info(f"Image size: {image.size}")
            image = image.resize((self.epd.width, self.epd.height))
        except Exception as e:
            logger.error(f"Error resizing image: {e}")
            return

        logger.info(f'Preparing display')
        self.epd.prepare()

        logger.info(f'Clearing display')
        self.epd.clear()
        logger.info(f'Writing to display')
        self.epd.display(image)
        self.epd.sleep()

    def closeDisplay(self):
        """Closes the EPD display connection."""
        if self.epd:
            try:
                self.epd.close()
                logger.info(f"EPD display closed.")
            except Exception as e:
                logger.error(f"Error closing EPD: {e}")
            finally:
                self.epd = None