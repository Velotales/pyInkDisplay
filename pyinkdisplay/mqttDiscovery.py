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
import paho.mqtt.client as mqtt


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
        print(f"Published Home Assistant discovery message to {DISCOVERY_TOPIC}")
    except Exception as e:
        print(f"Failed to publish discovery message: {e}")
