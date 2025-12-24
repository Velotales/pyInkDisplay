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

Unit tests for utils.py
"""

import pytest
from unittest.mock import patch, MagicMock

from PIL import Image
import pyinkdisplay.utils as utils


def test_fetchImageFromUrl_success():
    """Test successful image download from URL."""
    with patch("pyinkdisplay.utils.requests.get") as mock_get, patch(
        "pyinkdisplay.utils.BytesIO"
    ) as mock_bytesio, patch("pyinkdisplay.utils.Image.open") as mock_image_open:
        mock_response = MagicMock()
        mock_response.content = b"fake image data"
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        mock_bytesio_instance = MagicMock()
        mock_bytesio.return_value = mock_bytesio_instance

        mock_image = MagicMock()
        mock_image_open.return_value = mock_image

        result = utils.fetchImageFromUrl("http://example.com/image.jpg")

        mock_get.assert_called_once_with("http://example.com/image.jpg", timeout=10)
        mock_response.raise_for_status.assert_called_once()
        mock_bytesio.assert_called_once_with(b"fake image data")
        mock_image_open.assert_called_once_with(mock_bytesio_instance)
        assert result == mock_image


def test_fetchImageFromUrl_failure():
    """Test failure in image download, returns default image."""
    with patch("pyinkdisplay.utils.requests.get") as mock_get, patch(
        "pyinkdisplay.utils._createDefaultImage"
    ) as mock_default:
        mock_get.side_effect = Exception("Network error")

        mock_default_image = MagicMock()
        mock_default.return_value = mock_default_image

        result = utils.fetchImageFromUrl("http://example.com/image.jpg")

        assert result == mock_default_image
        mock_default.assert_called_once()


def test_createDefaultImage():
    """Test creating a default fallback image."""
    with patch("pyinkdisplay.utils.Image.new") as mock_image_new, patch(
        "pyinkdisplay.utils.ImageDraw.Draw"
    ) as mock_draw:
        mock_image = MagicMock()
        mock_image_new.return_value = mock_image

        mock_draw_instance = MagicMock()
        mock_draw.return_value = mock_draw_instance

        result = utils._createDefaultImage(800, 480)

        mock_image_new.assert_called_once_with("1", (800, 480), 0)
        mock_draw.assert_called_once_with(mock_image)
        mock_draw_instance.text.assert_called_once()
        assert result == mock_image
