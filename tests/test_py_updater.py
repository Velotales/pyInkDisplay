from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from pyinkdisplay.pyUpdater import getCurrentTag, getLatestTag, isDevMode


def test_get_current_tag_returns_tag_on_exact_match():
    """Returns the tag string when HEAD is exactly on a tag."""
    with patch("pyinkdisplay.pyUpdater.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(stdout="v1.2.3\n")
        result = getCurrentTag()
    assert result == "v1.2.3"


def test_get_current_tag_returns_none_when_not_on_tag():
    """Returns None when HEAD is not on an exact tag (CalledProcessError)."""
    import subprocess

    with patch(
        "pyinkdisplay.pyUpdater.subprocess.run",
        side_effect=subprocess.CalledProcessError(128, "git"),
    ):
        result = getCurrentTag()
    assert result is None


def test_get_latest_tag_returns_first_tag():
    """Returns the first (latest by semver sort) tag after fetching."""
    with patch("pyinkdisplay.pyUpdater.subprocess.run") as mock_run:
        mock_run.side_effect = [
            MagicMock(),  # git fetch --tags
            MagicMock(stdout="v2.0.0\nv1.2.3\nv1.0.0\n"),  # git tag --sort
        ]
        result = getLatestTag()
    assert result == "v2.0.0"


def test_get_latest_tag_returns_none_on_failure():
    """Returns None when git commands fail."""
    import subprocess

    with patch(
        "pyinkdisplay.pyUpdater.subprocess.run",
        side_effect=subprocess.CalledProcessError(1, "git"),
    ):
        result = getLatestTag()
    assert result is None


def test_is_dev_mode_true_when_marker_exists(tmp_path):
    """Returns True when the dev mode marker file is present."""
    marker = tmp_path / "dev_mode"
    marker.touch()
    assert isDevMode(marker_path=marker) is True


def test_is_dev_mode_false_when_marker_absent(tmp_path):
    """Returns False when the dev mode marker file is not present."""
    marker = tmp_path / "dev_mode"
    assert isDevMode(marker_path=marker) is False


from pyinkdisplay.pyUpdater import applyUpdate, checkAndApplyUpdate, restartService


def test_apply_update_checks_out_tag():
    """Checks out the specified tag via git checkout."""
    with patch("pyinkdisplay.pyUpdater.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock()
        result = applyUpdate("v2.0.0")
    mock_run.assert_called_once_with(
        ["git", "checkout", "v2.0.0"], capture_output=True, check=True
    )
    assert result is True


def test_apply_update_returns_false_on_failure():
    """Returns False if git checkout fails."""
    import subprocess

    with patch(
        "pyinkdisplay.pyUpdater.subprocess.run",
        side_effect=subprocess.CalledProcessError(1, "git"),
    ):
        result = applyUpdate("v2.0.0")
    assert result is False


def test_restart_service_calls_systemctl():
    """Calls sudo systemctl restart with the given service name."""
    with patch("pyinkdisplay.pyUpdater.subprocess.run") as mock_run:
        restartService("pyInkDisplay.service")
    mock_run.assert_called_once_with(
        ["sudo", "systemctl", "restart", "pyInkDisplay.service"],
        capture_output=True,
        check=True,
    )


def test_check_and_apply_update_skips_in_dev_mode(tmp_path):
    """Returns False immediately when dev mode marker is present."""
    marker = tmp_path / "dev_mode"
    marker.touch()
    with patch("pyinkdisplay.pyUpdater.DEV_MODE_MARKER", marker), patch(
        "pyinkdisplay.pyUpdater.getLatestTag"
    ) as mock_latest:
        result = checkAndApplyUpdate()
    assert result is False
    mock_latest.assert_not_called()


def test_check_and_apply_update_applies_when_newer_tag_available(tmp_path):
    """Applies update and restarts service when a newer tag is available."""
    marker = tmp_path / "dev_mode"  # does not exist
    with patch("pyinkdisplay.pyUpdater.DEV_MODE_MARKER", marker), patch(
        "pyinkdisplay.pyUpdater.getCurrentTag", return_value="v1.0.0"
    ), patch("pyinkdisplay.pyUpdater.getLatestTag", return_value="v2.0.0"), patch(
        "pyinkdisplay.pyUpdater.applyUpdate", return_value=True
    ) as mock_apply, patch(
        "pyinkdisplay.pyUpdater.restartService"
    ) as mock_restart:
        result = checkAndApplyUpdate()
    assert result is True
    mock_apply.assert_called_once_with("v2.0.0")
    mock_restart.assert_called_once()


def test_check_and_apply_update_skips_when_up_to_date(tmp_path):
    """Returns False when already on the latest tag."""
    marker = tmp_path / "dev_mode"  # does not exist
    with patch("pyinkdisplay.pyUpdater.DEV_MODE_MARKER", marker), patch(
        "pyinkdisplay.pyUpdater.getCurrentTag", return_value="v2.0.0"
    ), patch("pyinkdisplay.pyUpdater.getLatestTag", return_value="v2.0.0"), patch(
        "pyinkdisplay.pyUpdater.applyUpdate"
    ) as mock_apply:
        result = checkAndApplyUpdate()
    assert result is False
    mock_apply.assert_not_called()


def test_check_and_apply_update_returns_false_when_apply_fails(tmp_path):
    """Returns False when applyUpdate fails even if a newer tag is available."""
    marker = tmp_path / "dev_mode"  # does not exist
    with patch("pyinkdisplay.pyUpdater.DEV_MODE_MARKER", marker), patch(
        "pyinkdisplay.pyUpdater.getCurrentTag", return_value="v1.0.0"
    ), patch("pyinkdisplay.pyUpdater.getLatestTag", return_value="v2.0.0"), patch(
        "pyinkdisplay.pyUpdater.applyUpdate", return_value=False
    ) as mock_apply, patch(
        "pyinkdisplay.pyUpdater.restartService"
    ) as mock_restart:
        result = checkAndApplyUpdate()
    assert result is False
    mock_apply.assert_called_once_with("v2.0.0")
    mock_restart.assert_not_called()


def test_check_and_apply_update_returns_false_when_no_latest_tag(tmp_path):
    """Returns False when getLatestTag returns None."""
    marker = tmp_path / "dev_mode"  # does not exist
    with patch("pyinkdisplay.pyUpdater.DEV_MODE_MARKER", marker), patch(
        "pyinkdisplay.pyUpdater.getCurrentTag", return_value="v1.0.0"
    ), patch("pyinkdisplay.pyUpdater.getLatestTag", return_value=None), patch(
        "pyinkdisplay.pyUpdater.applyUpdate"
    ) as mock_apply:
        result = checkAndApplyUpdate()
    assert result is False
    mock_apply.assert_not_called()
