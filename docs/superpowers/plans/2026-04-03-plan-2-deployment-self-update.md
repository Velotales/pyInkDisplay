# Deployment & Self-Update Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a git-based self-update mechanism (USB power only) and a deploy/revert script pair for deploying dev builds to the Pi without committing to git.

**Architecture:** A new `updater.py` module handles all git operations (fetch tags, compare, checkout, restart service). A `dev_mode` marker file written by `deploy.sh` suppresses auto-update while dev code is on the Pi. `revert.sh` removes the marker and restores the latest release tag. The updater is wired into the USB-power path in `pyInkPictureFrame.py` before the continuous loop.

**Tech Stack:** Python 3.8+, `subprocess`, `pathlib`, `unittest.mock`, bash

**Prerequisites:** Plan 1 (power-aware runtime) must be complete.

---

### Task 1: Core tag inspection functions in `updater.py`

**Files:**
- Create: `pyinkdisplay/updater.py`
- Create: `tests/test_updater.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_updater.py`:

```python
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from pyinkdisplay.updater import get_current_tag, get_latest_tag, is_dev_mode


def test_get_current_tag_returns_tag_on_exact_match():
    """Returns the tag string when HEAD is exactly on a tag."""
    with patch("pyinkdisplay.updater.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(stdout="v1.2.3\n")
        result = get_current_tag()
    assert result == "v1.2.3"


def test_get_current_tag_returns_none_when_not_on_tag():
    """Returns None when HEAD is not on an exact tag (CalledProcessError)."""
    import subprocess
    with patch("pyinkdisplay.updater.subprocess.run", side_effect=subprocess.CalledProcessError(128, "git")):
        result = get_current_tag()
    assert result is None


def test_get_latest_tag_returns_first_tag():
    """Returns the first (latest by semver sort) tag after fetching."""
    with patch("pyinkdisplay.updater.subprocess.run") as mock_run:
        mock_run.side_effect = [
            MagicMock(),  # git fetch --tags
            MagicMock(stdout="v2.0.0\nv1.2.3\nv1.0.0\n"),  # git tag --sort
        ]
        result = get_latest_tag()
    assert result == "v2.0.0"


def test_get_latest_tag_returns_none_on_failure():
    """Returns None when git commands fail."""
    import subprocess
    with patch("pyinkdisplay.updater.subprocess.run", side_effect=subprocess.CalledProcessError(1, "git")):
        result = get_latest_tag()
    assert result is None


def test_is_dev_mode_true_when_marker_exists(tmp_path):
    """Returns True when the dev mode marker file is present."""
    marker = tmp_path / "dev_mode"
    marker.touch()
    assert is_dev_mode(marker_path=marker) is True


def test_is_dev_mode_false_when_marker_absent(tmp_path):
    """Returns False when the dev mode marker file is not present."""
    marker = tmp_path / "dev_mode"
    assert is_dev_mode(marker_path=marker) is False
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_updater.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'pyinkdisplay.updater'`

- [ ] **Step 3: Implement `get_current_tag`, `get_latest_tag`, and `is_dev_mode`**

Create `pyinkdisplay/updater.py`:

```python
"""
Git-based self-update logic for pyInkDisplay.

Checks for newer release tags and applies updates when on USB power.
Skips updates when a dev_mode marker file is present (written by deploy.sh).
"""

import logging
import subprocess
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

DEV_MODE_MARKER = Path("/tmp/pyinkdisplay_dev_mode")


def get_current_tag() -> Optional[str]:
    """Return the current git tag if HEAD is exactly on a tag, else None."""
    try:
        result = subprocess.run(
            ["git", "describe", "--tags", "--exact-match"],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError:
        return None


def get_latest_tag() -> Optional[str]:
    """Fetch remote tags and return the latest semver-sorted tag, or None on failure."""
    try:
        subprocess.run(["git", "fetch", "--tags"], capture_output=True, check=True)
        result = subprocess.run(
            ["git", "tag", "--sort=-v:refname"],
            capture_output=True,
            text=True,
            check=True,
        )
        tags = [t.strip() for t in result.stdout.strip().splitlines() if t.strip()]
        return tags[0] if tags else None
    except subprocess.CalledProcessError as e:
        logger.error("Failed to get latest tag: %s", e)
        return None


def is_dev_mode(marker_path: Path = DEV_MODE_MARKER) -> bool:
    """Return True if the dev mode marker file is present."""
    return marker_path.exists()
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_updater.py::test_get_current_tag_returns_tag_on_exact_match tests/test_updater.py::test_get_current_tag_returns_none_when_not_on_tag tests/test_updater.py::test_get_latest_tag_returns_first_tag tests/test_updater.py::test_get_latest_tag_returns_none_on_failure tests/test_updater.py::test_is_dev_mode_true_when_marker_exists tests/test_updater.py::test_is_dev_mode_false_when_marker_absent -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add pyinkdisplay/updater.py tests/test_updater.py
git commit -m "feat: add updater module — tag inspection and dev mode check"
```

---

### Task 2: `apply_update`, `restart_service`, and `check_and_apply_update`

**Files:**
- Modify: `pyinkdisplay/updater.py`
- Modify: `tests/test_updater.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_updater.py`:

```python
from pyinkdisplay.updater import apply_update, check_and_apply_update, restart_service


def test_apply_update_checks_out_tag():
    """Checks out the specified tag via git checkout."""
    with patch("pyinkdisplay.updater.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock()
        result = apply_update("v2.0.0")
    mock_run.assert_called_once_with(
        ["git", "checkout", "v2.0.0"], capture_output=True, check=True
    )
    assert result is True


def test_apply_update_returns_false_on_failure():
    """Returns False if git checkout fails."""
    import subprocess
    with patch("pyinkdisplay.updater.subprocess.run", side_effect=subprocess.CalledProcessError(1, "git")):
        result = apply_update("v2.0.0")
    assert result is False


def test_restart_service_calls_systemctl():
    """Calls sudo systemctl restart with the given service name."""
    with patch("pyinkdisplay.updater.subprocess.run") as mock_run:
        restart_service("pyInkDisplay.service")
    mock_run.assert_called_once_with(
        ["sudo", "systemctl", "restart", "pyInkDisplay.service"], check=True
    )


def test_check_and_apply_update_skips_in_dev_mode(tmp_path):
    """Returns False immediately when dev mode marker is present."""
    marker = tmp_path / "dev_mode"
    marker.touch()
    with patch("pyinkdisplay.updater.DEV_MODE_MARKER", marker), \
         patch("pyinkdisplay.updater.get_latest_tag") as mock_latest:
        result = check_and_apply_update()
    assert result is False
    mock_latest.assert_not_called()


def test_check_and_apply_update_applies_when_newer_tag_available(tmp_path):
    """Applies update and restarts service when a newer tag is available."""
    marker = tmp_path / "dev_mode"  # does not exist
    with patch("pyinkdisplay.updater.DEV_MODE_MARKER", marker), \
         patch("pyinkdisplay.updater.get_current_tag", return_value="v1.0.0"), \
         patch("pyinkdisplay.updater.get_latest_tag", return_value="v2.0.0"), \
         patch("pyinkdisplay.updater.apply_update", return_value=True) as mock_apply, \
         patch("pyinkdisplay.updater.restart_service") as mock_restart:
        result = check_and_apply_update()
    assert result is True
    mock_apply.assert_called_once_with("v2.0.0")
    mock_restart.assert_called_once()


def test_check_and_apply_update_skips_when_up_to_date(tmp_path):
    """Returns False when already on the latest tag."""
    marker = tmp_path / "dev_mode"  # does not exist
    with patch("pyinkdisplay.updater.DEV_MODE_MARKER", marker), \
         patch("pyinkdisplay.updater.get_current_tag", return_value="v2.0.0"), \
         patch("pyinkdisplay.updater.get_latest_tag", return_value="v2.0.0"), \
         patch("pyinkdisplay.updater.apply_update") as mock_apply:
        result = check_and_apply_update()
    assert result is False
    mock_apply.assert_not_called()
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_updater.py -k "apply_update or restart_service or check_and_apply" -v
```

Expected: FAIL with `ImportError`

- [ ] **Step 3: Implement the remaining functions in `updater.py`**

Append to `pyinkdisplay/updater.py`:

```python
def apply_update(latest_tag: str) -> bool:
    """Checkout the given tag. Returns True on success, False on failure."""
    try:
        subprocess.run(
            ["git", "checkout", latest_tag], capture_output=True, check=True
        )
        logger.info("Checked out tag %s successfully.", latest_tag)
        return True
    except subprocess.CalledProcessError as e:
        logger.error("Failed to checkout tag %s: %s", latest_tag, e)
        return False


def restart_service(service_name: str = "pyInkDisplay.service") -> None:
    """Restart the named systemd service via sudo systemctl."""
    try:
        subprocess.run(["sudo", "systemctl", "restart", service_name], check=True)
        logger.info("Service %s restarted.", service_name)
    except subprocess.CalledProcessError as e:
        logger.error("Failed to restart service %s: %s", service_name, e)


def check_and_apply_update() -> bool:
    """
    Check for a newer release tag and apply it if available.

    Skips entirely when the dev mode marker file is present.
    Returns True if an update was applied (and the service is restarting).
    """
    if is_dev_mode():
        logger.info("Dev mode active — skipping update check.")
        return False

    current = get_current_tag()
    latest = get_latest_tag()

    if not latest:
        logger.warning("Could not determine latest tag — skipping update.")
        return False

    if current == latest:
        logger.info("Already on latest tag %s — no update needed.", current)
        return False

    logger.info("New release available: %s (current: %s). Applying update.", latest, current)
    if apply_update(latest):
        restart_service()
        return True

    return False
```

- [ ] **Step 4: Run all updater tests**

```bash
pytest tests/test_updater.py -v
```

Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add pyinkdisplay/updater.py tests/test_updater.py
git commit -m "feat: add apply_update, restart_service, check_and_apply_update"
```

---

### Task 3: `scripts/deploy.sh`

**Files:**
- Create: `scripts/deploy.sh`

- [ ] **Step 1: Create the scripts directory and `deploy.sh`**

```bash
mkdir -p scripts
```

Create `scripts/deploy.sh`:

```bash
#!/usr/bin/env bash
# deploy.sh — Rsync the working directory to a Raspberry Pi and run it directly.
#
# Stops the systemd service and runs pyinkdisplay directly via SSH so that
# console output streams back to your terminal. Press Ctrl+C to stop.
# Run ./scripts/revert.sh to restore the service-managed production setup.
#
# Usage: ./scripts/deploy.sh pi@raspberrypi.local
#        ./scripts/deploy.sh pi@192.168.1.100
#        ./scripts/deploy.sh pi@raspberrypi.local /home/pi/pyInkDisplay config/config_dev.yaml
#
# Default remote directory: /home/pi/pyInkDisplay
# Default config file:      config/config.yaml

set -euo pipefail

TARGET="${1:-}"
if [[ -z "$TARGET" ]]; then
    echo "Usage: $0 <user@host> [remote-dir] [config-file]"
    exit 1
fi

REMOTE_DIR="${2:-/home/pi/pyInkDisplay}"
CONFIG_FILE="${3:-config/config.yaml}"
MARKER_PATH="/tmp/pyinkdisplay_dev_mode"
SERVICE_NAME="pyInkDisplay.service"

echo "Deploying to $TARGET:$REMOTE_DIR ..."

rsync -avz --delete \
    --exclude='.git' \
    --exclude='__pycache__' \
    --exclude='*.pyc' \
    --exclude='.venv' \
    --exclude='*.egg-info' \
    --exclude='.mypy_cache' \
    --exclude='.pytest_cache' \
    . "$TARGET:$REMOTE_DIR"

echo "Writing dev mode marker on $TARGET ..."
ssh "$TARGET" "touch $MARKER_PATH"

echo "Stopping $SERVICE_NAME on $TARGET ..."
ssh "$TARGET" "sudo systemctl stop $SERVICE_NAME"

echo "Deploy complete. Running directly (Ctrl+C to stop) ..."
ssh "$TARGET" "cd $REMOTE_DIR && python3 -m pyinkdisplay -c $CONFIG_FILE"

echo ""
echo "Run ./scripts/revert.sh $TARGET to restore the latest release and restart the service."
```

- [ ] **Step 2: Make executable**

```bash
chmod +x scripts/deploy.sh
```

- [ ] **Step 3: Verify the script is executable and has no syntax errors**

```bash
bash -n scripts/deploy.sh && echo "Syntax OK"
```

Expected: `Syntax OK`

- [ ] **Step 4: Commit**

```bash
git add scripts/deploy.sh
git commit -m "feat: add deploy.sh for rsync-based Pi deployment with direct execution"
```

---

### Task 4: `scripts/revert.sh`

**Files:**
- Create: `scripts/revert.sh`

- [ ] **Step 1: Create `scripts/revert.sh`**

Create `scripts/revert.sh`:

```bash
#!/usr/bin/env bash
# revert.sh — Restore the Pi to the latest git release tag and remove dev mode.
#
# Usage: ./scripts/revert.sh pi@raspberrypi.local

set -euo pipefail

TARGET="${1:-}"
if [[ -z "$TARGET" ]]; then
    echo "Usage: $0 <user@host>"
    exit 1
fi

REMOTE_DIR="/home/pi/pyInkDisplay"
MARKER_PATH="/tmp/pyinkdisplay_dev_mode"
SERVICE_NAME="pyInkDisplay.service"

echo "Reverting $TARGET to latest release tag ..."

ssh "$TARGET" bash <<EOF
set -euo pipefail
cd $REMOTE_DIR
git fetch --tags
LATEST_TAG=\$(git tag --sort=-v:refname | head -1)
if [[ -z "\$LATEST_TAG" ]]; then
    echo "No release tags found. Cannot revert."
    exit 1
fi
echo "Checking out \$LATEST_TAG ..."
git checkout "\$LATEST_TAG"
rm -f $MARKER_PATH
echo "Dev mode marker removed."
sudo systemctl restart $SERVICE_NAME
echo "Service restarted. Now running \$LATEST_TAG."
EOF

echo "Revert complete."
```

- [ ] **Step 2: Make executable**

```bash
chmod +x scripts/revert.sh
```

- [ ] **Step 3: Verify syntax**

```bash
bash -n scripts/revert.sh && echo "Syntax OK"
```

Expected: `Syntax OK`

- [ ] **Step 4: Commit**

```bash
git add scripts/revert.sh
git commit -m "feat: add revert.sh to restore Pi to latest release tag"
```

---

### Task 5: Wire updater into the USB-power path

**Files:**
- Modify: `pyinkdisplay/pyInkPictureFrame.py`
- Modify: `tests/test_py_ink_picture_frame.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_py_ink_picture_frame.py`:

```python
from pyinkdisplay.pyInkPictureFrame import pyInkPictureFrame


def test_pyInkPictureFrame_checks_for_update_when_usb_powered():
    """When on USB power, check_and_apply_update is called before the continuous loop."""
    with patch("pyinkdisplay.pyInkPictureFrame.parseArguments") as mock_args, \
         patch("pyinkdisplay.pyInkPictureFrame.loadConfig", return_value={}), \
         patch("pyinkdisplay.pyInkPictureFrame.mergeArgsAndConfig", return_value={
             "epd": "waveshare_epd.epd7in3f", "url": "http://example.com",
             "alarmMinutes": 20, "noShutdown": True, "logging": None,
         }), \
         patch("pyinkdisplay.pyInkPictureFrame.setupLogging"), \
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
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_py_ink_picture_frame.py::test_pyInkPictureFrame_checks_for_update_when_usb_powered -v
```

Expected: FAIL

- [ ] **Step 3: Wire updater into `pyInkPictureFrame.py`**

Add the import at the top of `pyinkdisplay/pyInkPictureFrame.py`:

```python
from .updater import check_and_apply_update
```

In `pyInkPictureFrame()`, update the USB-power branch to call `check_and_apply_update()` before the loop. Replace the `if alarmManager.isSugarPowered():` block with:

```python
        if alarmManager.isSugarPowered():
            logging.info("PiSugar is powered. Publishing battery level.")
            publishBatteryLevel(alarmManager, mqttConfig)
            logging.info("Checking for updates...")
            updated = check_and_apply_update()
            if updated:
                # Service is restarting — exit cleanly
                logging.info("Update applied. Service is restarting.")
                return
            continuousEpdUpdateLoop(
                displayManager,
                alarmManager,
                merged["url"],
                merged["alarmMinutes"],
                mqttConfig,
            )
        else:
            logging.info("PiSugar is on battery. Running one-shot battery mode.")
            runBatteryMode(alarmManager, merged["alarmMinutes"], mqttConfig, merged["noShutdown"])
```

- [ ] **Step 4: Run all tests**

```bash
pytest -v
```

Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add pyinkdisplay/pyInkPictureFrame.py tests/test_py_ink_picture_frame.py
git commit -m "feat: call check_and_apply_update in USB-power path"
```

---

### Task 6a: `force_revert` config flag

**Files:**
- Modify: `pyinkdisplay/pyInkPictureFrame.py`
- Modify: `tests/test_py_ink_picture_frame.py`
- Modify: `config/config.yaml`

Setting `force_revert: true` in `config_local.yaml` triggers a revert to the latest release tag on the next USB-power cycle, then clears the flag. This lets you recover from a dev-mode deploy without running `revert.sh`.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_py_ink_picture_frame.py`:

```python
def test_pyInkPictureFrame_reverts_when_force_revert_set():
    """When force_revert is true in config, calls apply_update with latest tag and clears the flag."""
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
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_py_ink_picture_frame.py::test_pyInkPictureFrame_reverts_when_force_revert_set -v
```

Expected: FAIL

- [ ] **Step 3: Implement force_revert in `pyInkPictureFrame.py`**

Add imports at the top:

```python
from .updater import apply_update, check_and_apply_update, get_latest_tag, restart_service
```

In `pyInkPictureFrame()`, inside the USB-power branch, before the `check_and_apply_update()` call, add:

```python
            forceRevert = updaterConfig.get("force_revert", False)
            if forceRevert:
                logging.info("force_revert is set. Reverting to latest release tag.")
                latestTag = get_latest_tag()
                if latestTag:
                    apply_update(latestTag)
                    restart_service()
                    logging.info("Reverted to %s. Service is restarting.", latestTag)
                    return
                else:
                    logging.warning("force_revert set but no tags found — skipping revert.")
```

- [ ] **Step 4: Run all tests**

```bash
pytest -v
```

Expected: all PASS

- [ ] **Step 5: Add `force_revert` to `config.yaml`**

Update the `updater` section in `config/config.yaml`:

```yaml
updater:
  enabled: true        # Set to false to disable auto-update entirely
  force_revert: false  # Set to true to revert to latest release on next USB-power cycle
```

- [ ] **Step 6: Commit**

```bash
git add pyinkdisplay/pyInkPictureFrame.py tests/test_py_ink_picture_frame.py config/config.yaml
git commit -m "feat: support force_revert config flag to restore latest release on USB boot"
```

---

### Task 6: Add `updater` config section

**Files:**
- Modify: `config/config.yaml`
- Modify: `pyinkdisplay/pyInkPictureFrame.py`
- Modify: `tests/test_py_ink_picture_frame.py`

- [ ] **Step 1: Update `config/config.yaml`** to add the updater section:

```yaml
updater:
  enabled: true    # Set to false to disable auto-update entirely
```

- [ ] **Step 2: Write the failing test**

Add to `tests/test_py_ink_picture_frame.py`:

```python
def test_pyInkPictureFrame_skips_update_when_disabled_in_config():
    """Skips update check when updater.enabled is false in config."""
    with patch("pyinkdisplay.pyInkPictureFrame.parseArguments") as mock_args, \
         patch("pyinkdisplay.pyInkPictureFrame.loadConfig", return_value={"updater": {"enabled": False}}), \
         patch("pyinkdisplay.pyInkPictureFrame.mergeArgsAndConfig", return_value={
             "epd": "waveshare_epd.epd7in3f", "url": "http://example.com",
             "alarmMinutes": 20, "noShutdown": True, "logging": None,
         }), \
         patch("pyinkdisplay.pyInkPictureFrame.setupLogging"), \
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
```

- [ ] **Step 3: Run test to verify it fails**

```bash
pytest tests/test_py_ink_picture_frame.py::test_pyInkPictureFrame_skips_update_when_disabled_in_config -v
```

Expected: FAIL

- [ ] **Step 4: Respect `updater.enabled` in `pyInkPictureFrame()`**

In `pyInkPictureFrame()`, read the updater config and gate the update check:

```python
    updaterConfig = config.get("updater", {}) if config else {}
    updaterEnabled = updaterConfig.get("enabled", True)
```

Then replace `updated = check_and_apply_update()` with:

```python
            if updaterEnabled:
                logging.info("Checking for updates...")
                updated = check_and_apply_update()
                if updated:
                    logging.info("Update applied. Service is restarting.")
                    return
            else:
                logging.info("Auto-update is disabled via config.")
```

- [ ] **Step 5: Run all tests**

```bash
pytest -v
```

Expected: all PASS

- [ ] **Step 6: Commit**

```bash
git add pyinkdisplay/pyInkPictureFrame.py config/config.yaml tests/test_py_ink_picture_frame.py
git commit -m "feat: add updater.enabled config flag to disable auto-update"
```
