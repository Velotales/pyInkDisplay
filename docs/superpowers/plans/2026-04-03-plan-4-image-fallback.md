# Image Fallback Chain Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** When the configured image URL fails, display something useful. A new `pyImageOfTheDay` module encapsulates all provider-specific logic (iNaturalist, NASA APOD). The fallback chain in `pyUtils.fetchFallbackImage` calls image-of-the-day, then loads from disk, then falls back to a generated default — so `pyInkPictureFrame` just calls two functions and always gets an image.

**Architecture:**
- `pyImageOfTheDay.py` — new module. Knows about providers (iNaturalist, NASA APOD). Exposes one function: `fetchImageOfTheDay(config)`. Returns `None` if provider not configured or all attempts fail.
- `pyUtils.fetchFallbackImage(fallback_file, iotd_config)` — orchestrates: `fetchImageOfTheDay` → load from disk → `_createDefaultImage`. Always returns an image.
- `pyInkPictureFrame` — chain is just: `fetchImageFromUrl` → `fetchFallbackImage`. No knowledge of providers.
- `fetchImageFromUrl` is also refactored so tenacity retries actually fire (currently broken).

**Tech Stack:** Python 3.8+, requests, PIL, tenacity, iNaturalist API (no auth), NASA APOD API (demo key)

---

## File Map

| File | Change |
|------|--------|
| `pyinkdisplay/pyUtils.py` | Refactor `fetchImageFromUrl`; add `_fetchImageAttempt`; refactor `fetchFallbackImage` |
| `pyinkdisplay/pyImageOfTheDay.py` | New module: `fetchImageOfTheDay`, `_fetchInaturalistImage`, `_fetchNasaApodImage` |
| `pyinkdisplay/pyInkPictureFrame.py` | Import `fetchFallbackImage`; read fallback config; replace `sys.exit(1)` |
| `config/config.yaml` | Add `fallback_file`, `image_of_the_day` sections |
| `tests/test_py_utils.py` | Update failure test; add retry test; update fallback tests |
| `tests/test_py_image_of_the_day.py` | New test file for pyImageOfTheDay |
| `tests/test_py_ink_picture_frame.py` | Add fallback wiring test; update notification test |

---

### Task 1: Refactor `fetchImageFromUrl` to return `None` on failure

The current implementation swallows exceptions inside the tenacity-decorated function, so retries never fire. Split into `_fetchImageAttempt` (raises, has the decorator) and `fetchImageFromUrl` (catches, returns `None`).

**Files:**
- Modify: `pyinkdisplay/pyUtils.py`
- Modify: `tests/test_py_utils.py`

- [ ] **Step 1: Update the existing failure test to assert `None` is returned**

Replace `test_fetchImageFromUrl_failure` in `tests/test_py_utils.py`:

```python
def test_fetchImageFromUrl_failure():
    """Returns None when the HTTP request fails after retries."""
    import requests as req
    with patch("pyinkdisplay.pyUtils._fetchImageAttempt",
               side_effect=req.exceptions.ConnectionError("refused")):
        result = utils.fetchImageFromUrl("http://example.com/image.jpg")
    assert result is None
```

- [ ] **Step 2: Run the test to confirm it fails**

```bash
cd /home/dwalsh/Development/pyInkDisplay && \
  python -m pytest tests/test_py_utils.py::test_fetchImageFromUrl_failure -v
```

Expected: `FAILED` — `_fetchImageAttempt` does not exist yet.

- [ ] **Step 3: Add the retry-verification test**

Append to `tests/test_py_utils.py`:

```python
def test_fetchImageFromUrl_retries_on_request_error():
    """requests.get is called up to 3 times on RequestException."""
    import requests as req
    with patch("pyinkdisplay.pyUtils.requests.get",
               side_effect=req.exceptions.ConnectionError("refused")) as mock_get:
        result = utils.fetchImageFromUrl("http://example.com/image.jpg")
    assert result is None
    assert mock_get.call_count == 3
```

- [ ] **Step 4: Run the retry test to confirm it fails**

```bash
cd /home/dwalsh/Development/pyInkDisplay && \
  python -m pytest tests/test_py_utils.py::test_fetchImageFromUrl_retries_on_request_error -v
```

Expected: `FAILED` — call count will be 1 because exceptions are currently swallowed.

- [ ] **Step 5: Refactor `pyinkdisplay/pyUtils.py`**

Replace the existing `fetchImageFromUrl` function with these two:

```python
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
```

- [ ] **Step 6: Run all pyUtils tests**

```bash
cd /home/dwalsh/Development/pyInkDisplay && \
  python -m pytest tests/test_py_utils.py -v
```

Expected: all `PASSED`.

- [ ] **Step 7: Run the full test suite**

```bash
cd /home/dwalsh/Development/pyInkDisplay && python -m pytest -v
```

Expected: all previously-passing tests still pass.

- [ ] **Step 8: Commit**

```bash
cd /home/dwalsh/Development/pyInkDisplay && \
  git add pyinkdisplay/pyUtils.py tests/test_py_utils.py && \
  git commit -m "refactor: fetchImageFromUrl returns None on failure, fix tenacity retry"
```

---

### Task 2: Create `pyImageOfTheDay.py`

New module encapsulating all provider-specific logic. Supports iNaturalist (no auth) and NASA APOD (demo key). `pyInkPictureFrame` and `pyUtils` never import provider-specific code directly.

**Files:**
- Create: `pyinkdisplay/pyImageOfTheDay.py`
- Create: `tests/test_py_image_of_the_day.py`

- [ ] **Step 1: Create the test file with failing tests**

Create `tests/test_py_image_of_the_day.py`:

```python
"""Unit tests for pyImageOfTheDay.py"""

from unittest.mock import MagicMock, patch

import pyinkdisplay.pyImageOfTheDay as iotd


def test_fetchImageOfTheDay_returns_none_when_provider_not_configured():
    """Returns None when no provider is configured."""
    result = iotd.fetchImageOfTheDay(None)
    assert result is None

    result = iotd.fetchImageOfTheDay({})
    assert result is None

    result = iotd.fetchImageOfTheDay({"provider": None})
    assert result is None


def test_fetchImageOfTheDay_dispatches_to_inaturalist():
    """Calls _fetchInaturalistImage when provider is 'inaturalist'."""
    mock_image = MagicMock()
    with patch("pyinkdisplay.pyImageOfTheDay._fetchInaturalistImage",
               return_value=mock_image) as mock_fetch:
        result = iotd.fetchImageOfTheDay({"provider": "inaturalist"})
    mock_fetch.assert_called_once()
    assert result == mock_image


def test_fetchImageOfTheDay_dispatches_to_nasa_apod():
    """Calls _fetchNasaApodImage when provider is 'nasa_apod'."""
    mock_image = MagicMock()
    with patch("pyinkdisplay.pyImageOfTheDay._fetchNasaApodImage",
               return_value=mock_image) as mock_fetch:
        result = iotd.fetchImageOfTheDay({"provider": "nasa_apod", "nasa_apod_key": "ABC123"})
    mock_fetch.assert_called_once_with("ABC123")
    assert result == mock_image


def test_fetchImageOfTheDay_unknown_provider_returns_none():
    """Returns None (with a warning) for unknown provider names."""
    result = iotd.fetchImageOfTheDay({"provider": "unknown_source"})
    assert result is None


def test_fetchInaturalistImage_returns_image_on_success():
    """Returns an image when iNaturalist returns a valid observation."""
    mock_api_response = MagicMock()
    mock_api_response.raise_for_status = MagicMock()
    mock_api_response.json.return_value = {
        "results": [{
            "photos": [{"url": "https://inaturalist.org/photos/1/square.jpg"}]
        }]
    }
    mock_image = MagicMock()

    with patch("pyinkdisplay.pyImageOfTheDay.requests.get",
               return_value=mock_api_response), \
         patch("pyinkdisplay.pyImageOfTheDay.fetchImageFromUrl",
               return_value=mock_image) as mock_fetch:
        result = iotd._fetchInaturalistImage()

    mock_fetch.assert_called_once_with("https://inaturalist.org/photos/1/large.jpg")
    assert result == mock_image


def test_fetchInaturalistImage_returns_none_on_empty_results():
    """Returns None when iNaturalist returns no observations."""
    mock_api_response = MagicMock()
    mock_api_response.raise_for_status = MagicMock()
    mock_api_response.json.return_value = {"results": []}

    with patch("pyinkdisplay.pyImageOfTheDay.requests.get",
               return_value=mock_api_response):
        result = iotd._fetchInaturalistImage()

    assert result is None


def test_fetchInaturalistImage_returns_none_on_api_error():
    """Returns None when the iNaturalist API call raises."""
    import requests as req
    with patch("pyinkdisplay.pyImageOfTheDay.requests.get",
               side_effect=req.exceptions.ConnectionError("refused")):
        result = iotd._fetchInaturalistImage()

    assert result is None


def test_fetchNasaApodImage_returns_image_on_success():
    """Returns an image when NASA APOD returns a valid photo URL."""
    mock_api_response = MagicMock()
    mock_api_response.raise_for_status = MagicMock()
    mock_api_response.json.return_value = {
        "media_type": "image",
        "url": "https://apod.nasa.gov/apod/image/today.jpg",
    }
    mock_image = MagicMock()

    with patch("pyinkdisplay.pyImageOfTheDay.requests.get",
               return_value=mock_api_response), \
         patch("pyinkdisplay.pyImageOfTheDay.fetchImageFromUrl",
               return_value=mock_image) as mock_fetch:
        result = iotd._fetchNasaApodImage("DEMO_KEY")

    mock_fetch.assert_called_once_with("https://apod.nasa.gov/apod/image/today.jpg")
    assert result == mock_image


def test_fetchNasaApodImage_returns_none_when_media_is_video():
    """Returns None when APOD media_type is 'video' (not displayable)."""
    mock_api_response = MagicMock()
    mock_api_response.raise_for_status = MagicMock()
    mock_api_response.json.return_value = {
        "media_type": "video",
        "url": "https://www.youtube.com/watch?v=xyz",
    }

    with patch("pyinkdisplay.pyImageOfTheDay.requests.get",
               return_value=mock_api_response):
        result = iotd._fetchNasaApodImage("DEMO_KEY")

    assert result is None


def test_fetchNasaApodImage_returns_none_on_api_error():
    """Returns None when the NASA APOD API call raises."""
    import requests as req
    with patch("pyinkdisplay.pyImageOfTheDay.requests.get",
               side_effect=req.exceptions.ConnectionError("refused")):
        result = iotd._fetchNasaApodImage("DEMO_KEY")

    assert result is None
```

- [ ] **Step 2: Run the tests to confirm they all fail**

```bash
cd /home/dwalsh/Development/pyInkDisplay && \
  python -m pytest tests/test_py_image_of_the_day.py -v
```

Expected: all `FAILED` — module does not exist yet.

- [ ] **Step 3: Create `pyinkdisplay/pyImageOfTheDay.py`**

```python
"""
MIT License

Copyright (c) 2025 Velotales

...licence header...

Image-of-the-day providers for pyInkDisplay.
Supports iNaturalist (no auth) and NASA APOD (demo key or configured key).
"""

import logging
from datetime import datetime
from typing import Optional

import requests
from PIL import Image  # type: ignore

from .pyUtils import fetchImageFromUrl

logger = logging.getLogger(__name__)

_INATURALIST_API = (
    "https://api.inaturalist.org/v1/observations"
    "?taxon_id=3&has[]=photos&quality_grade=research&per_page=1&page={page}"
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
    page = (day_of_year % 500) + 1
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
    url = _NASA_APOD_API.format(key=api_key or "DEMO_KEY")
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        if data.get("media_type") != "image":
            logger.warning("NASA APOD today is not an image (media_type=%s).", data.get("media_type"))
            return None
        image_url = data.get("url")
        logger.info("Fetching NASA APOD image from %s", image_url)
        return fetchImageFromUrl(image_url)
    except Exception as e:
        logger.error("NASA APOD fetch failed: %s", e)
        return None
```

- [ ] **Step 4: Run the tests to confirm they pass**

```bash
cd /home/dwalsh/Development/pyInkDisplay && \
  python -m pytest tests/test_py_image_of_the_day.py -v
```

Expected: all `PASSED`.

- [ ] **Step 5: Run the full test suite**

```bash
cd /home/dwalsh/Development/pyInkDisplay && python -m pytest -v
```

Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
cd /home/dwalsh/Development/pyInkDisplay && \
  git add pyinkdisplay/pyImageOfTheDay.py tests/test_py_image_of_the_day.py && \
  git commit -m "feat: add pyImageOfTheDay module with iNaturalist and NASA APOD providers"
```

---

### Task 3: Refactor `fetchFallbackImage` in `pyUtils.py`

Replace the existing `fetchFallbackImage` (which currently calls `_createDefaultImage` and `fetchBirdOfTheDay`) with a version that chains: `fetchImageOfTheDay` → load from disk → `_createDefaultImage`. Always returns an image.

**Files:**
- Modify: `pyinkdisplay/pyUtils.py`
- Modify: `tests/test_py_utils.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_py_utils.py`:

```python
def test_fetchFallbackImage_uses_image_of_the_day_first():
    """Calls fetchImageOfTheDay and returns its result when it succeeds."""
    mock_image = MagicMock()
    iotd_config = {"provider": "inaturalist"}
    with patch("pyinkdisplay.pyUtils.fetchImageOfTheDay", return_value=mock_image) as mock_iotd:
        result = utils.fetchFallbackImage(fallback_file=None, iotd_config=iotd_config)
    mock_iotd.assert_called_once_with(iotd_config)
    assert result == mock_image


def test_fetchFallbackImage_loads_from_disk_when_iotd_fails():
    """Falls through to disk image when image-of-the-day returns None."""
    mock_image = MagicMock()
    with patch("pyinkdisplay.pyUtils.fetchImageOfTheDay", return_value=None), \
         patch("pyinkdisplay.pyUtils.Image.open", return_value=mock_image):
        result = utils.fetchFallbackImage(fallback_file="/some/image.png", iotd_config=None)
    assert result == mock_image


def test_fetchFallbackImage_uses_default_when_disk_load_fails():
    """Falls through to _createDefaultImage when disk load raises."""
    mock_image = MagicMock()
    with patch("pyinkdisplay.pyUtils.fetchImageOfTheDay", return_value=None), \
         patch("pyinkdisplay.pyUtils.Image.open", side_effect=OSError("not found")), \
         patch("pyinkdisplay.pyUtils._createDefaultImage", return_value=mock_image):
        result = utils.fetchFallbackImage(fallback_file="/missing.png", iotd_config=None)
    assert result == mock_image


def test_fetchFallbackImage_uses_default_when_nothing_configured():
    """Falls straight to _createDefaultImage when no fallback is configured."""
    mock_image = MagicMock()
    with patch("pyinkdisplay.pyUtils.fetchImageOfTheDay", return_value=None), \
         patch("pyinkdisplay.pyUtils._createDefaultImage", return_value=mock_image):
        result = utils.fetchFallbackImage(fallback_file=None, iotd_config=None)
    assert result == mock_image
```

- [ ] **Step 2: Run the tests to confirm they fail**

```bash
cd /home/dwalsh/Development/pyInkDisplay && \
  python -m pytest \
    tests/test_py_utils.py::test_fetchFallbackImage_uses_image_of_the_day_first \
    tests/test_py_utils.py::test_fetchFallbackImage_loads_from_disk_when_iotd_fails \
    tests/test_py_utils.py::test_fetchFallbackImage_uses_default_when_disk_load_fails \
    tests/test_py_utils.py::test_fetchFallbackImage_uses_default_when_nothing_configured -v
```

Expected: all `FAILED`.

- [ ] **Step 3: Update `pyinkdisplay/pyUtils.py`**

Add the import for `fetchImageOfTheDay` at the top of the file (after existing imports):

```python
from .pyImageOfTheDay import fetchImageOfTheDay
```

Replace the existing `fetchFallbackImage` function with:

```python
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
```

- [ ] **Step 4: Run the fallback tests to confirm they pass**

```bash
cd /home/dwalsh/Development/pyInkDisplay && \
  python -m pytest \
    tests/test_py_utils.py::test_fetchFallbackImage_uses_image_of_the_day_first \
    tests/test_py_utils.py::test_fetchFallbackImage_loads_from_disk_when_iotd_fails \
    tests/test_py_utils.py::test_fetchFallbackImage_uses_default_when_disk_load_fails \
    tests/test_py_utils.py::test_fetchFallbackImage_uses_default_when_nothing_configured -v
```

Expected: all `PASSED`.

- [ ] **Step 5: Run the full test suite**

```bash
cd /home/dwalsh/Development/pyInkDisplay && python -m pytest -v
```

Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
cd /home/dwalsh/Development/pyInkDisplay && \
  git add pyinkdisplay/pyUtils.py tests/test_py_utils.py && \
  git commit -m "feat: fetchFallbackImage chains image-of-the-day, disk, and default"
```

---

### Task 4: Wire fallback into `pyInkPictureFrame.py` and update config

Replace `sys.exit(1)` on fetch failure with `fetchFallbackImage`. Read `fallback_file` and `image_of_the_day` from config. Add both keys to `config.yaml`.

**Files:**
- Modify: `pyinkdisplay/pyInkPictureFrame.py`
- Modify: `config/config.yaml`
- Modify: `tests/test_py_ink_picture_frame.py`

- [ ] **Step 1: Write the new fallback wiring test**

Append to `tests/test_py_ink_picture_frame.py`:

```python
def test_pyInkPictureFrame_uses_fallback_when_main_fetch_fails():
    """When main fetch returns None, calls fetchFallbackImage with config values."""
    with patch("pyinkdisplay.pyInkPictureFrame.parseArguments") as mock_args, \
         patch("pyinkdisplay.pyInkPictureFrame.loadConfig", return_value={}), \
         patch("pyinkdisplay.pyInkPictureFrame.mergeArgsAndConfig", return_value={
             "epd": "waveshare_epd.epd7in3f", "url": "http://example.com",
             "alarmMinutes": 20, "noShutdown": True, "logging": None,
             "fallback_file": "/some/image.png",
             "image_of_the_day": {"provider": "inaturalist"},
         }), \
         patch("pyinkdisplay.pyInkPictureFrame.setupLogging"), \
         patch("pyinkdisplay.pyInkPictureFrame.PyInkDisplay"), \
         patch("pyinkdisplay.pyInkPictureFrame.fetchImageFromUrl", return_value=None), \
         patch("pyinkdisplay.pyInkPictureFrame.fetchFallbackImage") as mock_fallback, \
         patch("pyinkdisplay.pyInkPictureFrame.notifyIfConfigured"), \
         patch("pyinkdisplay.pyInkPictureFrame.PiSugarAlarm") as mock_alarm_cls, \
         patch("pyinkdisplay.pyInkPictureFrame.runBatteryMode"):

        mock_args.return_value.config = None
        mock_alarm = MagicMock()
        mock_alarm.isSugarPowered.return_value = False
        mock_alarm_cls.return_value = mock_alarm
        mock_fallback.return_value = MagicMock()

        pyInkPictureFrame()

    mock_fallback.assert_called_once_with(
        fallback_file="/some/image.png",
        iotd_config={"provider": "inaturalist"},
    )
```

- [ ] **Step 2: Update `test_pyInkPictureFrame_notifies_on_image_fetch_failure`**

Replace the existing test with a version that expects no `SystemExit` and patches `fetchFallbackImage`:

```python
def test_pyInkPictureFrame_notifies_on_image_fetch_failure():
    """Sends an Apprise notification when image fetch returns None, then uses fallback."""
    with patch("pyinkdisplay.pyInkPictureFrame.parseArguments") as mock_args, \
         patch("pyinkdisplay.pyInkPictureFrame.loadConfig",
               return_value={"apprise": {"url": "http://apprise.local"}}), \
         patch("pyinkdisplay.pyInkPictureFrame.mergeArgsAndConfig", return_value={
             "epd": "waveshare_epd.epd7in3f", "url": "http://example.com",
             "alarmMinutes": 20, "noShutdown": True, "logging": None,
             "fallback_file": None, "image_of_the_day": None,
         }), \
         patch("pyinkdisplay.pyInkPictureFrame.setupLogging"), \
         patch("pyinkdisplay.pyInkPictureFrame.PyInkDisplay"), \
         patch("pyinkdisplay.pyInkPictureFrame.fetchImageFromUrl", return_value=None), \
         patch("pyinkdisplay.pyInkPictureFrame.fetchFallbackImage", return_value=MagicMock()), \
         patch("pyinkdisplay.pyInkPictureFrame.PiSugarAlarm") as mock_alarm_cls, \
         patch("pyinkdisplay.pyInkPictureFrame.runBatteryMode"), \
         patch("pyinkdisplay.pyInkPictureFrame.notifyIfConfigured") as mock_notify:

        mock_args.return_value.config = "config.yaml"
        mock_alarm = MagicMock()
        mock_alarm.isSugarPowered.return_value = False
        mock_alarm_cls.return_value = mock_alarm

        pyInkPictureFrame()  # must NOT raise SystemExit

    mock_notify.assert_any_call(
        {"url": "http://apprise.local"},
        "pyInkDisplay: Image Fetch Failed",
        "Failed to fetch image from http://example.com",
    )
```

- [ ] **Step 3: Run both tests to confirm they fail**

```bash
cd /home/dwalsh/Development/pyInkDisplay && \
  python -m pytest \
    tests/test_py_ink_picture_frame.py::test_pyInkPictureFrame_uses_fallback_when_main_fetch_fails \
    tests/test_py_ink_picture_frame.py::test_pyInkPictureFrame_notifies_on_image_fetch_failure -v
```

Expected: both `FAILED`.

- [ ] **Step 4: Update the import in `pyinkdisplay/pyInkPictureFrame.py`**

Find:

```python
from .pyUtils import fetchImageFromUrl
```

Replace with:

```python
from .pyUtils import fetchFallbackImage, fetchImageFromUrl
```

- [ ] **Step 5: Read fallback config in `pyInkPictureFrame()`**

Find:

```python
    appriseConfig = config.get("apprise") if config else None
```

Add two lines after it:

```python
    fallbackFile = config.get("fallback_file") if config else None
    iotdConfig = config.get("image_of_the_day") if config else None
```

- [ ] **Step 6: Replace `sys.exit(1)` with `fetchFallbackImage`**

Find:

```python
        image = fetchImageFromUrl(merged["url"])
        if image is None:
            logging.warning("Image fetch returned None — using fallback.")
            notifyIfConfigured(
                appriseConfig,
                "pyInkDisplay: Image Fetch Failed",
                f"Failed to fetch image from {merged['url']}",
            )
            logging.error("No image available — aborting cycle.")
            sys.exit(1)
```

Replace with:

```python
        image = fetchImageFromUrl(merged["url"])
        if image is None:
            logging.warning("Image fetch returned None — using fallback.")
            notifyIfConfigured(
                appriseConfig,
                "pyInkDisplay: Image Fetch Failed",
                f"Failed to fetch image from {merged['url']}",
            )
            image = fetchFallbackImage(fallback_file=fallbackFile, iotd_config=iotdConfig)
```

- [ ] **Step 7: Add `fallback_file` and `image_of_the_day` to `config/config.yaml`**

Find:

```yaml
url: "http://x.x.x.x"
```

Add after it:

```yaml
url: "http://x.x.x.x"
fallback_file: null          # Optional path to an image on disk
image_of_the_day:
  provider: null             # inaturalist | nasa_apod | null (disabled)
  nasa_apod_key: "DEMO_KEY"  # Only used when provider is nasa_apod
```

- [ ] **Step 8: Run both tests to confirm they pass**

```bash
cd /home/dwalsh/Development/pyInkDisplay && \
  python -m pytest \
    tests/test_py_ink_picture_frame.py::test_pyInkPictureFrame_uses_fallback_when_main_fetch_fails \
    tests/test_py_ink_picture_frame.py::test_pyInkPictureFrame_notifies_on_image_fetch_failure -v
```

Expected: both `PASSED`.

- [ ] **Step 9: Run the full test suite**

```bash
cd /home/dwalsh/Development/pyInkDisplay && python -m pytest -v
```

Expected: all tests `PASSED`.

- [ ] **Step 10: Commit**

```bash
cd /home/dwalsh/Development/pyInkDisplay && \
  git add pyinkdisplay/pyInkPictureFrame.py config/config.yaml \
          tests/test_py_ink_picture_frame.py && \
  git commit -m "feat: wire fetchFallbackImage into main cycle; add fallback_file and image_of_the_day config"
```
