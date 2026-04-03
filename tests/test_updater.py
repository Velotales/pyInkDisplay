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
