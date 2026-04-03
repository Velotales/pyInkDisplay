"""Unit tests for pyImageOfTheDay.py"""

from unittest.mock import MagicMock, patch

import requests as req

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
    with patch(
        "pyinkdisplay.pyImageOfTheDay._fetchInaturalistImage", return_value=mock_image
    ) as mock_fetch:
        result = iotd.fetchImageOfTheDay({"provider": "inaturalist"})
    mock_fetch.assert_called_once()
    assert result == mock_image


def test_fetchImageOfTheDay_dispatches_to_nasa_apod():
    """Calls _fetchNasaApodImage when provider is 'nasa_apod'."""
    mock_image = MagicMock()
    with patch(
        "pyinkdisplay.pyImageOfTheDay._fetchNasaApodImage", return_value=mock_image
    ) as mock_fetch:
        result = iotd.fetchImageOfTheDay(
            {"provider": "nasa_apod", "nasa_apod_key": "ABC123"}
        )
    mock_fetch.assert_called_once_with("ABC123")
    assert result == mock_image


def test_fetchImageOfTheDay_nasa_apod_uses_demo_key_when_not_configured():
    """Uses DEMO_KEY when nasa_apod_key is absent from config."""
    with patch(
        "pyinkdisplay.pyImageOfTheDay._fetchNasaApodImage", return_value=None
    ) as mock_fetch:
        iotd.fetchImageOfTheDay({"provider": "nasa_apod"})
    mock_fetch.assert_called_once_with("DEMO_KEY")


def test_fetchImageOfTheDay_unknown_provider_returns_none():
    """Returns None (with a warning) for unknown provider names."""
    result = iotd.fetchImageOfTheDay({"provider": "unknown_source"})
    assert result is None


def test_fetchInaturalistImage_returns_image_on_success():
    """Returns an image when iNaturalist returns a valid observation."""
    mock_api_response = MagicMock()
    mock_api_response.raise_for_status = MagicMock()
    mock_api_response.json.return_value = {
        "results": [
            {"photos": [{"url": "https://inaturalist.org/photos/1/square.jpg"}]}
        ]
    }
    mock_image = MagicMock()

    with patch(
        "pyinkdisplay.pyImageOfTheDay.requests.get", return_value=mock_api_response
    ), patch(
        "pyinkdisplay.pyImageOfTheDay.fetchImageFromUrl", return_value=mock_image
    ) as mock_fetch:
        result = iotd._fetchInaturalistImage()

    mock_fetch.assert_called_once_with("https://inaturalist.org/photos/1/large.jpg")
    assert result == mock_image


def test_fetchInaturalistImage_returns_none_on_empty_results():
    """Returns None when iNaturalist returns no observations."""
    mock_api_response = MagicMock()
    mock_api_response.raise_for_status = MagicMock()
    mock_api_response.json.return_value = {"results": []}

    with patch(
        "pyinkdisplay.pyImageOfTheDay.requests.get", return_value=mock_api_response
    ):
        result = iotd._fetchInaturalistImage()

    assert result is None


def test_fetchInaturalistImage_returns_none_when_photos_list_is_empty():
    """Returns None when observation has an empty photos list."""
    mock_api_response = MagicMock()
    mock_api_response.raise_for_status = MagicMock()
    mock_api_response.json.return_value = {"results": [{"photos": []}]}

    with patch(
        "pyinkdisplay.pyImageOfTheDay.requests.get", return_value=mock_api_response
    ):
        result = iotd._fetchInaturalistImage()

    assert result is None


def test_fetchInaturalistImage_returns_none_on_api_error():
    """Returns None when the iNaturalist API call raises."""
    with patch(
        "pyinkdisplay.pyImageOfTheDay.requests.get",
        side_effect=req.exceptions.ConnectionError("refused"),
    ):
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

    with patch(
        "pyinkdisplay.pyImageOfTheDay.requests.get", return_value=mock_api_response
    ), patch(
        "pyinkdisplay.pyImageOfTheDay.fetchImageFromUrl", return_value=mock_image
    ) as mock_fetch:
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

    with patch(
        "pyinkdisplay.pyImageOfTheDay.requests.get", return_value=mock_api_response
    ):
        result = iotd._fetchNasaApodImage("DEMO_KEY")

    assert result is None


def test_fetchNasaApodImage_returns_none_on_api_error():
    """Returns None when the NASA APOD API call raises."""
    with patch(
        "pyinkdisplay.pyImageOfTheDay.requests.get",
        side_effect=req.exceptions.ConnectionError("refused"),
    ):
        result = iotd._fetchNasaApodImage("DEMO_KEY")

    assert result is None
