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
        # Mock the setAlarm to avoid actual execution.
        # Since it's complex, just call and check no exception.
        # For simplicity, test that it doesn't raise if mocks are set.
        try:
            alarm.setAlarm(secondsInFuture=60)
            # If no exception, pass
        except Exception as e:
            pytest.fail(f"setAlarm raised an exception: {e}")


@patch("pyinkdisplay.pySugarAlarm.connect_tcp")
@patch("pyinkdisplay.pySugarAlarm.PiSugarServer")
def test_set_alarm_does_not_block_on_network(mock_pisugar_server, mock_connect_tcp):
    """setAlarm must not wait for network connectivity.

    rtc_alarm_set is a local socket call to pisugar-server. If the device
    wakes with no internet, a `while not _isOnline(): sleep(5)` loop would
    leave the Pi powered on indefinitely and drain the battery.
    """
    # Mock connection
    mock_connection = MagicMock()
    mock_event_connection = MagicMock()
    mock_connect_tcp.return_value = (mock_connection, mock_event_connection)

    # Mock PiSugarServer — RTC calls succeed, alarm-set succeeds
    mock_pisugar_instance = MagicMock()
    mock_pisugar_server.return_value = mock_pisugar_instance
    mock_pisugar_instance.get_rtc_time.return_value = MagicMock()
    mock_pisugar_instance.rtc_pi2rtc = MagicMock()

    alarm = PiSugarAlarm()

    # Patch _isOnline to always return False — if setAlarm consults it, the
    # old code would loop forever. We assert it is never called.
    with patch.object(PiSugarAlarm, "_isOnline", return_value=False) as mock_online:
        alarm.setAlarm(secondsInFuture=60)

    mock_online.assert_not_called()
    mock_pisugar_instance.rtc_alarm_set.assert_called_once()


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
    assert alarm.isSugarPowered() is True
    mock_pisugar_instance.get_battery_power_plugged.assert_called_once()


@patch("pyinkdisplay.pySugarAlarm.connect_tcp")
@patch("pyinkdisplay.pySugarAlarm.PiSugarServer")
def test_sync_rtc_skips_write_when_system_clock_is_bad(
    mock_pisugar_server, mock_connect_tcp
):
    """_syncRtc must not write Pi time to RTC when system clock year < 2024.

    On first boot before NTP sync, datetime.now() may return epoch or
    last-shutdown time. Writing that bad time to the RTC corrupts the alarm.
    """
    from datetime import datetime

    mock_connection = MagicMock()
    mock_event_connection = MagicMock()
    mock_connect_tcp.return_value = (mock_connection, mock_event_connection)

    mock_pisugar_instance = MagicMock()
    mock_pisugar_server.return_value = mock_pisugar_instance
    # get_rtc_time is called after sync — return a plausible RTC datetime
    mock_pisugar_instance.get_rtc_time.return_value = datetime(2025, 1, 1, 8, 0, 0)

    alarm = PiSugarAlarm()
    alarm._ensurePiSugarConnection()

    bad_time = datetime(2000, 1, 1, 0, 0, 0)  # year < 2024 — pre-NTP epoch time
    with patch("pyinkdisplay.pySugarAlarm.datetime") as mock_dt:
        mock_dt.now.return_value = bad_time
        alarm._syncRtc(bad_time)

    # rtc_pi2rtc must NOT have been called — bad Pi time must not reach the RTC
    mock_pisugar_instance.rtc_pi2rtc.assert_not_called()
