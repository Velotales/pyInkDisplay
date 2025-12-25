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
import os
import time

import paho.mqtt.client as mqtt

# Read MQTT config from environment variables for safety
MQTT_HOST = os.getenv("MQTT_HOST", "localhost")
MQTT_PORT = int(os.getenv("MQTT_PORT", 1883))
MQTT_TOPIC = os.getenv("MQTT_TOPIC", "test/connection")
MQTT_USERNAME = os.getenv("MQTT_USERNAME", "")
MQTT_PASSWORD = os.getenv("MQTT_PASSWORD", "")

# Home Assistant MQTT Discovery
DISCOVERY_TOPIC = "homeassistant/sensor/pisugar_battery/config"
STATE_TOPIC = "homeassistant/sensor/pisugar_battery/state"
DISCOVERY_PAYLOAD = {
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


def on_connect(client, userdata, flags, rc, properties=None):
    if rc == 0:
        print("Connected successfully!")
        # Publish Home Assistant discovery message
        client.publish(DISCOVERY_TOPIC, json.dumps(DISCOVERY_PAYLOAD), retain=True)
        print(f"Published discovery message to {DISCOVERY_TOPIC}")
        # Publish a test state message
        client.publish(STATE_TOPIC, "77", retain=True)
        print(f"Published test battery state to {STATE_TOPIC}")
        # Publish a test message to the test topic
        client.publish(MQTT_TOPIC, "MQTT connection test successful!")
        print(f"Published test message to {MQTT_TOPIC}")
    else:
        print(f"Failed to connect, return code {rc}")


client = mqtt.Client(protocol=mqtt.MQTTv5)
if MQTT_USERNAME:
    client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)
client.on_connect = on_connect

client.connect(MQTT_HOST, MQTT_PORT, 60)
client.loop_start()
time.sleep(2)
client.loop_stop()
client.disconnect()
