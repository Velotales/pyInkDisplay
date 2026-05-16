"""
Git-based self-update logic for pyInkDisplay.

MIT License

Copyright (c) 2026 Velotales

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

Checks for newer release tags and applies updates when on USB power.
Skips updates when a dev_mode marker file is present (written by deploy.sh).
"""

import json
import logging
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

DEV_MODE_MARKER = Path("/tmp/pyinkdisplay_dev_mode")  # nosec B108

# Rollback watchdog tunables. Three rapid boots on the same tag within ten
# minutes is the line between "transient flake" and "this release is broken".
BOOT_ATTEMPT_THRESHOLD = 3
BOOT_ATTEMPT_WINDOW = timedelta(minutes=10)
_PRIMARY_BOOT_STATE_PATH = Path("/var/lib/pyinkdisplay/boot_attempts")
_FALLBACK_BOOT_STATE_PATH = Path.home() / ".pyinkdisplay_boot_attempts"


def _defaultBootStatePath() -> Path:
    """Pick a writable state-file path at runtime.

    Prefer /var/lib/pyinkdisplay (persistent, system-managed), fall back to
    a dotfile in $HOME when the system path isn't writable (e.g. dev
    machine, or running as a user without write access)."""
    try:
        _PRIMARY_BOOT_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        if os.access(_PRIMARY_BOOT_STATE_PATH.parent, os.W_OK):
            return _PRIMARY_BOOT_STATE_PATH
    except OSError:
        pass
    return _FALLBACK_BOOT_STATE_PATH


def _readBootState(state_path: Path) -> dict:
    """Read JSON boot state; return empty dict on any error."""
    try:
        return json.loads(state_path.read_text())
    except (json.JSONDecodeError, OSError) as e:
        if not isinstance(e, FileNotFoundError):
            logger.warning(
                "Boot-attempt state file %s unreadable (%s) — resetting.",
                state_path,
                e,
            )
        return {}


def _writeBootState(state_path: Path, state: dict) -> None:
    """Best-effort write of JSON boot state. Logs but does not raise on failure."""
    try:
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text(json.dumps(state))
    except OSError as e:
        logger.error("Failed to write boot-attempt state to %s: %s", state_path, e)


def getCurrentTag() -> Optional[str]:
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


def getLatestTag() -> Optional[str]:
    """Fetch remote tags and return the latest semver-sorted tag, or None on failure.

    Always fetches first — if the fetch fails (non-zero exit or any exception
    such as git missing/network down), we bail out without reading the local
    tag list. Acting on stale refs can cause us to skip a real update
    indefinitely or re-apply a tag we've already applied.
    """
    try:
        subprocess.run(["git", "fetch", "--tags"], capture_output=True, check=True)
    except Exception as e:
        logger.warning(
            "git fetch --tags failed (%s); skipping update cycle to avoid"
            " acting on stale local tags.",
            e,
        )
        return None

    try:
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


def isDevMode(marker_path: Optional[Path] = None) -> bool:
    """Return True if the dev mode marker file is present."""
    if marker_path is None:
        marker_path = DEV_MODE_MARKER
    return marker_path.exists()


def applyUpdate(latest_tag: str) -> bool:
    """Checkout the given tag and reinstall pip deps.

    Returns True only if both `git checkout` and `pip install -e .` succeed.
    If pip install fails the caller MUST NOT restart the service — a new
    release that pulls in a missing dependency would crash on import and
    `Restart=on-failure` would burn the SD card in a tight restart loop.
    """
    try:
        subprocess.run(["git", "checkout", latest_tag], capture_output=True, check=True)
        logger.info("Checked out tag %s successfully.", latest_tag)
        # Note: stale .pyc bytecode may persist after checkout; this is acceptable
        # because the systemd service restart replaces the running process
    except subprocess.CalledProcessError as e:
        logger.error("Failed to checkout tag %s: %s", latest_tag, e)
        return False

    try:
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "-e", "."],
            capture_output=True,
            check=True,
        )
        logger.info("Reinstalled pip dependencies for %s.", latest_tag)
        return True
    except subprocess.CalledProcessError as e:
        logger.error(
            "pip install -e . failed after checkout of %s: %s."
            " NOT restarting service to avoid crash-loop.",
            latest_tag,
            e,
        )
        return False


def restartService(service_name: str = "pyInkPictureFrame.service") -> None:
    """Restart the named systemd service via sudo systemctl."""
    try:
        subprocess.run(
            ["sudo", "systemctl", "restart", service_name],
            capture_output=True,
            check=True,
        )
        logger.info("Service %s restarted.", service_name)
    except subprocess.CalledProcessError as e:
        logger.error("Failed to restart service %s: %s", service_name, e)


def checkAndApplyUpdate() -> bool:
    """
    Check for a newer release tag and apply it if available.

    Skips entirely when the dev mode marker file is present.
    Returns True if an update was applied (and the service is restarting).
    """
    if isDevMode():
        logger.info("Dev mode active — skipping update check.")
        return False

    current = getCurrentTag()
    latest = getLatestTag()

    if not latest:
        logger.warning("Could not determine latest tag — skipping update.")
        return False

    if current == latest:
        logger.info("Already on latest tag %s — no update needed.", current)
        return False

    logger.info(
        "New release available: %s (current: %s). Applying update.", latest, current
    )
    if applyUpdate(latest):
        restartService()
        return True

    return False


def recordBootAttempt(state_path: Optional[Path] = None) -> bool:
    """Record one startup attempt for the currently checked-out tag.

    Returns True when this attempt crossed the BOOT_ATTEMPT_THRESHOLD on the
    same tag within BOOT_ATTEMPT_WINDOW — i.e. we appear to be in a tight
    crash-loop on a broken release. In that case the function ALSO triggers
    a revert: if a previous `last_good_tag` is on file we call
    `applyUpdate(last_good_tag)` and `restartService()`; otherwise we just
    reset the counter (no known-good target to roll back to).

    State is persisted as JSON to `state_path` (default: /var/lib/pyinkdisplay
    or ~/.pyinkdisplay_boot_attempts when /var/lib isn't writable):
        {
          "tag":            <current tag or "dev">,
          "count":          <int>,
          "first_attempt":  <ISO-8601 UTC timestamp>,
          "last_good_tag":  <tag last known to reach a successful display>,
        }
    """
    if state_path is None:
        state_path = _defaultBootStatePath()

    current = getCurrentTag() or "dev"
    state = _readBootState(state_path)
    last_good_tag = state.get("last_good_tag")
    now = datetime.now(timezone.utc)

    same_tag = state.get("tag") == current
    if same_tag:
        first_attempt_iso = state.get("first_attempt")
        try:
            first_attempt = datetime.fromisoformat(str(first_attempt_iso))
        except (TypeError, ValueError):
            first_attempt = now
        within_window = (now - first_attempt) <= BOOT_ATTEMPT_WINDOW
        if within_window:
            new_count = int(state.get("count", 0)) + 1
        else:
            # Outside the window — treat as a fresh series so a slow-burn
            # flake doesn't eventually trip the watchdog after days of uptime.
            new_count = 1
            first_attempt = now
    else:
        # New tag — start a fresh window.
        new_count = 1
        first_attempt = now

    if new_count >= BOOT_ATTEMPT_THRESHOLD:
        if last_good_tag:
            logger.error(
                "Boot attempt %d for tag %s within %s — rolling back to %s.",
                new_count,
                current,
                BOOT_ATTEMPT_WINDOW,
                last_good_tag,
            )
            # Reset counter BEFORE the revert: applyUpdate will restart us
            # back into this function, and we must not see count >= threshold
            # on the next boot of the same (now-good) tag.
            _writeBootState(
                state_path,
                {
                    "tag": current,
                    "count": 0,
                    "first_attempt": now.isoformat(),
                    "last_good_tag": last_good_tag,
                },
            )
            if applyUpdate(last_good_tag):
                restartService()
            return True

        logger.error(
            "Boot attempt %d for tag %s within %s but no last_good_tag"
            " on file — cannot revert.",
            new_count,
            current,
            BOOT_ATTEMPT_WINDOW,
        )
        _writeBootState(
            state_path,
            {
                "tag": current,
                "count": 0,
                "first_attempt": now.isoformat(),
            },
        )
        return False

    new_state = {
        "tag": current,
        "count": new_count,
        "first_attempt": first_attempt.isoformat(),
    }
    if last_good_tag:
        new_state["last_good_tag"] = last_good_tag
    _writeBootState(state_path, new_state)
    return False


def resetBootCounter(state_path: Optional[Path] = None) -> None:
    """Clear the boot-attempt counter and record the current tag as known-good.

    Call this after a successful end-to-end display update — at that point
    the running release has demonstrably reached the application's happy
    path, so it's safe to mark as the rollback target for future broken
    releases."""
    if state_path is None:
        state_path = _defaultBootStatePath()

    current = getCurrentTag() or "dev"
    now = datetime.now(timezone.utc)
    _writeBootState(
        state_path,
        {
            "tag": current,
            "count": 0,
            "first_attempt": now.isoformat(),
            "last_good_tag": current,
        },
    )
