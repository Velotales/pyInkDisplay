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

Unit tests for pyInkDisplay.py
"""

import pytest
from unittest.mock import patch, MagicMock
from PIL import Image
from pyInkDisplay import PyInkDisplay, EPDNotFoundError


@patch('pyInkDisplay.displayfactory.load_display_driver')
def testLoadDisplayDriverSuccess(mock_load):
    """Test successful display driver loading."""
    mock_epd = MagicMock()
    mock_load.return_value = mock_epd

    display = PyInkDisplay()
    display.loadDisplayDriver('test_driver')

    mock_load.assert_called_once_with('test_driver')
    assert display.epd == mock_epd


@patch('pyInkDisplay.displayfactory.load_display_driver')
def testLoadDisplayDriverNotFound(mock_load):
    """Test handling of EPD not found."""
    mock_load.side_effect = EPDNotFoundError("Driver not found")

    display = PyInkDisplay()

    with pytest.raises(EPDNotFoundError):
        display.loadDisplayDriver('invalid_driver')


@patch('pyInkDisplay.displayfactory.load_display_driver')
def testLoadDisplayDriverGeneralError(mock_load):
    """Test handling of general errors in display driver loading."""
    mock_load.side_effect = Exception("General error")

    display = PyInkDisplay()

    with pytest.raises(Exception):
        display.loadDisplayDriver('test_driver')


@patch.object(PyInkDisplay, 'epd', new_callable=MagicMock)
def testDisplayImageSuccess(mock_epd):
    """Test successful image display."""
    display = PyInkDisplay()
    display.epd = mock_epd

    image = Image.new('RGB', (100, 100))

    display.displayImage(image)

    mock_epd.prepare.assert_called_once()
    mock_epd.clear.assert_called_once()
    mock_epd.display.assert_called_once_with(image)


def testDisplayImageNoEpd():
    """Test display image without loaded EPD."""
    display = PyInkDisplay()

    image = Image.new('RGB', (100, 100))

    with pytest.raises(RuntimeError, match="EPD driver not loaded"):
        display.displayImage(image)


@patch.object(PyInkDisplay, 'epd', new_callable=MagicMock)
def testDisplayImageResizeError(mock_epd):
    """Test handling of resize errors."""
    display = PyInkDisplay()
    display.epd = mock_epd

    image = Image.new('RGB', (100, 100))
    image.resize = MagicMock(side_effect=Exception("Resize error"))

    # Should not raise, just log
    display.displayImage(image)


@patch.object(PyInkDisplay, 'epd', new_callable=MagicMock)
def testCloseDisplay(mock_epd):
    """Test closing the display."""
    display = PyInkDisplay()
    display.epd = mock_epd

    display.closeDisplay()

    mock_epd.close.assert_called_once()


def testCloseDisplayNoEpd():
    """Test closing display when none is loaded."""
    display = PyInkDisplay()

    # Should not raise
    display.closeDisplay()


@patch('pyInkDisplay.fetchImageFromUrl')
def testFetchImageFromUrlWrapper(mock_fetch):
    """Test the wrapper method for fetching images."""
    mock_image = MagicMock()
    mock_fetch.return_value = mock_image

    display = PyInkDisplay()

    result = display.fetchImageFromUrl('http://example.com/image.jpg')

    assert result == mock_image
    mock_fetch.assert_called_once_with('http://example.com/image.jpg')