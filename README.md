# pyInkDisplay

My need was to display a Home Assistant dashboard on an e-ink display

![image](https://github.com/user-attachments/assets/8d20875c-5dad-4961-9875-134c08eebf63)

[![Python CI](https://github.com/Velotales/pyInkDisplay/actions/workflows/tests.yml/badge.svg)](https://github.com/Velotales/pyInkDisplay/actions/workflows/tests.yml)

## Details
This project takes an image, either locally or remotely, and displays it on an e-ink display.

## Home Assistant & MQTT Integration

This project supports publishing the PiSugar battery level to Home Assistant via MQTT, using Home Assistant's MQTT Discovery feature. This allows you to monitor the battery level as a sensor in Home Assistant with no manual YAML configuration.

### How it works
- The battery level is published to an MQTT topic after each update.
- On startup, a Home Assistant MQTT Discovery message is sent, so Home Assistant will automatically create a `sensor.pisugar_battery` entity.

### Configuration
Edit your `config/config.yaml` (or `config/config_local.yaml` for local, uncommitted settings) to include the `mqtt` section:

```yaml
mqtt:
	host: "localhost"   # MQTT broker address
	port: 1883           # MQTT broker port
	topic: "homeassistant/sensor/pisugar_battery/state"  # MQTT topic for battery level
	username: ""         # Optional: MQTT username
	password: ""         # Optional: MQTT password
```

If MQTT is configured, the battery level will be published and Home Assistant will auto-discover the sensor.

### Home Assistant Setup
1. Make sure the [MQTT integration](https://www.home-assistant.io/integrations/mqtt/) is enabled in Home Assistant and connected to your broker.
2. Start the pyInkDisplay service. You should see a new entity called `sensor.pisugar_battery` in Home Assistant.
3. The battery level will update after each display refresh.

### Troubleshooting
- Check the logs for MQTT connection errors.
- Use the provided `mqtt_test.py` to verify your MQTT broker and Home Assistant discovery setup.

---

This was written for a Raspberry Pi Zero W 2, using Waveshare's 7.3 inch 7 color e-ink display.

To make it a true digital photo frame, I added a PiSugar 3 to provide battery power and the ability to power the Raspberry Pi Zero on with RTC.

## Libraries
This project pulls in Rob Weber's [Omni-EPD](https://github.com/robweber/omni-epd/), so it "should" work with most e-ink displays.

I also made use of [PiSugar python library](https://github.com/PiSugar/pisugar-python) to control the PiSugar and set the next wakeup interval. 

I found this to be quite a dependancy nightmare, so included in the repo is a requirements.in. To use, follow this, preferably in a virtual environment:

1.  **Install `pip-tools`:** `pip install pip-tools`
2.  **Compile:** `pip-compile requirements.in`
3.  **Install:** `pip install -r requirements.txt`

## Systemd

I've added a basic systemd service template that can be used to run this on startup.

Here are the commands to manage your systemd service:

1.  **Reload:** `sudo systemctl daemon-reload` -  Reload the systemd daemon configuration.  This is necessary after creating or modifying a service file.

2.  **Enable:** `sudo systemctl enable pyInkDisplay.service` - Enable the service to start automatically at boot.

3.  **Start:** `sudo systemctl start pyInkDisplay.service` - Start the service immediately.

4.  **Status:** `sudo systemctl status pyInkDisplay.service` -  Show the current status of the service (running, stopped, errors, etc.).

5.  **Stop:** `sudo systemctl stop pyInkDisplay.service` - Stop the service.

6.  **Disable:** `sudo systemctl disable pyInkDisplay.service` - Prevent the service from starting automatically at boot.

## Similar work
This project was inspired by several e-ink display project including:

* [pycasso](https://github.com/jezs00/pycasso) - System to send AI generated art to an E-Paper display through a Raspberry PI unit.
* [PiArtFrame](https://github.com/runezor/PiArtFrame) - EPD project that displays randomly generated fractal art.

## CI & Raspberry Pi Runner

This repository includes a GitHub Actions workflow that:
- Compiles requirements from `.in` files on Ubuntu (`pip-compile`).
- Runs linting and type checks on Ubuntu using dev-only dependencies.
- Optionally runs tests on a Raspberry Pi self-hosted runner (ARM) using the compiled requirements.

### Set up a Raspberry Pi self-hosted runner (optional)
1. In GitHub, navigate to: Settings → Actions → Runners → New self-hosted runner.
2. Choose Linux and follow the on-screen instructions to download and configure the runner on your Raspberry Pi.
3. Add labels to the runner so the workflow can target it. At minimum:
	- `self-hosted`, `linux`, `arm` (or `arm64` if applicable)
4. Start the runner service.

The workflow includes these jobs:
- Compile (Ubuntu): generates `requirements.txt` and `requirements-dev.txt` artifacts from `.in` sources.
- Lint (Ubuntu): installs dev-only requirements and runs `black`, `isort`, `flake8`, `bandit`, and `mypy` across Python 3.9–3.11.
- Tests (Pi): runs `pytest` only on a self-hosted Raspberry Pi runner, is skipped on pull requests, and marked optional (`continue-on-error`) until a Pi runner is available.
