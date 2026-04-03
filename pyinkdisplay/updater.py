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


def is_dev_mode(marker_path: Optional[Path] = None) -> bool:
    """Return True if the dev mode marker file is present."""
    if marker_path is None:
        marker_path = DEV_MODE_MARKER
    return marker_path.exists()


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

    logger.info(
        "New release available: %s (current: %s). Applying update.", latest, current
    )
    if apply_update(latest):
        restart_service()
        return True

    return False
