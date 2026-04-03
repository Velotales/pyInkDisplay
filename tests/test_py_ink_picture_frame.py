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

from unittest.mock import MagicMock, patch

from pyinkdisplay.pyInkPictureFrame import (
    loadConfig,
    mergeArgsAndConfig,
    parseArguments,
    pyInkPictureFrame,
    runBatteryMode,
)


def test_loadConfig_success():
    """Test loading config from YAML file."""
    with patch("builtins.open"), patch(
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


def test_runBatteryMode_sets_alarm_and_shuts_down():
    """Battery mode sets alarm, publishes battery, and shuts down."""
    alarm = MagicMock()

    with patch("pyinkdisplay.pyInkPictureFrame.subprocess.run") as mock_run, \
         patch("pyinkdisplay.pyInkPictureFrame.publishBatteryLevel") as mock_pub:
        runBatteryMode(alarm, alarmMinutes=20, mqttConfig={"host": "localhost"}, noShutdown=False)

    alarm.setAlarm.assert_called_once_with(secondsInFuture=1200)
    mock_pub.assert_called_once_with(alarm, {"host": "localhost"})
    mock_run.assert_called_once_with(["sudo", "shutdown", "now"], check=True)


def test_runBatteryMode_no_shutdown_when_flag_set():
    """Battery mode skips shutdown when noShutdown=True."""
    alarm = MagicMock()

    with patch("pyinkdisplay.pyInkPictureFrame.subprocess.run") as mock_run, \
         patch("pyinkdisplay.pyInkPictureFrame.publishBatteryLevel"):
        runBatteryMode(alarm, alarmMinutes=20, mqttConfig=None, noShutdown=True)

    mock_run.assert_not_called()


def test_pyInkPictureFrame_calls_runBatteryMode_when_not_powered():
    """Main function calls runBatteryMode when PiSugar is not on mains power."""
    with patch("pyinkdisplay.pyInkPictureFrame.parseArguments") as mock_args, \
         patch("pyinkdisplay.pyInkPictureFrame.loadConfig", return_value={}), \
         patch("pyinkdisplay.pyInkPictureFrame.mergeArgsAndConfig", return_value={
             "epd": "waveshare_epd.epd7in3f", "url": "http://example.com",
             "alarmMinutes": 20, "noShutdown": True, "logging": None,
         }), \
         patch("pyinkdisplay.pyInkPictureFrame.setup_logging"), \
         patch("pyinkdisplay.pyInkPictureFrame.PyInkDisplay") as mock_display, \
         patch("pyinkdisplay.pyInkPictureFrame.fetchImageFromUrl", return_value=MagicMock()), \
         patch("pyinkdisplay.pyInkPictureFrame.PiSugarAlarm") as mock_alarm_cls, \
         patch("pyinkdisplay.pyInkPictureFrame.runBatteryMode") as mock_battery, \
         patch("pyinkdisplay.pyInkPictureFrame.continuousEpdUpdateLoop") as mock_usb:

        mock_args.return_value.config = None
        mock_alarm = MagicMock()
        mock_alarm.isSugarPowered.return_value = False
        mock_alarm_cls.return_value = mock_alarm

        pyInkPictureFrame()

    mock_battery.assert_called_once_with(mock_alarm, 20, None, True)
    mock_usb.assert_not_called()


def test_pyInkPictureFrame_calls_continuousLoop_when_powered():
    """Main function enters continuous loop when PiSugar is on mains power."""
    with patch("pyinkdisplay.pyInkPictureFrame.parseArguments") as mock_args, \
         patch("pyinkdisplay.pyInkPictureFrame.loadConfig", return_value={}), \
         patch("pyinkdisplay.pyInkPictureFrame.mergeArgsAndConfig", return_value={
             "epd": "waveshare_epd.epd7in3f", "url": "http://example.com",
             "alarmMinutes": 20, "noShutdown": True, "logging": None,
         }), \
         patch("pyinkdisplay.pyInkPictureFrame.setup_logging"), \
         patch("pyinkdisplay.pyInkPictureFrame.PyInkDisplay") as mock_display, \
         patch("pyinkdisplay.pyInkPictureFrame.fetchImageFromUrl", return_value=MagicMock()), \
         patch("pyinkdisplay.pyInkPictureFrame.PiSugarAlarm") as mock_alarm_cls, \
         patch("pyinkdisplay.pyInkPictureFrame.runBatteryMode") as mock_battery, \
         patch("pyinkdisplay.pyInkPictureFrame.continuousEpdUpdateLoop") as mock_usb:

        mock_args.return_value.config = None
        mock_alarm = MagicMock()
        mock_alarm.isSugarPowered.return_value = True
        mock_alarm_cls.return_value = mock_alarm

        pyInkPictureFrame()

    mock_usb.assert_called_once()
    mock_battery.assert_not_called()


def test_pyInkPictureFrame_checks_for_update_when_usb_powered():
    """When on USB power, check_and_apply_update is called before the continuous loop."""
    with patch("pyinkdisplay.pyInkPictureFrame.parseArguments") as mock_args, \
         patch("pyinkdisplay.pyInkPictureFrame.loadConfig", return_value={}), \
         patch("pyinkdisplay.pyInkPictureFrame.mergeArgsAndConfig", return_value={
             "epd": "waveshare_epd.epd7in3f", "url": "http://example.com",
             "alarmMinutes": 20, "noShutdown": True, "logging": None,
         }), \
         patch("pyinkdisplay.pyInkPictureFrame.setup_logging"), \
         patch("pyinkdisplay.pyInkPictureFrame.PyInkDisplay"), \
         patch("pyinkdisplay.pyInkPictureFrame.fetchImageFromUrl", return_value=MagicMock()), \
         patch("pyinkdisplay.pyInkPictureFrame.PiSugarAlarm") as mock_alarm_cls, \
         patch("pyinkdisplay.pyInkPictureFrame.publishBatteryLevel"), \
         patch("pyinkdisplay.pyInkPictureFrame.check_and_apply_update") as mock_update, \
         patch("pyinkdisplay.pyInkPictureFrame.continuousEpdUpdateLoop"):

        mock_args.return_value.config = None
        mock_alarm = MagicMock()
        mock_alarm.isSugarPowered.return_value = True
        mock_alarm_cls.return_value = mock_alarm
        mock_update.return_value = False  # no update, continue to loop

        pyInkPictureFrame()

    mock_update.assert_called_once()


def test_pyInkPictureFrame_skips_update_when_disabled_in_config():
    """Skips update check when updater.enabled is false in config."""
    with patch("pyinkdisplay.pyInkPictureFrame.parseArguments") as mock_args, \
         patch("pyinkdisplay.pyInkPictureFrame.loadConfig", return_value={"updater": {"enabled": False}}), \
         patch("pyinkdisplay.pyInkPictureFrame.mergeArgsAndConfig", return_value={
             "epd": "waveshare_epd.epd7in3f", "url": "http://example.com",
             "alarmMinutes": 20, "noShutdown": True, "logging": None,
         }), \
         patch("pyinkdisplay.pyInkPictureFrame.setup_logging"), \
         patch("pyinkdisplay.pyInkPictureFrame.PyInkDisplay"), \
         patch("pyinkdisplay.pyInkPictureFrame.fetchImageFromUrl", return_value=MagicMock()), \
         patch("pyinkdisplay.pyInkPictureFrame.PiSugarAlarm") as mock_alarm_cls, \
         patch("pyinkdisplay.pyInkPictureFrame.publishBatteryLevel"), \
         patch("pyinkdisplay.pyInkPictureFrame.check_and_apply_update") as mock_update, \
         patch("pyinkdisplay.pyInkPictureFrame.continuousEpdUpdateLoop"):

        mock_args.return_value.config = "config.yaml"
        mock_alarm = MagicMock()
        mock_alarm.isSugarPowered.return_value = True
        mock_alarm_cls.return_value = mock_alarm

        pyInkPictureFrame()

    mock_update.assert_not_called()


def test_pyInkPictureFrame_uses_setup_logging_from_config():
    """pyInkPictureFrame passes the logging config section to setup_logging."""
    logging_cfg = {"backend": "syslog", "level": "DEBUG"}

    with patch("pyinkdisplay.pyInkPictureFrame.parseArguments") as mock_args, \
         patch("pyinkdisplay.pyInkPictureFrame.loadConfig", return_value={"logging": logging_cfg}), \
         patch("pyinkdisplay.pyInkPictureFrame.mergeArgsAndConfig", return_value={
             "epd": "waveshare_epd.epd7in3f", "url": "http://example.com",
             "alarmMinutes": 20, "noShutdown": True, "logging": None,
         }), \
         patch("pyinkdisplay.pyInkPictureFrame.setup_logging") as mock_setup_logging, \
         patch("pyinkdisplay.pyInkPictureFrame.PyInkDisplay"), \
         patch("pyinkdisplay.pyInkPictureFrame.fetchImageFromUrl", return_value=MagicMock()), \
         patch("pyinkdisplay.pyInkPictureFrame.PiSugarAlarm") as mock_alarm_cls, \
         patch("pyinkdisplay.pyInkPictureFrame.runBatteryMode"):

        mock_args.return_value.config = "config.yaml"
        mock_alarm = MagicMock()
        mock_alarm.isSugarPowered.return_value = False
        mock_alarm_cls.return_value = mock_alarm

        pyInkPictureFrame()

    mock_setup_logging.assert_called_once_with(logging_cfg)


def test_pyInkPictureFrame_reverts_when_force_revert_set():
    """When force_revert is true in config, calls apply_update with latest tag and returns."""
    with patch("pyinkdisplay.pyInkPictureFrame.parseArguments") as mock_args, \
         patch("pyinkdisplay.pyInkPictureFrame.loadConfig", return_value={"updater": {"enabled": True, "force_revert": True}}), \
         patch("pyinkdisplay.pyInkPictureFrame.mergeArgsAndConfig", return_value={
             "epd": "waveshare_epd.epd7in3f", "url": "http://example.com",
             "alarmMinutes": 20, "noShutdown": True, "logging": None,
         }), \
         patch("pyinkdisplay.pyInkPictureFrame.setup_logging"), \
         patch("pyinkdisplay.pyInkPictureFrame.PyInkDisplay"), \
         patch("pyinkdisplay.pyInkPictureFrame.fetchImageFromUrl", return_value=MagicMock()), \
         patch("pyinkdisplay.pyInkPictureFrame.PiSugarAlarm") as mock_alarm_cls, \
         patch("pyinkdisplay.pyInkPictureFrame.runBatteryMode"), \
         patch("pyinkdisplay.pyInkPictureFrame.get_latest_tag", return_value="v2.0.0"), \
         patch("pyinkdisplay.pyInkPictureFrame.apply_update") as mock_apply, \
         patch("pyinkdisplay.pyInkPictureFrame.restart_service") as mock_restart:

        mock_args.return_value.config = "config.yaml"
        mock_alarm = MagicMock()
        mock_alarm.isSugarPowered.return_value = True
        mock_alarm_cls.return_value = mock_alarm

        pyInkPictureFrame()

    mock_apply.assert_called_once_with("v2.0.0")
    mock_restart.assert_called_once()


def test_pyInkPictureFrame_notifies_on_image_fetch_failure():
    """Sends an Apprise notification when image fetch returns None, then exits."""
    import pytest

    with patch("pyinkdisplay.pyInkPictureFrame.parseArguments") as mock_args, \
         patch("pyinkdisplay.pyInkPictureFrame.loadConfig", return_value={"apprise": {"url": "http://apprise.local"}}), \
         patch("pyinkdisplay.pyInkPictureFrame.mergeArgsAndConfig", return_value={
             "epd": "waveshare_epd.epd7in3f", "url": "http://example.com",
             "alarmMinutes": 20, "noShutdown": True, "logging": None,
         }), \
         patch("pyinkdisplay.pyInkPictureFrame.setup_logging"), \
         patch("pyinkdisplay.pyInkPictureFrame.PyInkDisplay"), \
         patch("pyinkdisplay.pyInkPictureFrame.fetchImageFromUrl", return_value=None), \
         patch("pyinkdisplay.pyInkPictureFrame.PiSugarAlarm") as mock_alarm_cls, \
         patch("pyinkdisplay.pyInkPictureFrame.runBatteryMode"), \
         patch("pyinkdisplay.pyInkPictureFrame.notify_if_configured") as mock_notify:

        mock_args.return_value.config = "config.yaml"
        mock_alarm = MagicMock()
        mock_alarm.isSugarPowered.return_value = False
        mock_alarm_cls.return_value = mock_alarm

        with pytest.raises(SystemExit) as exc_info:
            pyInkPictureFrame()

        assert exc_info.value.code == 1

    mock_notify.assert_any_call(
        {"url": "http://apprise.local"},
        "pyInkDisplay: Image Fetch Failed",
        "Failed to fetch image from http://example.com",
    )


def test_pyInkPictureFrame_publishes_telemetry_after_display():
    """publishHaTelemetry is called with the correct fields after display."""
    with patch("pyinkdisplay.pyInkPictureFrame.parseArguments") as mock_args, \
         patch("pyinkdisplay.pyInkPictureFrame.loadConfig", return_value={"mqtt": {"host": "localhost"}}), \
         patch("pyinkdisplay.pyInkPictureFrame.mergeArgsAndConfig", return_value={
             "epd": "waveshare_epd.epd7in3f", "url": "http://example.com",
             "alarmMinutes": 20, "noShutdown": True, "logging": None,
         }), \
         patch("pyinkdisplay.pyInkPictureFrame.setup_logging"), \
         patch("pyinkdisplay.pyInkPictureFrame.publishHaBatteryDiscovery"), \
         patch("pyinkdisplay.pyInkPictureFrame.publishHaTelemetryDiscovery"), \
         patch("pyinkdisplay.pyInkPictureFrame.PyInkDisplay"), \
         patch("pyinkdisplay.pyInkPictureFrame.fetchImageFromUrl", return_value=MagicMock()), \
         patch("pyinkdisplay.pyInkPictureFrame.PiSugarAlarm") as mock_alarm_cls, \
         patch("pyinkdisplay.pyInkPictureFrame.runBatteryMode"), \
         patch("pyinkdisplay.pyInkPictureFrame.publishHaTelemetry") as mock_telemetry:

        mock_args.return_value.config = "config.yaml"
        mock_alarm = MagicMock()
        mock_alarm.isSugarPowered.return_value = False
        mock_alarm.get_battery_level.return_value = 75
        mock_alarm_cls.return_value = mock_alarm

        pyInkPictureFrame()

    mock_telemetry.assert_called_once()
    telemetry_arg = mock_telemetry.call_args[0][1]
    assert "battery_level" in telemetry_arg
    assert "last_update_time" in telemetry_arg
    assert "image_fetch_status" in telemetry_arg
    assert "power_mode" in telemetry_arg
    assert "software_version" in telemetry_arg


def test_pyInkPictureFrame_notifies_when_battery_below_threshold():
    """Sends Apprise notification when battery level is below configured threshold."""
    with patch("pyinkdisplay.pyInkPictureFrame.parseArguments") as mock_args, \
         patch("pyinkdisplay.pyInkPictureFrame.loadConfig", return_value={
             "mqtt": {"host": "localhost"},
             "apprise": {"url": "http://apprise.local", "battery_alert_threshold": 20},
         }), \
         patch("pyinkdisplay.pyInkPictureFrame.mergeArgsAndConfig", return_value={
             "epd": "waveshare_epd.epd7in3f", "url": "http://example.com",
             "alarmMinutes": 20, "noShutdown": True, "logging": None,
         }), \
         patch("pyinkdisplay.pyInkPictureFrame.setup_logging"), \
         patch("pyinkdisplay.pyInkPictureFrame.publishHaBatteryDiscovery"), \
         patch("pyinkdisplay.pyInkPictureFrame.publishHaTelemetryDiscovery"), \
         patch("pyinkdisplay.pyInkPictureFrame.publishHaTelemetry"), \
         patch("pyinkdisplay.pyInkPictureFrame.PyInkDisplay"), \
         patch(
             "pyinkdisplay.pyInkPictureFrame.fetchImageFromUrl",
             return_value=MagicMock(),
         ), \
         patch("pyinkdisplay.pyInkPictureFrame.PiSugarAlarm") as mock_alarm_cls, \
         patch("pyinkdisplay.pyInkPictureFrame.runBatteryMode"), \
         patch(
             "pyinkdisplay.pyInkPictureFrame.notify_if_configured"
         ) as mock_notify:

        mock_args.return_value.config = "config.yaml"
        mock_alarm = MagicMock()
        mock_alarm.isSugarPowered.return_value = False
        mock_alarm.get_battery_level.return_value = 15  # below threshold of 20
        mock_alarm_cls.return_value = mock_alarm

        pyInkPictureFrame()

    mock_notify.assert_any_call(
        {"url": "http://apprise.local", "battery_alert_threshold": 20},
        "pyInkDisplay: Low Battery",
        "Battery level is 15% (threshold: 20%)",
    )


def test_pyInkPictureFrame_notifies_when_update_applied():
    """Sends Apprise notification when check_and_apply_update returns True."""
    with patch("pyinkdisplay.pyInkPictureFrame.parseArguments") as mock_args, \
         patch("pyinkdisplay.pyInkPictureFrame.loadConfig", return_value={
             "apprise": {"url": "http://apprise.local"},
             "updater": {"enabled": True},
         }), \
         patch("pyinkdisplay.pyInkPictureFrame.mergeArgsAndConfig", return_value={
             "epd": "waveshare_epd.epd7in3f", "url": "http://example.com",
             "alarmMinutes": 20, "noShutdown": True, "logging": None,
         }), \
         patch("pyinkdisplay.pyInkPictureFrame.setup_logging"), \
         patch("pyinkdisplay.pyInkPictureFrame.publishHaTelemetry"), \
         patch("pyinkdisplay.pyInkPictureFrame.publishHaBatteryDiscovery"), \
         patch("pyinkdisplay.pyInkPictureFrame.publishHaTelemetryDiscovery"), \
         patch("pyinkdisplay.pyInkPictureFrame.PyInkDisplay"), \
         patch(
             "pyinkdisplay.pyInkPictureFrame.fetchImageFromUrl",
             return_value=MagicMock(),
         ), \
         patch("pyinkdisplay.pyInkPictureFrame.PiSugarAlarm") as mock_alarm_cls, \
         patch(
             "pyinkdisplay.pyInkPictureFrame.check_and_apply_update",
             return_value=True,
         ), \
         patch(
             "pyinkdisplay.pyInkPictureFrame.notify_if_configured"
         ) as mock_notify:

        mock_args.return_value.config = "config.yaml"
        mock_alarm = MagicMock()
        mock_alarm.isSugarPowered.return_value = True
        mock_alarm.get_battery_level.return_value = 90
        mock_alarm_cls.return_value = mock_alarm

        pyInkPictureFrame()

    mock_notify.assert_any_call(
        {"url": "http://apprise.local"},
        "pyInkDisplay: Update Applied",
        "Updated to latest release. Service is restarting.",
    )
