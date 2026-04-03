# Observability Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add configurable logging backends (console/seq/syslog, loki reserved), Apprise push notifications for key events, and richer MQTT telemetry published to Home Assistant after each cycle.

**Architecture:** Three new modules — `logging_config.py` (backend abstraction), `notifications.py` (Apprise wrapper), extended `mqttDiscovery.py` (rich telemetry). All three are wired into `pyInkPictureFrame.py`. Config is driven by new `logging` and `apprise` sections in `config.yaml`.

**Tech Stack:** Python 3.8+, `paho-mqtt`, `requests`, `seqlog` (optional), `unittest.mock`

**Prerequisites:** Plan 1 (power-aware runtime) must be complete. Plan 2 (deployment) is independent but recommended first.

---

### Task 1: `logging_config.py` — console and syslog backends

**Files:**
- Create: `pyinkdisplay/logging_config.py`
- Create: `tests/test_logging_config.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_logging_config.py`:

```python
import logging
from unittest.mock import MagicMock, patch

from pyinkdisplay.logging_config import setup_logging


def test_setup_logging_console_calls_basicConfig():
    """Console backend calls logging.basicConfig with INFO level."""
    with patch("pyinkdisplay.logging_config.logging.basicConfig") as mock_config:
        setup_logging({"backend": "console", "level": "INFO"})
    mock_config.assert_called_once()
    call_kwargs = mock_config.call_args[1]
    assert call_kwargs["level"] == logging.INFO


def test_setup_logging_defaults_to_console():
    """Empty config dict uses console backend at INFO level."""
    with patch("pyinkdisplay.logging_config.logging.basicConfig") as mock_config:
        setup_logging({})
    mock_config.assert_called_once()


def test_setup_logging_syslog_adds_handler():
    """Syslog backend adds a SysLogHandler to the root logger."""
    with patch("pyinkdisplay.logging_config.logging.handlers.SysLogHandler") as mock_handler_cls, \
         patch("pyinkdisplay.logging_config.logging.getLogger") as mock_get_logger:
        mock_root = MagicMock()
        mock_get_logger.return_value = mock_root
        mock_handler_cls.return_value = MagicMock()

        setup_logging({
            "backend": "syslog",
            "level": "WARNING",
            "syslog": {"host": "logserver.local", "port": "514"},
        })

    mock_handler_cls.assert_called_once_with(address=("logserver.local", 514))
    mock_root.addHandler.assert_called_once()
    mock_root.setLevel.assert_called_once_with(logging.WARNING)


def test_setup_logging_loki_falls_back_to_console():
    """Loki backend logs a warning and falls back to console."""
    with patch("pyinkdisplay.logging_config.logging.basicConfig") as mock_config, \
         patch("pyinkdisplay.logging_config.logging.warning") as mock_warning:
        setup_logging({"backend": "loki"})
    mock_config.assert_called_once()
    mock_warning.assert_called_once()
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_logging_config.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'pyinkdisplay.logging_config'`

- [ ] **Step 3: Implement `logging_config.py`**

Create `pyinkdisplay/logging_config.py`:

```python
"""
Configurable logging backends for pyInkDisplay.

Supported backends: console (default), seq, syslog.
loki is reserved for future implementation.
"""

import logging
import logging.handlers

_FMT = "%(asctime)s - %(levelname)s - %(module)s:%(funcName)s - %(message)s"


def setup_logging(config: dict) -> None:
    """
    Configure the root logger from the 'logging' section of config.yaml.

    Args:
        config (dict): The 'logging' config section, e.g.
            {"backend": "syslog", "level": "INFO", "syslog": {"host": "...", "port": 514}}
    """
    backend = config.get("backend", "console")
    level_name = config.get("level", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)

    if backend == "seq":
        _setup_seq(config.get("seq", {}), level)
    elif backend == "syslog":
        _setup_syslog(config.get("syslog", {}), level)
    elif backend == "loki":
        logging.basicConfig(level=level, format=_FMT)
        logging.warning("Loki backend is not yet implemented — falling back to console logging.")
    else:
        logging.basicConfig(level=level, format=_FMT)
        logging.info("Console logging enabled.")


def _setup_seq(seq_config: dict, level: int) -> None:
    """Configure Seq structured logging via the seqlog package."""
    try:
        import seqlog  # type: ignore[import-untyped]

        seqlog.log_to_seq(
            server_url=seq_config.get("url", "http://localhost:5341"),
            level=level,
            override_root_logger=True,
        )
        logging.info("Seq logging enabled.")
    except ImportError:
        logging.basicConfig(level=level, format=_FMT)
        logging.warning("seqlog package not installed — falling back to console logging.")


def _setup_syslog(syslog_config: dict, level: int) -> None:
    """Configure remote syslog via SysLogHandler."""
    handler = logging.handlers.SysLogHandler(
        address=(
            syslog_config.get("host", "localhost"),
            int(syslog_config.get("port", 514)),
        )
    )
    handler.setFormatter(logging.Formatter(_FMT))
    root = logging.getLogger()
    root.setLevel(level)
    root.addHandler(handler)
    logging.info("Syslog logging enabled.")
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_logging_config.py -v
```

Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add pyinkdisplay/logging_config.py tests/test_logging_config.py
git commit -m "feat: add logging_config module with console, syslog, loki-stub backends"
```

---

### Task 2: Add seq backend to `logging_config.py`

**Files:**
- Modify: `tests/test_logging_config.py`

The seq backend is already implemented in Task 1. This task adds tests for it.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_logging_config.py`:

```python
def test_setup_logging_seq_calls_seqlog(monkeypatch):
    """Seq backend calls seqlog.log_to_seq with the configured URL."""
    mock_seqlog = MagicMock()
    monkeypatch.setitem(__import__("sys").modules, "seqlog", mock_seqlog)

    setup_logging({
        "backend": "seq",
        "level": "DEBUG",
        "seq": {"url": "http://seq.local:5341"},
    })

    mock_seqlog.log_to_seq.assert_called_once_with(
        server_url="http://seq.local:5341",
        level=logging.DEBUG,
        override_root_logger=True,
    )


def test_setup_logging_seq_falls_back_when_seqlog_missing():
    """Falls back to console logging when seqlog is not installed."""
    with patch("pyinkdisplay.logging_config.logging.basicConfig") as mock_config, \
         patch("builtins.__import__", side_effect=lambda name, *a, **kw: (_ for _ in ()).throw(ImportError()) if name == "seqlog" else __import__(name, *a, **kw)):
        setup_logging({"backend": "seq", "seq": {"url": "http://seq.local:5341"}})
    mock_config.assert_called_once()
```

- [ ] **Step 2: Run tests to verify they pass** (seq impl is already present from Task 1)

```bash
pytest tests/test_logging_config.py -v
```

Expected: all PASS

- [ ] **Step 3: Commit**

```bash
git add tests/test_logging_config.py
git commit -m "test: add seq backend tests for logging_config"
```

---

### Task 3: Wire `logging_config` into `pyInkPictureFrame.py`

**Files:**
- Modify: `pyinkdisplay/pyInkPictureFrame.py`
- Modify: `tests/test_py_ink_picture_frame.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_py_ink_picture_frame.py`:

```python
from pyinkdisplay.pyInkPictureFrame import pyInkPictureFrame


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
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_py_ink_picture_frame.py::test_pyInkPictureFrame_uses_setup_logging_from_config -v
```

Expected: FAIL

- [ ] **Step 3: Replace `setupLogging` with `setup_logging` in `pyInkPictureFrame.py`**

Add import at the top of `pyinkdisplay/pyInkPictureFrame.py`:

```python
from .logging_config import setup_logging
```

In `pyInkPictureFrame()`, replace the call to `setupLogging(merged.get("logging"))` with:

```python
    loggingConfig = config.get("logging", {}) if config else {}
    setup_logging(loggingConfig)
```

The `setupLogging` function can remain in the file (it is still tested) but is no longer called from `pyInkPictureFrame()`.

- [ ] **Step 4: Run all tests**

```bash
pytest -v
```

Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add pyinkdisplay/pyInkPictureFrame.py tests/test_py_ink_picture_frame.py
git commit -m "feat: wire logging_config.setup_logging into main entry point"
```

---

### Task 4: `notifications.py` — Apprise wrapper

**Files:**
- Create: `pyinkdisplay/notifications.py`
- Create: `tests/test_notifications.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_notifications.py`:

```python
from unittest.mock import MagicMock, patch

from pyinkdisplay.notifications import notify_if_configured, send_notification


def test_send_notification_posts_to_apprise():
    """POSTs title and body to the Apprise /notify endpoint."""
    with patch("pyinkdisplay.notifications.requests.post") as mock_post:
        mock_post.return_value = MagicMock(status_code=200)
        mock_post.return_value.raise_for_status = MagicMock()
        result = send_notification("http://apprise.local:8000", "Test Title", "Test body")
    mock_post.assert_called_once_with(
        "http://apprise.local:8000/notify",
        json={"title": "Test Title", "body": "Test body"},
        timeout=5,
    )
    assert result is True


def test_send_notification_returns_false_on_request_error():
    """Returns False when the HTTP request fails."""
    import requests as req
    with patch("pyinkdisplay.notifications.requests.post", side_effect=req.exceptions.ConnectionError("refused")):
        result = send_notification("http://apprise.local:8000", "Title", "Body")
    assert result is False


def test_notify_if_configured_sends_when_url_present():
    """Calls send_notification when apprise_config contains a url."""
    with patch("pyinkdisplay.notifications.send_notification") as mock_send:
        notify_if_configured({"url": "http://apprise.local:8000"}, "Title", "Body")
    mock_send.assert_called_once_with("http://apprise.local:8000", "Title", "Body")


def test_notify_if_configured_skips_when_no_config():
    """Does nothing when apprise_config is None."""
    with patch("pyinkdisplay.notifications.send_notification") as mock_send:
        notify_if_configured(None, "Title", "Body")
    mock_send.assert_not_called()


def test_notify_if_configured_skips_when_url_missing():
    """Does nothing when apprise_config has no url key."""
    with patch("pyinkdisplay.notifications.send_notification") as mock_send:
        notify_if_configured({}, "Title", "Body")
    mock_send.assert_not_called()
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_notifications.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'pyinkdisplay.notifications'`

- [ ] **Step 3: Implement `notifications.py`**

Create `pyinkdisplay/notifications.py`:

```python
"""
Apprise notification wrapper for pyInkDisplay.

Sends push notifications to a local Apprise container for key events
(errors, updates applied, low battery). Silent no-op when not configured.
"""

import logging
from typing import Optional

import requests

logger = logging.getLogger(__name__)


def send_notification(apprise_url: str, title: str, message: str) -> bool:
    """
    Send a notification via the Apprise container REST API.

    Args:
        apprise_url (str): Base URL of the Apprise container (e.g. 'http://localhost:8000').
        title (str): Notification title.
        message (str): Notification body.

    Returns:
        bool: True on success, False on failure.
    """
    try:
        response = requests.post(
            f"{apprise_url.rstrip('/')}/notify",
            json={"title": title, "body": message},
            timeout=5,
        )
        response.raise_for_status()
        logger.info("Notification sent: %s", title)
        return True
    except requests.exceptions.RequestException as e:
        logger.error("Failed to send notification '%s': %s", title, e)
        return False


def notify_if_configured(
    apprise_config: Optional[dict], title: str, message: str
) -> None:
    """
    Send a notification if Apprise is configured; silently skip if not.

    Args:
        apprise_config (dict or None): The 'apprise' config section.
        title (str): Notification title.
        message (str): Notification body.
    """
    if not apprise_config or not apprise_config.get("url"):
        return
    send_notification(apprise_config["url"], title, message)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_notifications.py -v
```

Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add pyinkdisplay/notifications.py tests/test_notifications.py
git commit -m "feat: add notifications module for Apprise push events"
```

---

### Task 5: Wire notifications into `pyInkPictureFrame.py`

**Files:**
- Modify: `pyinkdisplay/pyInkPictureFrame.py`
- Modify: `tests/test_py_ink_picture_frame.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_py_ink_picture_frame.py`:

```python
def test_pyInkPictureFrame_notifies_on_image_fetch_failure():
    """Sends an Apprise notification when image fetch returns the fallback image."""
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

        pyInkPictureFrame()

    mock_notify.assert_any_call(
        {"url": "http://apprise.local"},
        "pyInkDisplay: Image Fetch Failed",
        "Failed to fetch image from http://example.com",
    )
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_py_ink_picture_frame.py::test_pyInkPictureFrame_notifies_on_image_fetch_failure -v
```

Expected: FAIL

- [ ] **Step 3: Wire notifications into `pyInkPictureFrame.py`**

Add import:

```python
from .notifications import notify_if_configured
```

In `pyInkPictureFrame()`, read the Apprise config and add notification calls:

```python
    appriseConfig = config.get("apprise") if config else None
```

After the `fetchImageFromUrl` call, add a check for fetch failure:

```python
        image = fetchImageFromUrl(merged["url"])
        if image is None:
            logging.warning("Image fetch returned None — using fallback.")
            notify_if_configured(
                appriseConfig,
                "pyInkDisplay: Image Fetch Failed",
                f"Failed to fetch image from {merged['url']}",
            )
```

In the `except` block of the main try/except, add:

```python
    except (EPDNotFoundError, RuntimeError) as e:
        logging.error("EPD display error: %s", e)
        notify_if_configured(appriseConfig, "pyInkDisplay: EPD Error", str(e))
        sys.exit(1)
    except Exception as e:
        logging.error("An unexpected error occurred during EPD display: %s", e)
        notify_if_configured(appriseConfig, "pyInkDisplay: Unexpected Error", str(e))
        sys.exit(1)
```

- [ ] **Step 4: Run all tests**

```bash
pytest -v
```

Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add pyinkdisplay/pyInkPictureFrame.py tests/test_py_ink_picture_frame.py
git commit -m "feat: send Apprise notifications on image fetch failure and errors"
```

---

### Task 6: Extended MQTT telemetry in `mqttDiscovery.py`

**Files:**
- Modify: `pyinkdisplay/mqttDiscovery.py`
- Modify or create: `tests/test_mqtt_discovery.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_mqtt_discovery.py`:

```python
import json
from unittest.mock import MagicMock, call, patch

from pyinkdisplay.mqttDiscovery import publishHaTelemetry, publishHaTelemetryDiscovery


MQTT_CONFIG = {"host": "localhost", "port": 1883}


def test_publishHaTelemetry_publishes_json_payload():
    """Publishes the telemetry dict as a JSON string to the state topic."""
    telemetry = {
        "battery_level": 80,
        "last_update_time": "2026-04-03T12:00:00",
        "image_fetch_status": "success",
        "power_mode": "battery",
        "software_version": "v1.2.0",
        "update_available": False,
    }
    with patch("pyinkdisplay.mqttDiscovery.mqtt.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client

        publishHaTelemetry(MQTT_CONFIG, telemetry)

    published_payload = mock_client.publish.call_args[0][1]
    assert json.loads(published_payload) == telemetry
    published_topic = mock_client.publish.call_args[0][0]
    assert published_topic == "homeassistant/sensor/pyinkdisplay/state"


def test_publishHaTelemetryDiscovery_publishes_discovery_for_all_sensors():
    """Publishes one HA discovery message per telemetry sensor field."""
    with patch("pyinkdisplay.mqttDiscovery.mqtt.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client

        publishHaTelemetryDiscovery(MQTT_CONFIG)

    publish_topics = [call_args[0][0] for call_args in mock_client.publish.call_args_list]
    expected_sensors = [
        "last_update_time", "image_fetch_status", "power_mode",
        "software_version", "update_available",
    ]
    for sensor in expected_sensors:
        assert any(sensor in topic for topic in publish_topics), f"Missing discovery for {sensor}"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_mqtt_discovery.py -v
```

Expected: FAIL with `ImportError`

- [ ] **Step 3: Add `publishHaTelemetry` and `publishHaTelemetryDiscovery` to `mqttDiscovery.py`**

Append to `pyinkdisplay/mqttDiscovery.py`:

```python
import logging

logger = logging.getLogger(__name__)

STATE_TOPIC = "homeassistant/sensor/pyinkdisplay/state"

_TELEMETRY_SENSORS = [
    {
        "field": "last_update_time",
        "name": "pyInkDisplay Last Update",
        "device_class": "timestamp",
        "unique_id": "pyinkdisplay_last_update",
    },
    {
        "field": "image_fetch_status",
        "name": "pyInkDisplay Image Fetch Status",
        "device_class": None,
        "unique_id": "pyinkdisplay_image_fetch_status",
    },
    {
        "field": "power_mode",
        "name": "pyInkDisplay Power Mode",
        "device_class": None,
        "unique_id": "pyinkdisplay_power_mode",
    },
    {
        "field": "software_version",
        "name": "pyInkDisplay Software Version",
        "device_class": None,
        "unique_id": "pyinkdisplay_software_version",
    },
    {
        "field": "update_available",
        "name": "pyInkDisplay Update Available",
        "device_class": None,
        "unique_id": "pyinkdisplay_update_available",
    },
]

_DEVICE = {
    "identifiers": ["pyinkdisplay_1"],
    "name": "pyInkDisplay",
    "manufacturer": "Velotales",
}


def _mqtt_client(mqtt_config: dict):
    """Create and connect a paho MQTT client."""
    client = mqtt.Client(protocol=mqtt.MQTTv5)
    if mqtt_config.get("username"):
        client.username_pw_set(
            mqtt_config["username"], mqtt_config.get("password", "")
        )
    client.connect(
        mqtt_config.get("host", "localhost"), int(mqtt_config.get("port", 1883)), 60
    )
    return client


def publishHaTelemetryDiscovery(mqtt_config: dict) -> None:
    """
    Publish Home Assistant MQTT discovery messages for all telemetry sensors.
    Call once at startup alongside publishHaBatteryDiscovery.
    """
    try:
        client = _mqtt_client(mqtt_config)
        client.loop_start()
        for sensor in _TELEMETRY_SENSORS:
            discovery_topic = (
                f"homeassistant/sensor/{sensor['unique_id']}/config"
            )
            payload = {
                "name": sensor["name"],
                "state_topic": STATE_TOPIC,
                "value_template": f"{{{{ value_json.{sensor['field']} }}}}",
                "unique_id": sensor["unique_id"],
                "device": _DEVICE,
            }
            if sensor["device_class"]:
                payload["device_class"] = sensor["device_class"]
            client.publish(discovery_topic, json.dumps(payload), retain=True)
        client.loop_stop()
        client.disconnect()
        logger.info("Published telemetry discovery messages.")
    except Exception as e:
        logger.error("Failed to publish telemetry discovery: %s", e)


def publishHaTelemetry(mqtt_config: dict, telemetry: dict) -> None:
    """
    Publish the telemetry payload as JSON to the pyinkdisplay state topic.

    Args:
        mqtt_config (dict): MQTT broker configuration.
        telemetry (dict): Dict with keys: battery_level, last_update_time,
            image_fetch_status, power_mode, software_version, update_available.
    """
    try:
        client = _mqtt_client(mqtt_config)
        client.loop_start()
        client.publish(STATE_TOPIC, json.dumps(telemetry), retain=True)
        client.loop_stop()
        client.disconnect()
        logger.info("Published telemetry to %s", STATE_TOPIC)
    except Exception as e:
        logger.error("Failed to publish telemetry: %s", e)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_mqtt_discovery.py -v
```

Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add pyinkdisplay/mqttDiscovery.py tests/test_mqtt_discovery.py
git commit -m "feat: add publishHaTelemetry and publishHaTelemetryDiscovery to mqttDiscovery"
```

---

### Task 7: Wire telemetry into `pyInkPictureFrame.py`

**Files:**
- Modify: `pyinkdisplay/pyInkPictureFrame.py`
- Modify: `tests/test_py_ink_picture_frame.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_py_ink_picture_frame.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_py_ink_picture_frame.py::test_pyInkPictureFrame_publishes_telemetry_after_display -v
```

Expected: FAIL

- [ ] **Step 3: Wire telemetry into `pyInkPictureFrame.py`**

Add imports:

```python
from datetime import datetime, timezone

from .mqttDiscovery import publishHaBatteryDiscovery, publishHaTelemetry, publishHaTelemetryDiscovery
from .updater import check_and_apply_update, get_current_tag
```

In `pyInkPictureFrame()`, after fetching and displaying the image, build and publish the telemetry payload. Replace the existing `publishHaBatteryDiscovery` startup block and the `publishBatteryLevel` calls with:

```python
    # Publish HA discovery on startup
    if mqttConfig:
        publishHaBatteryDiscovery(mqttConfig)
        publishHaTelemetryDiscovery(mqttConfig)
```

After `displayManager.displayImage(image)`, build the telemetry and publish it:

```python
        imageFetchStatus = "success" if image is not None else "failure"
        powerMode = "usb" if alarmManager.isSugarPowered() else "battery"

        try:
            batteryLevel = alarmManager.get_battery_level()
        except Exception:
            batteryLevel = None

        telemetry = {
            "battery_level": batteryLevel,
            "last_update_time": datetime.now(timezone.utc).isoformat(),
            "image_fetch_status": imageFetchStatus,
            "power_mode": powerMode,
            "software_version": get_current_tag() or "unknown",
            "update_available": False,  # updated below in USB mode if a newer tag is found
        }

        if mqttConfig:
            publishHaTelemetry(mqttConfig, telemetry)
```

Remove the old `publishBatteryLevel(alarmManager, mqttConfig)` calls from the USB and battery branches (telemetry now covers this).

- [ ] **Step 4: Run all tests**

```bash
pytest -v
```

Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add pyinkdisplay/pyInkPictureFrame.py tests/test_py_ink_picture_frame.py
git commit -m "feat: publish rich telemetry payload to MQTT after each cycle"
```

---

### Task 7b: Battery threshold and update-applied notifications

**Files:**
- Modify: `pyinkdisplay/pyInkPictureFrame.py`
- Modify: `tests/test_py_ink_picture_frame.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_py_ink_picture_frame.py`:

```python
def test_pyInkPictureFrame_notifies_when_battery_below_threshold():
    """Sends Apprise notification when battery level is below the configured threshold."""
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
         patch("pyinkdisplay.pyInkPictureFrame.fetchImageFromUrl", return_value=MagicMock()), \
         patch("pyinkdisplay.pyInkPictureFrame.PiSugarAlarm") as mock_alarm_cls, \
         patch("pyinkdisplay.pyInkPictureFrame.runBatteryMode"), \
         patch("pyinkdisplay.pyInkPictureFrame.notify_if_configured") as mock_notify:

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
         patch("pyinkdisplay.pyInkPictureFrame.fetchImageFromUrl", return_value=MagicMock()), \
         patch("pyinkdisplay.pyInkPictureFrame.PiSugarAlarm") as mock_alarm_cls, \
         patch("pyinkdisplay.pyInkPictureFrame.check_and_apply_update", return_value=True), \
         patch("pyinkdisplay.pyInkPictureFrame.notify_if_configured") as mock_notify:

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
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_py_ink_picture_frame.py::test_pyInkPictureFrame_notifies_when_battery_below_threshold tests/test_py_ink_picture_frame.py::test_pyInkPictureFrame_notifies_when_update_applied -v
```

Expected: FAIL

- [ ] **Step 3: Add battery threshold check and update-applied notification to `pyInkPictureFrame.py`**

After building the `telemetry` dict (from Task 7), add the battery threshold check:

```python
        batteryThreshold = appriseConfig.get("battery_alert_threshold", 0) if appriseConfig else 0
        if batteryLevel is not None and batteryThreshold and batteryLevel < batteryThreshold:
            notify_if_configured(
                appriseConfig,
                "pyInkDisplay: Low Battery",
                f"Battery level is {batteryLevel}% (threshold: {batteryThreshold}%)",
            )
```

In the USB-power branch, after `check_and_apply_update()` returns `True`, add the notification before returning:

```python
            updated = check_and_apply_update()
            if updated:
                notify_if_configured(
                    appriseConfig,
                    "pyInkDisplay: Update Applied",
                    "Updated to latest release. Service is restarting.",
                )
                logging.info("Update applied. Service is restarting.")
                return
```

- [ ] **Step 4: Run all tests**

```bash
pytest -v
```

Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add pyinkdisplay/pyInkPictureFrame.py tests/test_py_ink_picture_frame.py
git commit -m "feat: notify on low battery and when self-update is applied"
```

---

### Task 8: Add `apprise` and `logging` config sections to `config.yaml`

**Files:**
- Modify: `config/config.yaml`

- [ ] **Step 1: Update `config/config.yaml`**

Add the following sections to `config/config.yaml`:

```yaml
# Apprise notification configuration
apprise:
  url: "http://localhost:8000"       # Apprise container base URL
  battery_alert_threshold: 20        # Notify when battery drops below this %

# Logging backend configuration
logging:
  backend: "console"    # Options: console | seq | syslog | loki (future)
  level: "INFO"
  seq:
    url: "http://localhost:5341"
  syslog:
    host: "localhost"
    port: 514
  loki:
    url: "http://localhost:3100/loki/api/v1/push"
    labels:
      job: "pyInkPictureFrame"
```

- [ ] **Step 2: Verify the full config file is valid YAML**

```bash
python3 -c "import yaml; yaml.safe_load(open('config/config.yaml'))" && echo "Valid YAML"
```

Expected: `Valid YAML`

- [ ] **Step 3: Commit**

```bash
git add config/config.yaml
git commit -m "docs: add apprise and logging sections to config.yaml"
```
