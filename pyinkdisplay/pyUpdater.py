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

import logging
import subprocess
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

DEV_MODE_MARKER = Path("/tmp/pyinkdisplay_dev_mode")  # nosec B108


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


def isDevMode(marker_path: Optional[Path] = None) -> bool:
    """Return True if the dev mode marker file is present."""
    if marker_path is None:
        marker_path = DEV_MODE_MARKER
    return marker_path.exists()


def applyUpdate(latest_tag: str) -> bool:
    """Checkout the given tag. Returns True on success, False on failure."""
    try:
        subprocess.run(["git", "checkout", latest_tag], capture_output=True, check=True)
        logger.info("Checked out tag %s successfully.", latest_tag)
        # Note: stale .pyc bytecode may persist after checkout; this is acceptable
        # because the systemd service restart replaces the running process
        return True
    except subprocess.CalledProcessError as e:
        logger.error("Failed to checkout tag %s: %s", latest_tag, e)
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
