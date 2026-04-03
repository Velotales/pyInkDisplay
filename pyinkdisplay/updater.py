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
