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

Unit tests for pySugarAlarm.py
"""

import pytest
from unittest.mock import patch, MagicMock
from pySugarAlarm import PiSugarAlarm


@patch('pySugarAlarm.PiSugar')
def testInit(mock_pisugar):
    """Test PiSugarAlarm initialization."""
    alarm = PiSugarAlarm()

    mock_pisugar.assert_called_once()


@patch('pySugarAlarm.PiSugar')
def testSetAlarm(mock_pisugar):
    """Test setting an alarm."""
    mock_instance = MagicMock()
    mock_pisugar.return_value = mock_instance

    alarm = PiSugarAlarm()
    alarm.setAlarm(secondsInFuture=60)

    mock_instance.set_alarm.assert_called_once_with(60)


@patch('pySugarAlarm.PiSugar')
def testIsSugarPowered(mock_pisugar):
    """Test checking if PiSugar is powered."""
    mock_instance = MagicMock()
    mock_instance.get_power_status.return_value = True
    mock_pisugar.return_value = mock_instance

    alarm = PiSugarAlarm()

    assert alarm.isSugarPowered() == True
    mock_instance.get_power_status.assert_called_once()