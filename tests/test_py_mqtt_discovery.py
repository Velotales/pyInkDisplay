import json
from unittest.mock import MagicMock, patch

from pyinkdisplay.pyMqttDiscovery import (
    publishHaBatteryDiscovery,
    publishHaTelemetry,
    publishHaTelemetryDiscovery,
)

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
    with patch("pyinkdisplay.pyMqttDiscovery.mqtt.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client

        publishHaTelemetry(MQTT_CONFIG, telemetry)

    published_payload = mock_client.publish.call_args[0][1]
    assert json.loads(published_payload) == telemetry
    published_topic = mock_client.publish.call_args[0][0]
    assert published_topic == "homeassistant/sensor/pyinkdisplay/state"


def test_publishHaTelemetryDiscovery_publishes_discovery_for_all_sensors():
    """Publishes one HA discovery message per telemetry sensor field."""
    with patch("pyinkdisplay.pyMqttDiscovery.mqtt.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client

        publishHaTelemetryDiscovery(MQTT_CONFIG)

    publish_topics = [
        call_args[0][0] for call_args in mock_client.publish.call_args_list
    ]
    expected_sensors = [
        "last_update_time",
        "image_fetch_status",
        "power_mode",
        "software_version",
        "update_available",
    ]
    for sensor in expected_sensors:
        assert any(
            sensor in topic for topic in publish_topics
        ), f"Missing discovery for {sensor}"


def test_publishHaTelemetry_disconnects_even_when_publish_raises():
    """disconnect must be called even if publish raises an exception.

    Without try/finally, a publish failure leaks the MQTT connection.
    On USB mode (hundreds of iterations/day) leaked connections accumulate.
    """
    with patch("pyinkdisplay.pyMqttDiscovery.mqtt.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.publish.side_effect = RuntimeError("broker gone")

        # The function swallows exceptions — we just verify disconnect was still called
        publishHaTelemetry(MQTT_CONFIG, {"battery_level": 50})

    mock_client.disconnect.assert_called_once()


def test_publishHaBatteryDiscovery_disconnects_even_when_publish_raises():
    """disconnect must be called in publishHaBatteryDiscovery even if publish raises."""
    with patch("pyinkdisplay.pyMqttDiscovery.mqtt.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.publish.side_effect = RuntimeError("broker gone")

        # The function catches all exceptions internally — we just verify disconnect ran
        publishHaBatteryDiscovery(MQTT_CONFIG)

    mock_client.disconnect.assert_called_once()
