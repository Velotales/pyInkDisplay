# pyInkDisplay — Product Requirements Document

**Date:** 2026-04-03
**Author:** Velotales
**Status:** Approved

---

## Overview

pyInkDisplay is a Raspberry Pi project that fetches an image from a URL and displays it on an e-ink screen, designed primarily to show a Home Assistant dashboard. It runs on a Raspberry Pi Zero W 2 with a Waveshare 7.3" 7-colour e-ink display, powered by a PiSugar 3 battery with RTC wake scheduling.

This PRD captures the next phase of improvements across three areas: power-aware runtime behaviour, a proper deployment and self-update workflow, and expanded observability.

---

## Goals

- Maximise battery life by making the runtime strictly minimal when on battery
- Enable development from a laptop rather than directly on the Pi
- Provide a safe, release-gated self-update mechanism for production
- Give useful visibility into the device state without requiring SSH

## Non-Goals

- Web UI or remote configuration interface
- Multi-display support
- PyPI publishing (structure should support it in future, but not required now)
- Loki logging implementation (kept as a future option in config only)

---

## 1. Power-Aware Runtime

### Problem
The current continuous update loop runs regardless of power source. On battery, the device should do the minimum necessary work and sleep immediately.

### Behaviour

**Battery mode** (PiSugar not on mains power):
1. Wake via RTC alarm
2. Fetch image from configured URL
3. Display image on e-ink
4. Publish telemetry to MQTT
5. Set next RTC alarm
6. Shut down immediately

**USB/Mains mode** (PiSugar on mains power):
1. Wake (or stay running)
2. Fetch and display image
3. Publish telemetry to MQTT
4. Check for a newer release (git tag); if found, update and restart service
5. Re-enter continuous update loop — sleep between intervals, refresh, repeat while powered

### Key Principle
Battery mode is a strict one-shot cycle. USB mode is the existing continuous loop, extended with self-update. Power source is detected via the existing `PiSugarAlarm.isSugarPowered()` method.

---

## 2. Deployment & Self-Update

### Problem
Development currently happens directly on the Pi. There is no workflow for developing on a laptop and deploying to the Pi, and no mechanism for the Pi to update itself in production.

### Dev Testing Workflow

A `scripts/deploy.sh` script rsyncs the working directory from the developer's laptop to the Pi over SSH, then restarts the systemd service.

```bash
./scripts/deploy.sh pi@raspberrypi.local
```

- Excludes `.git`, `__pycache__`, `.venv`, `*.pyc`
- Writes a `dev_mode` marker file to the Pi after sync
- While `dev_mode` is present, auto-update is skipped (to avoid overwriting test code)

### Production Self-Update (USB power only)

- Pi does `git fetch --tags` and compares the latest release tag to the currently checked-out tag
- If a newer tag exists, checks it out and restarts the systemd service
- Skipped entirely in battery mode and when `dev_mode` marker is present

### Reverting to Latest Release

After dev testing, the Pi can be restored to the latest release via:

```bash
./scripts/revert.sh pi@raspberrypi.local
```

- Removes the `dev_mode` marker
- Runs `git fetch --tags && git checkout <latest-tag>`
- Restarts the service

Alternatively, setting `force_revert: true` in `config_local.yaml` triggers a revert on the next USB-power cycle, then clears the flag.

### Promotion Flow

```
edit on laptop → deploy.sh to Pi → test → commit → cut GitHub Release → Pi self-updates on next USB-power cycle
```

### Package Structure

`pyproject.toml` must be complete and correct so the project is installable via `pip install .`. This future-proofs for PyPI publishing without requiring any refactoring.

---

## 3. Observability

Three distinct concerns handled separately: telemetry, alerting, and logging.

### 3.1 MQTT Telemetry (extend existing)

After each cycle, publish a richer status payload alongside the existing battery level. Each field becomes a Home Assistant sensor via MQTT Discovery:

| Field | Description |
|---|---|
| `battery_level` | Battery percentage (existing) |
| `last_update_time` | ISO 8601 timestamp of last successful cycle |
| `image_fetch_status` | `success` or `failure` |
| `power_mode` | `battery` or `usb` |
| `software_version` | Current git tag |
| `update_available` | `true`/`false` (USB mode only) |

### 3.2 Apprise Event Notifications

Use the existing local Apprise container to send push notifications for key events:

- Image fetch failure
- Self-update applied (old tag → new tag)
- Battery below configurable threshold
- Unexpected application error

Configured via an `apprise` section in `config.yaml`:

```yaml
apprise:
  url: "http://localhost:8000"   # Apprise container endpoint
  battery_alert_threshold: 20   # Percentage
```

### 3.3 Configurable Logging

Logging backend is set via `config.yaml`. The logging layer should be abstracted so the backend can be swapped without changing application code.

| Backend | Status | Notes |
|---|---|---|
| `console` | Default | Always available |
| `seq` | In scope | Structured logs to local Seq instance; uses `seqlog` Python library |
| `syslog` | In scope | Remote syslog via `SysLogHandler` |
| `loki` | Future | Not implemented yet; reserved in config schema |

```yaml
logging:
  backend: "console"    # console | seq | syslog | loki
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

---

## Config Schema Changes

Summary of new/changed `config.yaml` fields:

```yaml
# Existing fields unchanged: epd, url, alarmMinutes, noShutdown, mqtt

updater:
  enabled: true              # Enable git-based self-update on USB power
  force_revert: false        # If true, revert to latest release on next USB-power cycle

apprise:
  url: "http://localhost:8000"
  battery_alert_threshold: 20

logging:
  backend: "console"         # console | seq | syslog | loki
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

---

## Out of Scope

- Web UI or dashboard
- Multiple image sources / playlists
- PyPI publishing
- Loki logging implementation
- Multi-Pi fleet management
