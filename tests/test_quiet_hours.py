"""
MIT License

Copyright (c) 2026 Velotales

Unit tests for quiet hours logic in pyInkPictureFrame.
"""

from datetime import datetime
from unittest.mock import MagicMock, patch

from pyinkdisplay.pyInkPictureFrame import (
    isInQuietHours,
    pyInkPictureFrame,
    secondsUntilQuietEnd,
)

# --- isInQuietHours ---


def test_isInQuietHours_before_midnight_is_inside_window():
    """22:30 is inside a 22:00-07:00 quiet window."""
    now = datetime(2026, 5, 1, 22, 30)
    assert isInQuietHours(now, {"start": "22:00", "end": "07:00"}) is True


def test_isInQuietHours_after_midnight_is_inside_window():
    """02:00 is inside a 22:00-07:00 quiet window."""
    now = datetime(2026, 5, 1, 2, 0)
    assert isInQuietHours(now, {"start": "22:00", "end": "07:00"}) is True


def test_isInQuietHours_midday_is_outside_window():
    """12:00 is outside a 22:00-07:00 quiet window."""
    now = datetime(2026, 5, 1, 12, 0)
    assert isInQuietHours(now, {"start": "22:00", "end": "07:00"}) is False


def test_isInQuietHours_exactly_at_start_is_inside():
    """22:00 exactly is inside the quiet window."""
    now = datetime(2026, 5, 1, 22, 0)
    assert isInQuietHours(now, {"start": "22:00", "end": "07:00"}) is True


def test_isInQuietHours_exactly_at_end_is_outside():
    """07:00 exactly is outside (end is exclusive)."""
    now = datetime(2026, 5, 1, 7, 0)
    assert isInQuietHours(now, {"start": "22:00", "end": "07:00"}) is False


def test_isInQuietHours_same_day_window():
    """03:00 is inside a same-day 02:00-06:00 quiet window."""
    now = datetime(2026, 5, 1, 3, 0)
    assert isInQuietHours(now, {"start": "02:00", "end": "06:00"}) is True


def test_isInQuietHours_outside_same_day_window():
    """08:00 is outside a same-day 02:00-06:00 quiet window."""
    now = datetime(2026, 5, 1, 8, 0)
    assert isInQuietHours(now, {"start": "02:00", "end": "06:00"}) is False


def test_isInQuietHours_no_config_returns_false():
    """None config always returns False."""
    now = datetime(2026, 5, 1, 22, 30)
    assert isInQuietHours(now, None) is False


# --- secondsUntilQuietEnd ---


def test_secondsUntilQuietEnd_after_midnight():
    """At 02:00, returns 5 hours (18000s) until 07:00."""
    now = datetime(2026, 5, 1, 2, 0, 0)
    result = secondsUntilQuietEnd(now, {"start": "22:00", "end": "07:00"})
    assert result == 5 * 3600


def test_secondsUntilQuietEnd_before_midnight():
    """At 22:30, returns 8.5 hours (30600s) until 07:00 next day."""
    now = datetime(2026, 5, 1, 22, 30, 0)
    result = secondsUntilQuietEnd(now, {"start": "22:00", "end": "07:00"})
    assert result == 8 * 3600 + 30 * 60


# --- integration: skip display during quiet hours ---


def test_pyInkPictureFrame_quiet_hours_usb_sleeps_then_restarts():
    """On USB power during quiet hours: sleep in-process, then restart service when done."""
    mock_alarm = MagicMock()
    mock_alarm.isSugarPowered.return_value = True  # USB

    with patch("pyinkdisplay.pyInkPictureFrame.parseArguments") as mock_args, patch(
        "pyinkdisplay.pyInkPictureFrame.loadConfig",
        return_value={"quiet_hours": {"start": "22:00", "end": "07:00"}},
    ), patch(
        "pyinkdisplay.pyInkPictureFrame.mergeArgsAndConfig",
        return_value={
            "epd": "waveshare_epd.epd7in3f",
            "url": "http://example.com",
            "alarmMinutes": 120,
            "noShutdown": False,
            "logging": None,
        },
    ), patch(
        "pyinkdisplay.pyInkPictureFrame.setupLogging"
    ), patch(
        "pyinkdisplay.pyInkPictureFrame.PyInkDisplay"
    ), patch(
        "pyinkdisplay.pyInkPictureFrame.PiSugarAlarm", return_value=mock_alarm
    ), patch(
        "pyinkdisplay.pyInkPictureFrame.fetchImageFromUrl"
    ) as mock_fetch, patch(
        "pyinkdisplay.pyInkPictureFrame.isInQuietHours", return_value=True
    ), patch(
        "pyinkdisplay.pyInkPictureFrame.secondsUntilQuietEnd", return_value=28800
    ), patch(
        "pyinkdisplay.pyInkPictureFrame.getCurrentTag", return_value="v0.3.6"
    ), patch(
        "pyinkdisplay.pyInkPictureFrame.time.sleep"
    ) as mock_sleep, patch(
        "pyinkdisplay.pyInkPictureFrame.subprocess.run"
    ) as mock_run, patch(
        "pyinkdisplay.pyInkPictureFrame.restartService"
    ) as mock_restart:

        mock_args.return_value.config = "config.yaml"
        pyInkPictureFrame()

    mock_fetch.assert_not_called()
    mock_alarm.setAlarm.assert_not_called()
    mock_sleep.assert_called_once_with(28800)
    mock_run.assert_not_called()
    mock_restart.assert_called_once()


def test_pyInkPictureFrame_quiet_hours_battery_shuts_down():
    """On battery during quiet hours: set alarm and shut down immediately."""
    mock_alarm = MagicMock()
    mock_alarm.isSugarPowered.return_value = False  # battery

    with patch("pyinkdisplay.pyInkPictureFrame.parseArguments") as mock_args, patch(
        "pyinkdisplay.pyInkPictureFrame.loadConfig",
        return_value={"quiet_hours": {"start": "22:00", "end": "07:00"}},
    ), patch(
        "pyinkdisplay.pyInkPictureFrame.mergeArgsAndConfig",
        return_value={
            "epd": "waveshare_epd.epd7in3f",
            "url": "http://example.com",
            "alarmMinutes": 120,
            "noShutdown": False,
            "logging": None,
        },
    ), patch(
        "pyinkdisplay.pyInkPictureFrame.setupLogging"
    ), patch(
        "pyinkdisplay.pyInkPictureFrame.PyInkDisplay"
    ), patch(
        "pyinkdisplay.pyInkPictureFrame.PiSugarAlarm", return_value=mock_alarm
    ), patch(
        "pyinkdisplay.pyInkPictureFrame.fetchImageFromUrl"
    ) as mock_fetch, patch(
        "pyinkdisplay.pyInkPictureFrame.isInQuietHours", return_value=True
    ), patch(
        "pyinkdisplay.pyInkPictureFrame.secondsUntilQuietEnd", return_value=28800
    ), patch(
        "pyinkdisplay.pyInkPictureFrame.getCurrentTag", return_value="v0.3.6"
    ), patch(
        "pyinkdisplay.pyInkPictureFrame.time.sleep"
    ) as mock_sleep, patch(
        "pyinkdisplay.pyInkPictureFrame.subprocess.run"
    ) as mock_run:

        mock_args.return_value.config = "config.yaml"
        pyInkPictureFrame()

    mock_fetch.assert_not_called()
    mock_alarm.setAlarm.assert_called_once_with(secondsInFuture=28800)
    mock_run.assert_called_once_with(["sudo", "shutdown", "now"], check=True)
    mock_sleep.assert_not_called()


def test_pyInkPictureFrame_quiet_hours_no_shutdown_flag_skips_sleep_and_shutdown():
    """noShutdown=True suppresses both shutdown and in-process sleep (dev mode)."""
    mock_alarm = MagicMock()
    mock_alarm.isSugarPowered.return_value = True  # USB

    with patch("pyinkdisplay.pyInkPictureFrame.parseArguments") as mock_args, patch(
        "pyinkdisplay.pyInkPictureFrame.loadConfig",
        return_value={"quiet_hours": {"start": "22:00", "end": "07:00"}},
    ), patch(
        "pyinkdisplay.pyInkPictureFrame.mergeArgsAndConfig",
        return_value={
            "epd": "waveshare_epd.epd7in3f",
            "url": "http://example.com",
            "alarmMinutes": 120,
            "noShutdown": True,
            "logging": None,
        },
    ), patch(
        "pyinkdisplay.pyInkPictureFrame.setupLogging"
    ), patch(
        "pyinkdisplay.pyInkPictureFrame.PyInkDisplay"
    ), patch(
        "pyinkdisplay.pyInkPictureFrame.PiSugarAlarm", return_value=mock_alarm
    ), patch(
        "pyinkdisplay.pyInkPictureFrame.fetchImageFromUrl"
    ) as mock_fetch, patch(
        "pyinkdisplay.pyInkPictureFrame.isInQuietHours", return_value=True
    ), patch(
        "pyinkdisplay.pyInkPictureFrame.secondsUntilQuietEnd", return_value=28800
    ), patch(
        "pyinkdisplay.pyInkPictureFrame.getCurrentTag", return_value="v0.3.6"
    ), patch(
        "pyinkdisplay.pyInkPictureFrame.time.sleep"
    ) as mock_sleep, patch(
        "pyinkdisplay.pyInkPictureFrame.subprocess.run"
    ) as mock_run:

        mock_args.return_value.config = "config.yaml"
        pyInkPictureFrame()

    mock_fetch.assert_not_called()
    mock_alarm.setAlarm.assert_not_called()
    mock_sleep.assert_not_called()
    mock_run.assert_not_called()
