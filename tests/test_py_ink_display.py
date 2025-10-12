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


@patch('omni_epd.displayfactory.load_display_driver')
def test_load_display_driver_success(mock_load):
    """Test successful display driver loading."""
    mock_epd = MagicMock()
    mock_load.return_value = mock_epd

    display = PyInkDisplay()
    display.loadDisplayDriver('test_driver')

    mock_load.assert_called_once_with('test_driver')
    assert display.epd == mock_epd


@patch('omni_epd.displayfactory.load_display_driver')
def test_load_display_driver_not_found(mock_load):
    """Test handling of EPD not found."""
    mock_load.side_effect = EPDNotFoundError("Driver not found")

    display = PyInkDisplay()

    with pytest.raises(EPDNotFoundError):
        display.loadDisplayDriver('invalid_driver')


@patch('omni_epd.displayfactory.load_display_driver')
def test_load_display_driver_general_error(mock_load):
    """Test handling of general errors in display driver loading."""
    mock_load.side_effect = Exception("General error")

    display = PyInkDisplay()

    with pytest.raises(Exception):
        display.loadDisplayDriver('test_driver')


def test_display_image_success():
    """Test successful image display."""
    display = PyInkDisplay()
    display.epd = MagicMock()
    display.epd.width = 100
    display.epd.height = 100

    image = Image.new('RGB', (100, 100))

    display.displayImage(image)

    display.epd.prepare.assert_called_once()
    display.epd.clear.assert_called_once()
    display.epd.display.assert_called_once_with(image)


def test_display_image_no_epd():
    """Test display image without loaded EPD."""
    display = PyInkDisplay()

    image = Image.new('RGB', (100, 100))

    with pytest.raises(RuntimeError, match="EPD driver not loaded"):
        display.displayImage(image)


def test_display_image_resize_error():
    """Test handling of resize errors."""
    display = PyInkDisplay()
    display.epd = MagicMock()

    image = Image.new('RGB', (100, 100))
    image.resize = MagicMock(side_effect=Exception("Resize error"))

    display.displayImage(image)

    # Since resize fails, the rest shouldn't be called
    display.epd.prepare.assert_not_called()
    display.epd.clear.assert_not_called()
    display.epd.display.assert_not_called()