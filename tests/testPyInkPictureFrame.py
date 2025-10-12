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
from unittest.mock import patch, MagicMock, mock_open
import yaml
from pyInkPictureFrame import loadConfig, parseArguments, mergeArgsAndConfig, setupLogging


def test_load_config_success():
    """Test loading valid config."""
    config_data = {'epd': 'test', 'url': 'http://example.com'}
    mock_file = mock_open(read_data=yaml.dump(config_data))

    with patch('builtins.open', mock_file):
        result = loadConfig('config.yaml')

        assert result == config_data


def test_load_config_file_not_found():
    """Test handling of missing config file."""
    with patch('builtins.open', side_effect=FileNotFoundError):
        result = loadConfig('missing.yaml')

        assert result == {}


def test_load_config_invalid_yaml():
    """Test handling of invalid YAML."""
    with patch('builtins.open', mock_open(read_data='invalid: yaml: content: [')):
        result = loadConfig('config.yaml')

        assert result == {}


@patch('pyInkPictureFrame.argparse.ArgumentParser.parse_args')
def test_parse_arguments(mock_parse):
    """Test argument parsing."""
    mock_parse.return_value = MagicMock(epd='test', url='http://example.com', alarmMinutes=20, noShutdown=False, config=None)

    args = parseArguments()

    assert args.epd == 'test'


def test_merge_args_and_config():
    """Test merging args and config."""
    args = MagicMock(epd='arg_epd', url='arg_url', alarmMinutes=30, noShutdown=True, config=None, logging=None)
    config = {'epd': 'config_epd', 'url': 'config_url', 'alarmMinutes': 40, 'noShutdown': False, 'logging': {'type': 'console'}}

    result = mergeArgsAndConfig(args, config)

    # Args should take precedence
    assert result['epd'] == 'arg_epd'
    assert result['alarmMinutes'] == 30
    assert result['noShutdown'] == True


@patch('pyInkPictureFrame.logging.basicConfig')
def test_setup_logging_console(mock_basic):
    """Test console logging setup."""
    setupLogging({'type': 'console'})

    mock_basic.assert_called_once()


@patch('pyInkPictureFrame.logging.basicConfig')
def test_setup_logging_default(mock_basic):
    """Test default logging setup."""
    setupLogging(None)

    mock_basic.assert_called_once()