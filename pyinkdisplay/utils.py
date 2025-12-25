"""

Shared utilities for pyInkDisplay project.

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
from io import BytesIO
from typing import Optional

import requests
import tenacity
from PIL import Image, ImageDraw

logger = logging.getLogger(__name__)


def _createDefaultImage(width: int = 800, height: int = 480) -> Image.Image:
    """
    Creates a default fallback image for display when fetching fails.
    This is a simple black image with white text indicating an error.

    Args:
        width (int): Width of the image.
        height (int): Height of the image.

    Returns:
        PIL.Image.Image: A default image.
    """
    # Create a black image
    image = Image.new("1", (width, height), 0)  # '1' for 1-bit black and white
    draw = ImageDraw.Draw(image)
    # Draw white text (since background is black)
    text = "Image Fetch Failed\nCheck Network"
    # Simple text placement (PIL's default font is basic)
    draw.text((10, height // 2 - 20), text, fill=1)
    return image


@tenacity.retry(
    stop=tenacity.stop_after_attempt(3),  # Retry up to 3 times
    wait=tenacity.wait_exponential(multiplier=1, min=1, max=10),  # Exponential backoff
    retry=tenacity.retry_if_exception_type(
        (requests.exceptions.RequestException, Exception)
    ),
    reraise=True,  # Re-raise after retries
)
def fetchImageFromUrl(url: str) -> Optional[Image.Image]:
    """
    Downloads an image from a URL and returns it as a PIL Image object.
    Includes retries for network requests and fallback to a default image on failure.

    Args:
        url (str): The URL to fetch the image from.

    Returns:
        PIL.Image.Image: The downloaded image as a PIL Image object, or a default fallback image on error.
    """
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        image = Image.open(BytesIO(response.content))
        logger.info("PIL Image object created from URL.")
        return image
    except requests.exceptions.RequestException as e:
        logger.error("Error fetching image from %s: %s", url, e)
        logger.info("Returning default fallback image due to fetch failure.")
        return _createDefaultImage()
    except Exception as e:
        logger.error("An unexpected error occurred: %s", e)
        logger.info("Returning default fallback image due to unexpected error.")
        return _createDefaultImage()
