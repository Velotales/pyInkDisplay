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

import requests  # type: ignore[import-untyped]
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
    stop=tenacity.stop_after_attempt(3),
    wait=tenacity.wait_exponential(multiplier=1, min=1, max=10),
    retry=tenacity.retry_if_exception_type(requests.exceptions.RequestException),
)
def _fetchImageAttempt(url: str) -> Image.Image:
    """Single attempt to fetch an image. Raises on failure so tenacity can retry."""
    response = requests.get(url, timeout=10)
    response.raise_for_status()
    return Image.open(BytesIO(response.content))


def fetchImageFromUrl(url: str) -> Optional[Image.Image]:
    """Fetch an image from a URL with up to 3 retries. Returns None on failure."""
    try:
        image = _fetchImageAttempt(url)
        logger.info("Image fetched from %s", url)
        return image
    except Exception as e:
        logger.error("Failed to fetch image from %s after retries: %s", url, e)
        return None


def fetchFallbackImage(
    fallback_file: Optional[str],
    iotd_config: Optional[dict],
) -> Image.Image:
    """
    Return a fallback image using the chain:
    1. Image of the day (if provider configured)
    2. Image loaded from disk (if fallback_file configured)
    3. Generated default image (always available)
    """
    from .pyImageOfTheDay import (
        fetchImageOfTheDay,
    )  # lazy import: avoids circular dependency

    image = fetchImageOfTheDay(iotd_config)
    if image is not None:
        logger.info("Image of the day fetched successfully.")
        return image

    if fallback_file:
        try:
            image = Image.open(fallback_file)
            logger.info("Loaded fallback image from disk: %s", fallback_file)
            return image
        except Exception as e:
            logger.warning("Failed to load fallback file %s: %s", fallback_file, e)

    logger.warning("All fallbacks failed. Using generated default image.")
    return _createDefaultImage()
