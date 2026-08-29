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

import logging
from typing import Any, Optional

from omni_epd import EPDNotFoundError, displayfactory
from PIL import Image

logger = logging.getLogger(__name__)

# Above this relative difference in aspect ratio, cropping would cut into the
# subject (a 3:4 portrait keeps only its middle 45%), so letterbox instead.
_MAX_CROP_MISMATCH = 0.25


def fitImageToPanel(image, width, height, mismatchLimit=_MAX_CROP_MISMATCH):
    """Fit an image to the panel without distorting it.

    Crops to fill when the aspect mismatch is mild, letterboxes on black when
    it is severe. An image already at the panel's aspect ratio is scaled
    straight to size, so a dashboard capture is unaffected.
    """
    if image.width == width and image.height == height:
        return image

    srcRatio = image.width / image.height
    dstRatio = width / height
    mismatch = abs(srcRatio - dstRatio) / dstRatio

    if mismatch <= mismatchLimit:
        scale = max(width / image.width, height / image.height)
        scaled = image.resize(
            (max(1, round(image.width * scale)), max(1, round(image.height * scale)))
        )
        left = (scaled.width - width) // 2
        top = (scaled.height - height) // 2
        return scaled.crop((left, top, left + width, top + height))

    scale = min(width / image.width, height / image.height)
    scaled = image.resize(
        (max(1, round(image.width * scale)), max(1, round(image.height * scale)))
    )
    canvas = Image.new("RGB", (width, height), (0, 0, 0))
    canvas.paste(
        scaled.convert("RGB"),
        ((width - scaled.width) // 2, (height - scaled.height) // 2),
    )
    return canvas


class PyInkDisplay:
    """
    Manage and display images on E-Paper displays (EPD)
    using omni_epd.

    Supports fetching images from local files or remote URLs
    and handling display operations.
    """

    def __init__(self, epd_type: Optional[str] = None):
        """
        Initializes the PyInkDisplay.

        Args:
            epd_type (str, optional): The type of EPD driver to load.
                If None, the display driver will need to be loaded
                separately using loadDisplayDriver.
        """
        self.epd: Optional[Any] = None
        logger.info("Initializing PyInkDisplay.")

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
            logger.info("EPD driver '%s' loaded successfully.", epd_type)
            epd = self.epd
            assert epd is not None
            logger.info("EPD mode: %s", epd.mode)
            logger.info("EPD palette_filter: %s", epd.palette_filter)
            logger.info("EPD max_colors: %s", epd.max_colors)
        except EPDNotFoundError:
            logger.error("Couldn't find EPD driver: %s", epd_type)
            raise
        except Exception as e:
            logger.error("Error loading EPD driver: %s", e)
            raise

    def displayImage(self, image: Image.Image):
        """
        Displays the given PIL Image object on the EPD.

        Args:
            image (PIL.Image.Image): The image to display.

        Raises:
            RuntimeError: If the EPD driver has not been loaded.
        """
        if not self.epd:
            logger.error("EPD driver not loaded. Call loadDisplayDriver first.")
            raise RuntimeError("EPD driver not loaded.")

        logger.info("Image size: %s", image.size)
        epd = self.epd
        assert epd is not None
        image = fitImageToPanel(image, epd.width, epd.height)

        logger.info("Preparing display")
        epd.prepare()

        logger.info("Clearing display")
        epd.clear()
        logger.info("Writing to display")
        epd.display(image)
        epd.sleep()

    def closeDisplay(self):
        """Closes the EPD display connection."""
        if self.epd:
            try:
                self.epd.close()
                logger.info("EPD display closed.")
            except Exception as e:
                logger.error("Error closing EPD: %s", e)
            finally:
                self.epd = None
