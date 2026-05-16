import json
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

from pyinkdisplay.pyUpdater import (
    applyUpdate,
    checkAndApplyUpdate,
    getCurrentTag,
    getLatestTag,
    isDevMode,
    recordBootAttempt,
    resetBootCounter,
    restartService,
)


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


def test_get_latest_tag_returns_none_when_fetch_fails_and_skips_tag_listing():
    """If git fetch --tags fails, return None and do NOT call git tag.

    Acting on stale local refs after a failed fetch can cause us to skip a
    real update indefinitely (or re-apply a tag we've already applied), so
    the caller must skip the whole update cycle.
    """
    import subprocess

    with patch("pyinkdisplay.pyUpdater.subprocess.run") as mock_run:
        mock_run.side_effect = subprocess.CalledProcessError(128, "git")
        result = getLatestTag()

    assert result is None
    # Only the fetch should have been attempted — never the tag listing.
    assert mock_run.call_count == 1
    args, _ = mock_run.call_args
    assert args[0] == ["git", "fetch", "--tags"]


def test_get_latest_tag_returns_none_when_fetch_raises_generic_exception():
    """A non-CalledProcessError from git fetch (e.g. FileNotFoundError, OSError)
    must also cause us to bail out and never read stale local tags."""
    with patch("pyinkdisplay.pyUpdater.subprocess.run") as mock_run:
        mock_run.side_effect = FileNotFoundError("git not installed")
        result = getLatestTag()

    assert result is None
    assert mock_run.call_count == 1
    args, _ = mock_run.call_args
    assert args[0] == ["git", "fetch", "--tags"]


def test_is_dev_mode_true_when_marker_exists(tmp_path):
    """Returns True when the dev mode marker file is present."""
    marker = tmp_path / "dev_mode"
    marker.touch()
    assert isDevMode(marker_path=marker) is True


def test_is_dev_mode_false_when_marker_absent(tmp_path):
    """Returns False when the dev mode marker file is not present."""
    marker = tmp_path / "dev_mode"
    assert isDevMode(marker_path=marker) is False


def test_apply_update_checks_out_tag():
    """Checks out the specified tag via git checkout AND reinstalls pip deps."""
    import sys

    with patch("pyinkdisplay.pyUpdater.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock()
        result = applyUpdate("v2.0.0")
    assert mock_run.call_count == 2
    checkout_call, pip_call = mock_run.call_args_list
    assert checkout_call.args[0] == ["git", "checkout", "v2.0.0"]
    assert pip_call.args[0] == [sys.executable, "-m", "pip", "install", "-e", "."]
    assert result is True


def test_apply_update_returns_false_when_pip_install_fails():
    """Returns False if git checkout succeeds but pip install fails."""
    import subprocess

    with patch("pyinkdisplay.pyUpdater.subprocess.run") as mock_run:
        mock_run.side_effect = [
            MagicMock(),  # checkout succeeds
            subprocess.CalledProcessError(1, "pip"),  # pip install fails
        ]
        result = applyUpdate("v2.0.0")
    assert result is False
    assert mock_run.call_count == 2


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


def test_check_and_apply_update_skips_restart_when_pip_install_fails(tmp_path):
    """If git checkout succeeds but pip install -e . fails, do NOT restart
    the service — restarting into a broken venv hammers the SD card via
    Restart=on-failure."""
    import subprocess
    import sys

    marker = tmp_path / "dev_mode"  # does not exist
    with patch("pyinkdisplay.pyUpdater.DEV_MODE_MARKER", marker), patch(
        "pyinkdisplay.pyUpdater.getCurrentTag", return_value="v1.0.0"
    ), patch("pyinkdisplay.pyUpdater.getLatestTag", return_value="v2.0.0"), patch(
        "pyinkdisplay.pyUpdater.subprocess.run"
    ) as mock_run, patch(
        "pyinkdisplay.pyUpdater.restartService"
    ) as mock_restart:
        # 1st call: git checkout — succeeds.
        # 2nd call: pip install -e . — fails.
        mock_run.side_effect = [
            MagicMock(),
            subprocess.CalledProcessError(1, "pip"),
        ]
        result = checkAndApplyUpdate()

    assert result is False
    # Both checkout and pip install must have been attempted.
    assert mock_run.call_count == 2
    checkout_call = mock_run.call_args_list[0]
    pip_call = mock_run.call_args_list[1]
    assert checkout_call.args[0] == ["git", "checkout", "v2.0.0"]
    assert pip_call.args[0] == [sys.executable, "-m", "pip", "install", "-e", "."]
    mock_restart.assert_not_called()


def test_check_and_apply_update_restarts_when_checkout_and_pip_install_succeed(
    tmp_path,
):
    """When both git checkout and pip install -e . succeed, the service is
    restarted to pick up the new code."""
    import sys

    marker = tmp_path / "dev_mode"  # does not exist
    with patch("pyinkdisplay.pyUpdater.DEV_MODE_MARKER", marker), patch(
        "pyinkdisplay.pyUpdater.getCurrentTag", return_value="v1.0.0"
    ), patch("pyinkdisplay.pyUpdater.getLatestTag", return_value="v2.0.0"), patch(
        "pyinkdisplay.pyUpdater.subprocess.run"
    ) as mock_run, patch(
        "pyinkdisplay.pyUpdater.restartService"
    ) as mock_restart:
        mock_run.return_value = MagicMock()
        result = checkAndApplyUpdate()

    assert result is True
    assert mock_run.call_count == 2
    pip_call = mock_run.call_args_list[1]
    assert pip_call.args[0] == [sys.executable, "-m", "pip", "install", "-e", "."]
    mock_restart.assert_called_once()


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


# ---------------------------------------------------------------------------
# Boot-attempt rollback watchdog (issue 2.2c)
# ---------------------------------------------------------------------------


def test_record_boot_attempt_creates_new_file_on_first_boot(tmp_path):
    """First boot for a tag: file is created with count=1 and first_attempt set."""
    boot_file = tmp_path / "boot_attempts"
    with patch("pyinkdisplay.pyUpdater.getCurrentTag", return_value="v1.0.0"):
        revert = recordBootAttempt(state_path=boot_file)

    assert revert is False
    assert boot_file.exists()
    state = json.loads(boot_file.read_text())
    assert state["tag"] == "v1.0.0"
    assert state["count"] == 1
    assert "first_attempt" in state


def test_record_boot_attempt_increments_count_for_same_tag(tmp_path):
    """Subsequent boots on the same tag bump the counter."""
    boot_file = tmp_path / "boot_attempts"
    now_iso = datetime.now(timezone.utc).isoformat()
    boot_file.write_text(
        json.dumps({"tag": "v1.0.0", "count": 1, "first_attempt": now_iso})
    )
    with patch("pyinkdisplay.pyUpdater.getCurrentTag", return_value="v1.0.0"):
        revert = recordBootAttempt(state_path=boot_file)

    assert revert is False
    state = json.loads(boot_file.read_text())
    assert state["count"] == 2
    assert state["tag"] == "v1.0.0"


def test_record_boot_attempt_resets_when_tag_changes(tmp_path):
    """A new tag resets count to 1 and updates first_attempt."""
    boot_file = tmp_path / "boot_attempts"
    old_iso = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    boot_file.write_text(
        json.dumps(
            {
                "tag": "v1.0.0",
                "count": 2,
                "first_attempt": old_iso,
                "last_good_tag": "v0.9.0",
            }
        )
    )
    with patch("pyinkdisplay.pyUpdater.getCurrentTag", return_value="v1.1.0"):
        revert = recordBootAttempt(state_path=boot_file)

    assert revert is False
    state = json.loads(boot_file.read_text())
    assert state["tag"] == "v1.1.0"
    assert state["count"] == 1
    # last_good_tag must survive across tag changes so the next failed tag
    # has somewhere safe to roll back to.
    assert state["last_good_tag"] == "v0.9.0"


def test_record_boot_attempt_triggers_revert_at_threshold_within_window(tmp_path):
    """count >= 3 on same tag within 10 minutes triggers a revert."""
    boot_file = tmp_path / "boot_attempts"
    five_min_ago = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
    boot_file.write_text(
        json.dumps(
            {
                "tag": "v1.0.0",
                "count": 2,
                "first_attempt": five_min_ago,
                "last_good_tag": "v0.9.0",
            }
        )
    )
    with patch("pyinkdisplay.pyUpdater.getCurrentTag", return_value="v1.0.0"), patch(
        "pyinkdisplay.pyUpdater.applyUpdate", return_value=True
    ) as mock_apply, patch("pyinkdisplay.pyUpdater.restartService") as mock_restart:
        revert = recordBootAttempt(state_path=boot_file)

    assert revert is True
    mock_apply.assert_called_once_with("v0.9.0")
    mock_restart.assert_called_once()
    # Counter must reset so we don't keep reverting in a loop.
    state = json.loads(boot_file.read_text())
    assert state["count"] == 0


def test_record_boot_attempt_does_not_revert_outside_window(tmp_path):
    """3 attempts spread over more than 10 minutes does NOT trigger revert.

    A device that's been up for hours and just had its third crash isn't
    in a tight crash-loop — don't punish a slow-burn flake."""
    boot_file = tmp_path / "boot_attempts"
    long_ago = (datetime.now(timezone.utc) - timedelta(minutes=30)).isoformat()
    boot_file.write_text(
        json.dumps(
            {
                "tag": "v1.0.0",
                "count": 2,
                "first_attempt": long_ago,
                "last_good_tag": "v0.9.0",
            }
        )
    )
    with patch("pyinkdisplay.pyUpdater.getCurrentTag", return_value="v1.0.0"), patch(
        "pyinkdisplay.pyUpdater.applyUpdate"
    ) as mock_apply, patch("pyinkdisplay.pyUpdater.restartService") as mock_restart:
        revert = recordBootAttempt(state_path=boot_file)

    assert revert is False
    mock_apply.assert_not_called()
    mock_restart.assert_not_called()
    # Slow-burn flake — reset the window so the next 3 in 10 min still trigger.
    state = json.loads(boot_file.read_text())
    assert state["count"] == 1


def test_record_boot_attempt_skips_revert_when_no_last_good_tag(tmp_path):
    """If we hit the threshold but have no last_good_tag, skip the revert
    (we have nowhere to roll back to) but still reset the counter so we
    stop trying."""
    boot_file = tmp_path / "boot_attempts"
    one_min_ago = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
    boot_file.write_text(
        json.dumps(
            {
                "tag": "v1.0.0",
                "count": 2,
                "first_attempt": one_min_ago,
            }
        )
    )
    with patch("pyinkdisplay.pyUpdater.getCurrentTag", return_value="v1.0.0"), patch(
        "pyinkdisplay.pyUpdater.applyUpdate"
    ) as mock_apply, patch("pyinkdisplay.pyUpdater.restartService") as mock_restart:
        revert = recordBootAttempt(state_path=boot_file)

    assert revert is False
    mock_apply.assert_not_called()
    mock_restart.assert_not_called()
    state = json.loads(boot_file.read_text())
    assert state["count"] == 0


def test_reset_boot_counter_records_last_good_tag(tmp_path):
    """After a successful display, count drops to 0 and last_good_tag is set."""
    boot_file = tmp_path / "boot_attempts"
    boot_file.write_text(
        json.dumps(
            {
                "tag": "v1.0.0",
                "count": 2,
                "first_attempt": datetime.now(timezone.utc).isoformat(),
            }
        )
    )
    with patch("pyinkdisplay.pyUpdater.getCurrentTag", return_value="v1.0.0"):
        resetBootCounter(state_path=boot_file)

    state = json.loads(boot_file.read_text())
    assert state["count"] == 0
    assert state["last_good_tag"] == "v1.0.0"


def test_reset_boot_counter_handles_missing_file(tmp_path):
    """resetBootCounter is safe to call when no boot-attempts file exists yet."""
    boot_file = tmp_path / "does_not_exist_yet"
    with patch("pyinkdisplay.pyUpdater.getCurrentTag", return_value="v1.0.0"):
        resetBootCounter(state_path=boot_file)
    assert boot_file.exists()
    state = json.loads(boot_file.read_text())
    assert state["count"] == 0
    assert state["last_good_tag"] == "v1.0.0"


def test_record_boot_attempt_handles_corrupt_state_file(tmp_path):
    """A corrupt state file should not crash startup — it just resets
    bookkeeping for the current tag."""
    boot_file = tmp_path / "boot_attempts"
    boot_file.write_text("this is not json {")
    with patch("pyinkdisplay.pyUpdater.getCurrentTag", return_value="v1.0.0"):
        revert = recordBootAttempt(state_path=boot_file)
    assert revert is False
    state = json.loads(boot_file.read_text())
    assert state["tag"] == "v1.0.0"
    assert state["count"] == 1
