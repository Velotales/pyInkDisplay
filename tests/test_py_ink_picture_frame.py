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

Unit tests for pyInkPictureFrame.py
"""

import pytest
from unittest.mock import patch, MagicMock
from pyinkdisplay.pyInkPictureFrame import (
    loadConfig,
    parseArguments,
    mergeArgsAndConfig,
    setupLogging,
)


def test_loadConfig_success():
    """Test loading config from YAML file."""
    with patch("builtins.open") as mock_open, patch(
        "pyinkdisplay.pyInkPictureFrame.yaml.safe_load"
    ) as mock_yaml_load:
        mock_yaml_load.return_value = {"key": "value"}

        result = loadConfig("config.yaml")

        assert result == {"key": "value"}


def test_loadConfig_file_not_found():
    """Test loading config when file is not found."""
    with patch("builtins.open", side_effect=FileNotFoundError):
        result = loadConfig("missing.yaml")

        assert result == {}


def test_parseArguments():
    """Test parsing command line arguments."""
    with patch("pyinkdisplay.pyInkPictureFrame.argparse.ArgumentParser") as mock_parser:
        mock_args = MagicMock()
        mock_parser.return_value.parse_args.return_value = mock_args

        result = parseArguments()

        assert result == mock_args


def test_mergeArgsAndConfig():
    """Test merging arguments and config."""
    args = MagicMock()
    args.url = "http://example.com"
    args.alarmMinutes = 60  # Use correct argument name
    args.epd = None
    args.noShutdown = None

    config = {"url": "default.com", "alarmMinutes": 30}

    result = mergeArgsAndConfig(args, config)

    assert result["url"] == "http://example.com"  # Args take precedence
    assert result["alarmMinutes"] == 60  # Correct key


def test_setupLogging():
    """Test setting up logging."""
    with patch("pyinkdisplay.pyInkPictureFrame.logging.basicConfig") as mock_basic_config:
        setupLogging({"level": "INFO"})

        mock_basic_config.assert_called_once()
