# pyInkDisplay

My need was to display a Home Assistant dashboard on an e-ink display

![image](https://github.com/user-attachments/assets/8d20875c-5dad-4961-9875-134c08eebf63)

[![Python CI](https://github.com/Velotales/pyInkDisplay/actions/workflows/tests.yml/badge.svg)](https://github.com/Velotales/pyInkDisplay/actions/workflows/tests.yml)

## Details

This project fetches an image from a URL and displays it on an e-ink display. It was built primarily to show a Home Assistant dashboard, and runs on a Raspberry Pi Zero W 2 with a Waveshare 7.3" 7-colour e-ink display, powered by a PiSugar 3 battery with RTC wake scheduling.

---

## Power-Aware Runtime

The runtime behaves differently depending on whether the Pi is on battery or USB/mains power.

**Battery mode** — one-shot cycle:
1. Wake via RTC alarm
2. Fetch and display image
3. Publish telemetry to MQTT
4. Set next RTC alarm
5. Shut down immediately

**USB/mains mode** — continuous loop:
1. Fetch and display image
2. Publish telemetry to MQTT
3. Check for a newer release tag; if found, update and restart
4. Sleep for `alarmMinutes`, then repeat

Power source is detected via the PiSugar. Battery mode is strict: no update checks, no looping.

---

## Image Fallback

If the configured `url` fails to return an image, the display falls back through a chain rather than showing nothing:

1. **Image of the day** — fetches from a configured provider (iNaturalist birds or NASA APOD)
2. **Disk image** — loads a local file from `fallback_file`
3. **Generated default** — a plain black image with error text

Configure in `config.yaml`:

```yaml
url: "http://your-home-assistant/dashboard.png"
fallback_file: null           # e.g. "/home/pi/fallback.png"
image_of_the_day:
  provider: null              # inaturalist | nasa_apod | null (disabled)
  nasa_apod_key: "DEMO_KEY"   # only needed for nasa_apod
```

An Apprise notification is sent when the primary fetch fails (see [Notifications](#notifications)).

---

## Home Assistant & MQTT

MQTT telemetry is published after each cycle using Home Assistant's MQTT Discovery, so sensors appear in Home Assistant automatically with no manual YAML configuration.

### Sensors

| Sensor | Description |
|--------|-------------|
| `battery_level` | PiSugar battery percentage |
| `last_update_time` | ISO 8601 timestamp of last successful cycle |
| `image_fetch_status` | `success` or `failure` |
| `power_mode` | `battery` or `usb` |
| `software_version` | Currently running git tag |
| `update_available` | `true` / `false` (USB mode only) |

### Configuration

```yaml
mqtt:
  host: "localhost"
  port: 1883
  topic: "homeassistant/sensor/pisugar_battery/state"
  username: ""   # optional
  password: ""   # optional
```

### Home Assistant Setup

1. Enable the [MQTT integration](https://www.home-assistant.io/integrations/mqtt/) and connect it to your broker.
2. Start the pyInkPictureFrame service — sensors will appear automatically.

---

## Notifications

Push notifications are sent via a local [Apprise](https://github.com/caronc/apprise) container for:

- Image fetch failure
- Self-update applied (old tag → new tag)
- Battery below threshold
- Unexpected application error

```yaml
apprise:
  url: "http://localhost:8000"
  battery_alert_threshold: 20   # notify when battery drops below this %
```

---

## Self-Update

When running on USB power, the Pi checks for a newer git release tag on each cycle. If one exists, it checks out the new tag and restarts the systemd service automatically.

Self-update is skipped when:
- On battery power
- Dev mode marker is present (set by `deploy.sh`)
- `updater.enabled: false` in config

To force a revert to the latest release tag on the next USB-power cycle, set `updater.force_revert: true` in `config.yaml`.

---

## Dev Deploy Workflow

Development happens on a laptop and is deployed to the Pi over SSH.

### Local config

Create `config/config_local.yaml` with your real settings (it's gitignored). `deploy.sh` picks it up automatically:

```yaml
url: "http://192.168.1.x:8123/path/to/dashboard.png"
mqtt:
  host: "192.168.1.x"
  username: "myuser"
  password: "mypassword"
```

### Deploy and run

```bash
./scripts/deploy.sh pi@raspberrypi.local
# or with a custom config:
./scripts/deploy.sh pi@raspberrypi.local /home/pi/pyInkDisplay config/my_config.yaml
```

This will:
1. Rsync the working directory to the Pi (excluding `.git`, `.venv`, `__pycache__`, etc.)
2. Set up a venv on the Pi and install from `requirements.in` (skipped if unchanged)
3. Stop the `pyInkPictureFrame.service`
4. Run `pyinkdisplay` directly — output streams back to your terminal
5. Write a dev-mode marker that disables auto-update while testing

Press Ctrl+C to stop. The remote Python process is killed cleanly.

### Revert to latest release

```bash
./scripts/revert.sh pi@raspberrypi.local
```

Removes the dev-mode marker, checks out the latest git release tag, and restarts the service.

---

## Logging

The logging backend is configurable in `config.yaml`:

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

---

## Libraries

This project uses Rob Weber's [Omni-EPD](https://github.com/robweber/omni-epd/) for display support, so it should work with most e-ink displays. Display settings (mode, palette, brightness, contrast, sharpness) are configured in `waveshare_epd.epd7in3f.ini` at the project root — omni-epd picks this up automatically.

I also made use of the [PiSugar python library](https://github.com/PiSugar/pisugar-python) to control the PiSugar and set the next wakeup interval.

Dependencies are managed with `requirements.in`. The deploy script installs directly from it on the Pi (with checksum caching to skip reinstalls when nothing has changed). For local development:

1. **Install `pip-tools`:** `pip install pip-tools`
2. **Compile:** `pip-compile requirements.in`
3. **Install:** `pip install -r requirements.txt`

---

## Systemd

The service file is at `config/pyInkPictureFrame.service`.

```bash
sudo systemctl daemon-reload
sudo systemctl enable pyInkPictureFrame.service
sudo systemctl start pyInkPictureFrame.service
sudo systemctl status pyInkPictureFrame.service
sudo systemctl stop pyInkPictureFrame.service
sudo systemctl disable pyInkPictureFrame.service
```

---

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
- **Compile** (Ubuntu): generates `requirements.txt` and `requirements-dev.txt` artifacts from `.in` sources.
- **Lint** (Ubuntu): installs dev-only requirements and runs `black`, `isort`, `flake8`, `bandit`, and `mypy` across Python 3.9–3.11.
- **Tests** (Pi): runs `pytest` only on a self-hosted Raspberry Pi runner, is skipped on pull requests, and marked optional (`continue-on-error`) until a Pi runner is available.

---

## Similar Work

* [pycasso](https://github.com/jezs00/pycasso) — System to send AI generated art to an E-Paper display through a Raspberry PI unit.
* [PiArtFrame](https://github.com/runezor/PiArtFrame) — EPD project that displays randomly generated fractal art.
