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
import tenacity
import utils


@patch('utils.requests.get')
def testFetchImageFromUrlSuccess(mock_get):
    """Test successful image fetching."""
    mock_response = MagicMock()
    mock_response.raise_for_status.return_value = None
    mock_response.content = b'fake_image_data'
    mock_get.return_value = mock_response

    with patch('utils.Image.open') as mock_image_open:
        mock_image = MagicMock()
        mock_image_open.return_value = mock_image

        result = utils.fetchImageFromUrl('http://example.com/image.jpg')

        assert result == mock_image
        mock_get.assert_called_once_with('http://example.com/image.jpg', timeout=10)


@patch('utils.requests.get')
def testFetchImageFromUrlRequestException(mock_get):
    """Test handling of request exceptions."""
    mock_get.side_effect = requests.exceptions.RequestException("Network error")

    result = utils.fetchImageFromUrl('http://example.com/image.jpg')

    assert isinstance(result, Image.Image)
    # Should return default image on error


@patch('utils.requests.get')
def testFetchImageFromUrlImageOpenError(mock_get):
    """Test handling of image open errors."""
    mock_response = MagicMock()
    mock_response.raise_for_status.return_value = None
    mock_response.content = b'invalid_data'
    mock_get.return_value = mock_response

    with patch('utils.Image.open', side_effect=Exception("Invalid image")):
        result = utils.fetchImageFromUrl('http://example.com/image.jpg')

        assert isinstance(result, Image.Image)
        # Should return default image on error


def testCreateDefaultImage():
    """Test creation of default image."""
    image = utils._createDefaultImage()

    assert isinstance(image, Image.Image)
    assert image.mode == '1'  # 1-bit
    assert image.size == (800, 480)  # Default size