# pyInkDisplay

My need was to display a Home Assistant dashboard on an e-ink display

![image](https://github.com/user-attachments/assets/8d20875c-5dad-4961-9875-134c08eebf63)

[![Python CI](https://github.com/Velotales/pyInkDisplay/actions/workflows/tests.yml/badge.svg)](https://github.com/Velotales/pyInkDisplay/actions/workflows/tests.yml)

## Details
This project takes an image, either locally or remotely, and displays it on an e-ink display.

This was written for a Raspberry Pi Zero W 2, using Waveshare's 7.3 inch 7 color e-ink display.

To make it a true digital photo frame, I added a PiSugar 3 to provide battery power and the ability to power the Raspberry Pi Zero on with RTC.

## Power-Aware Runtime

Since this runs on battery, I wanted to make sure it does the minimum necessary work when not plugged in.

**On battery** it does a single one-shot cycle — wake, fetch image, display it, publish telemetry, set the next RTC alarm, and shut down. No looping, no update checks.

**On USB/mains power** it runs a continuous loop — fetch and display, publish telemetry, check for a newer release and update if one is found, then sleep for `alarmMinutes` and repeat.

## Quiet Hours

To avoid waking the display overnight, you can configure a quiet window. When the Pi wakes during this period it skips the display update entirely, sets the RTC alarm to fire at the end of the window, and shuts back down.

```yaml
quiet_hours:
  start: "22:00"   # 24-hour format
  end: "07:00"     # spans midnight automatically
```

The window can span midnight (e.g. `22:00` to `07:00`) or stay within a single day (e.g. `02:00` to `06:00`). The end time is exclusive — a wake at exactly `07:00` will proceed normally.

## Image Fallback

If the configured URL can't be reached, rather than showing a blank screen I've set up a fallback chain:

1. **Image of the day** — fetches from a configured provider (iNaturalist birds or NASA APOD)
2. **A file on disk** — a local image you specify in `fallback_file`
3. **Generated default** — a plain black image with an error message, so at least something appears

```yaml
url: "http://your-home-assistant/dashboard.png"
fallback_file: null           # e.g. "/home/pi/fallback.png"
image_of_the_day:
  provider: null              # inaturalist | nasa_apod | null (disabled)
  nasa_apod_key: "DEMO_KEY"   # only needed for nasa_apod
```

## Home Assistant & MQTT Integration

This project supports publishing telemetry to Home Assistant via MQTT, using Home Assistant's MQTT Discovery feature. This means Home Assistant will automatically create sensors with no manual YAML configuration.

### Sensors

After each cycle the following are published:

| Sensor | Description |
|--------|-------------|
| `battery_level` | PiSugar battery percentage |
| `last_update_time` | ISO 8601 timestamp of last successful cycle |
| `image_fetch_status` | `success` or `failure` |
| `power_mode` | `battery` or `usb` |
| `software_version` | Currently running git tag |
| `update_available` | `true` / `false` (USB mode only) |

### Configuration
Edit your `config/config.yaml` (or `config/config_local.yaml` for local, uncommitted settings) to include the `mqtt` section:

```yaml
mqtt:
  host: "localhost"   # MQTT broker address
  port: 1883
  topic: "homeassistant/sensor/pisugar_battery/state"
  username: ""        # optional
  password: ""        # optional
```

### Home Assistant Setup
1. Make sure the [MQTT integration](https://www.home-assistant.io/integrations/mqtt/) is enabled in Home Assistant and connected to your broker.
2. Start the pyInkPictureFrame service. Sensors will appear automatically in Home Assistant.
3. Telemetry updates after each display refresh.

### Troubleshooting
- Check the logs for MQTT connection errors.
- Use the provided `mqtt_test.py` to verify your MQTT broker and Home Assistant discovery setup.

## Notifications

I've wired up [Apprise](https://github.com/caronc/apprise) for push notifications on key events:

- Image fetch failure
- Self-update applied (old tag → new tag)
- Battery below a configurable threshold
- Unexpected application error

```yaml
apprise:
  url: "http://localhost:8000"
  battery_alert_threshold: 20   # notify when battery drops below this %
```

## Self-Update

When running on USB power, the Pi checks for a newer git release tag on each cycle. If one exists it checks it out and restarts the service automatically. This means I can cut a GitHub release and the Pi will pick it up on its own next time it's plugged in.

Self-update is skipped on battery, when the dev-mode marker is present, or when `updater.enabled: false`.

If something goes wrong and I need to roll back, setting `updater.force_revert: true` in config will revert to the latest release tag on the next USB-power cycle.

## Dev Deploy Workflow

I got tired of SSHing into the Pi to test changes, so I wrote a deploy script that rsyncs from my laptop and runs the app directly so I can see the output.

### Local config

I keep my real settings (IP addresses, MQTT credentials, etc.) in `config/config_local.yaml`, which is gitignored. The deploy script picks it up automatically:

```yaml
url: "http://192.168.1.x:8123/path/to/dashboard.png"
mqtt:
  host: "192.168.1.x"
  username: "myuser"
  password: "mypassword"
```

### Deploying

```bash
./scripts/deploy.sh pi@raspberrypi.local
# or override the remote dir and config:
./scripts/deploy.sh pi@raspberrypi.local /home/pi/pyInkDisplay config/my_config.yaml
```

This rsyncs the project, sets up the venv (skipping pip if `requirements.in` hasn't changed), stops the service, and runs `pyinkdisplay` directly so output streams back to my terminal. Press Ctrl+C to stop — it kills the remote process cleanly.

While the dev-mode marker is present, self-update is disabled so it won't overwrite my test code.

### Reverting

```bash
./scripts/revert.sh pi@raspberrypi.local
```

Removes the dev-mode marker, checks out the latest release tag, and restarts the service.

## Logging

I've made the logging backend configurable so I can point it at Seq or syslog without changing any code:

```yaml
logging:
  backend: "console"   # console | seq | syslog | loki (future)
  level: "INFO"
  seq:
    url: "http://localhost:5341"
  syslog:
    host: "localhost"
    port: 514
```

## Libraries
This project pulls in Rob Weber's [Omni-EPD](https://github.com/robweber/omni-epd/), so it "should" work with most e-ink displays. Display settings (mode, palette, brightness, contrast, sharpness) live in `waveshare_epd.epd7in3f.ini` at the project root — omni-epd picks this up automatically based on the EPD type in config.

I also made use of the [PiSugar python library](https://github.com/PiSugar/pisugar-python) to control the PiSugar and set the next wakeup interval.

I found this to be quite a dependency nightmare, so included in the repo is a `requirements.in`. To use, follow this, preferably in a virtual environment:

1.  **Install `pip-tools`:** `pip install pip-tools`
2.  **Compile:** `pip-compile requirements.in`
3.  **Install:** `pip install -r requirements.txt`

(The deploy script handles this automatically on the Pi, installing directly from `requirements.in` and caching a checksum so it skips the install if nothing has changed.)

## Systemd

I've added a basic systemd service file at `config/pyInkPictureFrame.service` that can be used to run this on startup.

Here are the commands to manage your systemd service:

1.  **Reload:** `sudo systemctl daemon-reload` — Reload the systemd daemon configuration. This is necessary after creating or modifying a service file.

2.  **Enable:** `sudo systemctl enable pyInkPictureFrame.service` — Enable the service to start automatically at boot.

3.  **Start:** `sudo systemctl start pyInkPictureFrame.service` — Start the service immediately.

4.  **Status:** `sudo systemctl status pyInkPictureFrame.service` — Show the current status of the service (running, stopped, errors, etc.).

5.  **Stop:** `sudo systemctl stop pyInkPictureFrame.service` — Stop the service.

6.  **Disable:** `sudo systemctl disable pyInkPictureFrame.service` — Prevent the service from starting automatically at boot.

## Similar work
This project was inspired by several e-ink display projects including:

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
