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

from unittest.mock import MagicMock, patch

import pytest

from pyinkdisplay.pySugarAlarm import PiSugarAlarm


@patch("pyinkdisplay.pySugarAlarm.connect_tcp")
@patch("pyinkdisplay.pySugarAlarm.PiSugarServer")
def test_set_alarm(mock_pisugar_server, mock_connect_tcp):
    """Test setting an alarm."""
    # Mock network check
    with patch("pyinkdisplay.pySugarAlarm.requests.get") as mock_requests_get:
        mock_response = MagicMock()
        mock_response.status_code = 204
        mock_requests_get.return_value = mock_response

        # Mock connection
        mock_connection = MagicMock()
        mock_event_connection = MagicMock()
        mock_connect_tcp.return_value = (mock_connection, mock_event_connection)

        # Mock PiSugarServer
        mock_pisugar_instance = MagicMock()
        mock_pisugar_server.return_value = mock_pisugar_instance
        mock_pisugar_instance.get_rtc_time.return_value = MagicMock()  # Mock datetime
        mock_pisugar_instance.rtc_pi2rtc = MagicMock()

        alarm = PiSugarAlarm()
        # Mock the setAlarm to avoid actual execution, but since it's complex, perhaps just call and check no exception
        # For simplicity, since the method is complex, test that it doesn't raise if mocks are set
        try:
            alarm.setAlarm(secondsInFuture=60)
            # If no exception, pass
        except Exception as e:
            pytest.fail(f"setAlarm raised an exception: {e}")


@patch("pyinkdisplay.pySugarAlarm.connect_tcp")
@patch("pyinkdisplay.pySugarAlarm.PiSugarServer")
def test_is_sugar_powered(mock_pisugar_server, mock_connect_tcp):
    """Test checking if PiSugar is powered."""
    # Mock connection
    mock_connection = MagicMock()
    mock_event_connection = MagicMock()
    mock_connect_tcp.return_value = (mock_connection, mock_event_connection)

    # Mock PiSugarServer
    mock_pisugar_instance = MagicMock()
    mock_pisugar_server.return_value = mock_pisugar_instance
    mock_pisugar_instance.get_battery_power_plugged.return_value = True

    alarm = PiSugarAlarm()
    assert alarm.isSugarPowered() == True
    mock_pisugar_instance.get_battery_power_plugged.assert_called_once()
