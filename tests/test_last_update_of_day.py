"""
MIT License

Copyright (c) 2026 Velotales

Unit tests for last-update-of-day image selection in pyInkPictureFrame.
"""

from datetime import datetime

from pyinkdisplay.pyInkPictureFrame import isLastUpdateBeforeQuietHours

QUIET = {"start": "22:00", "end": "07:00"}


def test_update_whose_next_wake_lands_in_quiet_window_is_the_last():
    """21:00 + 120 min = 23:00, inside the window, so this is the last update."""
    now = datetime(2026, 5, 1, 21, 0)
    assert isLastUpdateBeforeQuietHours(now, 120, QUIET) is True


def test_update_whose_next_wake_is_still_before_quiet_is_not_the_last():
    """18:00 + 120 min = 20:00, still outside the window, so more updates follow."""
    now = datetime(2026, 5, 1, 18, 0)
    assert isLastUpdateBeforeQuietHours(now, 120, QUIET) is False


def test_next_wake_landing_exactly_on_quiet_start_is_the_last():
    """20:00 + 120 min = 22:00 exactly, which isInQuietHours treats as inside."""
    now = datetime(2026, 5, 1, 20, 0)
    assert isLastUpdateBeforeQuietHours(now, 120, QUIET) is True


def test_inside_quiet_hours_is_never_the_last_update():
    """No update happens during quiet hours, so the question does not arise."""
    now = datetime(2026, 5, 1, 23, 0)
    assert isLastUpdateBeforeQuietHours(now, 120, QUIET) is False


def test_no_quiet_config_disables_the_feature():
    """Without quiet hours there is no end of day to detect."""
    now = datetime(2026, 5, 1, 21, 0)
    assert isLastUpdateBeforeQuietHours(now, 120, None) is False


def test_interval_spanning_the_whole_window_still_counts_as_last():
    """A 12h interval from 21:00 lands at 09:00, past the window entirely."""
    now = datetime(2026, 5, 1, 21, 0)
    assert isLastUpdateBeforeQuietHours(now, 720, QUIET) is True


def test_same_day_quiet_window_is_supported():
    """01:00 + 120 min = 03:00, inside a same-day 02:00-06:00 window."""
    now = datetime(2026, 5, 1, 1, 0)
    assert (
        isLastUpdateBeforeQuietHours(now, 120, {"start": "02:00", "end": "06:00"})
        is True
    )


# --- continuousEpdUpdateLoop image source selection ---


def _runLoopOnce(**patches):
    """Run one iteration of the loop, then exit via a power-loss return."""
    from unittest.mock import MagicMock, patch

    from pyinkdisplay.pyInkPictureFrame import continuousEpdUpdateLoop

    mock_alarm = MagicMock()
    mock_alarm.isSugarPowered.return_value = False  # ends the loop after one pass
    mock_display = MagicMock()
    with (
        patch("pyinkdisplay.pyInkPictureFrame.isInQuietHours", return_value=False),
        patch("pyinkdisplay.pyInkPictureFrame.resetBootCounter"),
        patch("pyinkdisplay.pyInkPictureFrame.time.sleep"),
        patch(
            "pyinkdisplay.pyInkPictureFrame.isLastUpdateBeforeQuietHours",
            return_value=patches["is_last"],
        ),
        patch(
            "pyinkdisplay.pyInkPictureFrame.fetchImageOfTheDay",
            return_value=patches["photo"],
        ) as mock_iotd,
        patch(
            "pyinkdisplay.pyInkPictureFrame.fetchImageFromUrl",
            return_value=patches["dashboard"],
        ) as mock_url,
    ):
        continuousEpdUpdateLoop(
            mock_display,
            mock_alarm,
            "http://example.com",
            alarmMinutes=0,
            quietConfig=QUIET,
            iotdConfig={"provider": "nasa_apod"},
        )
    return mock_display, mock_iotd, mock_url


def test_last_update_of_day_displays_the_image_of_the_day():
    """The overnight image comes from the photo provider, not the dashboard."""
    photo = object()
    display, mock_iotd, mock_url = _runLoopOnce(
        is_last=True, photo=photo, dashboard=object()
    )
    mock_iotd.assert_called_once()
    mock_url.assert_not_called()
    display.displayImage.assert_called_once_with(photo)


def test_ordinary_update_still_displays_the_dashboard():
    """Every update that is not the last of the day keeps using the URL."""
    dashboard = object()
    display, mock_iotd, mock_url = _runLoopOnce(
        is_last=False, photo=object(), dashboard=dashboard
    )
    mock_iotd.assert_not_called()
    mock_url.assert_called_once()
    display.displayImage.assert_called_once_with(dashboard)


def test_failed_photo_fetch_falls_back_to_the_dashboard():
    """A dead photo provider must not leave the panel blank all night."""
    dashboard = object()
    display, mock_iotd, mock_url = _runLoopOnce(
        is_last=True, photo=None, dashboard=dashboard
    )
    mock_iotd.assert_called_once()
    mock_url.assert_called_once()
    display.displayImage.assert_called_once_with(dashboard)


# --- one-shot battery path ---


def test_battery_last_update_of_day_displays_the_image_of_the_day():
    """The battery one-shot path must pick the photo for the overnight image too."""
    from unittest.mock import MagicMock, patch

    from pyinkdisplay.pyInkPictureFrame import pyInkPictureFrame

    mock_alarm = MagicMock()
    mock_alarm.isSugarPowered.return_value = False  # battery
    photo = object()

    with (
        patch("pyinkdisplay.pyInkPictureFrame.parseArguments") as mock_args,
        patch(
            "pyinkdisplay.pyInkPictureFrame.loadConfig",
            return_value={
                "quiet_hours": QUIET,
                "image_of_the_day": {"provider": "nasa_apod"},
            },
        ),
        patch(
            "pyinkdisplay.pyInkPictureFrame.mergeArgsAndConfig",
            return_value={
                "epd": "waveshare_epd.epd7in3f",
                "url": "http://example.com",
                "alarmMinutes": 120,
                "noShutdown": False,
                "logging": None,
            },
        ),
        patch("pyinkdisplay.pyInkPictureFrame.setupLogging"),
        patch("pyinkdisplay.pyInkPictureFrame.PyInkDisplay") as mock_display_cls,
        patch("pyinkdisplay.pyInkPictureFrame.PiSugarAlarm", return_value=mock_alarm),
        patch("pyinkdisplay.pyInkPictureFrame.isInQuietHours", return_value=False),
        patch(
            "pyinkdisplay.pyInkPictureFrame.isLastUpdateBeforeQuietHours",
            return_value=True,
        ),
        patch(
            "pyinkdisplay.pyInkPictureFrame.fetchImageOfTheDay", return_value=photo
        ) as mock_iotd,
        patch("pyinkdisplay.pyInkPictureFrame.fetchImageFromUrl") as mock_url,
        patch("pyinkdisplay.pyInkPictureFrame.getCurrentTag", return_value="v0.4.6"),
        patch("pyinkdisplay.pyInkPictureFrame.recordBootAttempt", return_value=False),
        patch("pyinkdisplay.pyInkPictureFrame.resetBootCounter"),
        patch("pyinkdisplay.pyInkPictureFrame.time.sleep"),
        patch("pyinkdisplay.pyInkPictureFrame.subprocess.run"),
    ):
        mock_args.return_value.config = "config.yaml"
        pyInkPictureFrame()

    mock_iotd.assert_called_once()
    mock_url.assert_not_called()
    mock_display_cls.return_value.displayImage.assert_called_once_with(photo)
