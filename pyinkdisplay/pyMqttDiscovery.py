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
"""

import json
import logging

import paho.mqtt.client as mqtt

logger = logging.getLogger(__name__)


def publishHaBatteryDiscovery(mqtt_config):
    """
    Publishes Home Assistant MQTT discovery message for PiSugar battery sensor.
    """
    DISCOVERY_TOPIC = "homeassistant/sensor/pisugar_battery/config"
    STATE_TOPIC = mqtt_config.get("topic", "homeassistant/sensor/pisugar_battery/state")
    payload = {
        "name": "PiSugar Battery",
        "state_topic": STATE_TOPIC,
        "unit_of_measurement": "%",
        "device_class": "battery",
        "unique_id": "pisugar_battery_1",
        "device": {
            "identifiers": ["pisugar_1"],
            "name": "PiSugar UPS",
            "model": "PiSugar3",
            "manufacturer": "PiSugar",
        },
    }
    client = mqtt.Client(protocol=mqtt.MQTTv5)
    if mqtt_config.get("username"):
        client.username_pw_set(
            mqtt_config.get("username"), mqtt_config.get("password", "")
        )
    try:
        client.connect(
            mqtt_config.get("host", "localhost"), int(mqtt_config.get("port", 1883)), 60
        )
        client.loop_start()
        client.publish(DISCOVERY_TOPIC, json.dumps(payload), retain=True)
        client.loop_stop()
        client.disconnect()
        logger.info("Published Home Assistant discovery message to %s", DISCOVERY_TOPIC)
    except Exception as e:
        logger.error("Failed to publish discovery message: %s", e)


STATE_TOPIC = "homeassistant/sensor/pyinkdisplay/state"

_TELEMETRY_SENSORS = [
    {
        "field": "battery_level",
        "name": "pyInkDisplay Battery Level",
        "device_class": "battery",
        "unique_id": "pyinkdisplay_battery_level",
    },
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


def _mqttClient(mqtt_config: dict):
    """Create and connect a paho MQTT client."""
    client = mqtt.Client(protocol=mqtt.MQTTv5)
    if mqtt_config.get("username"):
        client.username_pw_set(
            mqtt_config["username"], mqtt_config.get("password", "")
        )
    client.connect(
        mqtt_config.get("host", "localhost"),
        int(mqtt_config.get("port", 1883)),
        60,
    )
    return client


def publishHaTelemetryDiscovery(mqtt_config: dict) -> None:
    """
    Publish Home Assistant MQTT discovery messages for all telemetry sensors.
    Call once at startup alongside publishHaBatteryDiscovery.
    """
    try:
        client = _mqttClient(mqtt_config)
        client.loop_start()
        for sensor in _TELEMETRY_SENSORS:
            discovery_topic = (
                f"homeassistant/sensor/{sensor['field']}/config"
            )
            payload = {
                "name": sensor["name"],
                "state_topic": STATE_TOPIC,
                "value_template": (
                    f"{{{{ value_json.{sensor['field']} }}}}"
                ),
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
        client = _mqttClient(mqtt_config)
        client.loop_start()
        client.publish(STATE_TOPIC, json.dumps(telemetry), retain=True)
        client.loop_stop()
        client.disconnect()
        logger.info("Published telemetry to %s", STATE_TOPIC)
    except Exception as e:
        logger.error("Failed to publish telemetry: %s", e)
