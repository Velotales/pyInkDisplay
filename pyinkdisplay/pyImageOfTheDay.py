"""

Image-of-the-day providers for pyInkDisplay.
Supports iNaturalist (no auth) and NASA APOD (demo key or configured key).

MIT License

Copyright (c) 2026 Velotales

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
from datetime import datetime
from typing import Optional

import requests  # type: ignore[import-untyped]
from PIL import Image  # type: ignore

from .pyUtils import fetchImageFromUrl

logger = logging.getLogger(__name__)

_INATURALIST_MAX_PAGE = 500  # upper bound to avoid sparse result pages
_INATURALIST_API = (
    "https://api.inaturalist.org/v1/observations"
    "?taxon_id=3"  # taxon_id=3 is Aves (birds) in the iNaturalist taxonomy
    "&has[]=photos&quality_grade=research"
    "&per_page=1&page={page}"
)
_NASA_APOD_API = "https://api.nasa.gov/planetary/apod?api_key={key}"


def fetchImageOfTheDay(config: Optional[dict]) -> Optional[Image.Image]:
    """
    Fetch an image from the configured provider.
    Returns None if no provider is configured or all attempts fail.
    """
    if not config:
        return None
    provider = config.get("provider")
    if not provider:
        return None
    if provider == "inaturalist":
        return _fetchInaturalistImage()
    if provider == "nasa_apod":
        return _fetchNasaApodImage(config.get("nasa_apod_key", "DEMO_KEY"))
    logger.warning("Unknown image_of_the_day provider: %s", provider)
    return None


def _fetchInaturalistImage() -> Optional[Image.Image]:
    """
    Fetch a research-grade bird photo from iNaturalist.
    Uses day-of-year as a page offset for a consistent daily image.
    """
    day_of_year = datetime.now().timetuple().tm_yday
    page = (day_of_year % _INATURALIST_MAX_PAGE) + 1
    url = _INATURALIST_API.format(page=page)
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        results = response.json().get("results", [])
        if not results or not results[0].get("photos"):
            logger.warning("No photos in iNaturalist response.")
            return None
        photo_url = results[0]["photos"][0]["url"].replace("square", "large")
        logger.info("Fetching iNaturalist image from %s", photo_url)
        return fetchImageFromUrl(photo_url)
    except Exception as e:
        logger.error("iNaturalist fetch failed: %s", e)
        return None


def _fetchNasaApodImage(api_key: str) -> Optional[Image.Image]:
    """
    Fetch today's NASA Astronomy Picture of the Day.
    Returns None if today's APOD is a video rather than an image.
    """
    url = _NASA_APOD_API.format(key=api_key)
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        if data.get("media_type") != "image":
            logger.warning(
                "NASA APOD today is not an image (media_type=%s).",
                data.get("media_type"),
            )
            return None
        image_url = data.get("url")
        if not image_url:
            logger.warning("NASA APOD response missing 'url' field.")
            return None
        logger.info("Fetching NASA APOD image from %s", image_url)
        return fetchImageFromUrl(image_url)
    except Exception as e:
        logger.error("NASA APOD fetch failed: %s", e)
        return None
