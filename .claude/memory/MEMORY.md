# Memory Index

Project memory for pyInkDisplay, tier 2: it lives in this repo so one `git pull` brings the
code and its context together. Global memory (who Dane is, how he wants me to work, the
GitHub account rules, timezone) is in `~/.claude/CLAUDE.md` and loads in every session.

- [Pi SSH access](project_pi_ssh.md): pizero at 192.168.1.60 runs the display, server Pi at
  192.168.1.50 runs Docker. SSH needs the explicit `dwalsh@` username. The service runs from
  `/home/dwalsh/pyInkDisplay`, NOT from `~/Development/pyInkDisplay`.
- [Dev deploys run directly, not via systemd](feedback_deploy_dev_mode.md): stop the service
  and run the module over SSH so output streams back, instead of restarting and losing it to
  journald.
- [Service name and Seq-only logs](project_service_name_and_seq_only_logs.md): the unit is
  `pyInkPictureFrame.service`, and app logs go only to Seq, so `journalctl -u` looks empty.
- [Unit file is not auto-deployed](project_unit_file_is_not_auto_deployed.md): the updater only
  checks out tags, so systemd unit changes must be applied to the Pi by hand.
- [Refresh duration tells you if it was real](project_epd_refresh_duration_tells_you_if_it_was_real.md):
  ~62s means the panel actually updated, ~12s is a silent no-op despite the `EPD updated.` log.

Seq logging is not here. It is shared infrastructure and lives in the `_root` memory of
claude-dotfiles, which also records that Seq is reachable from tuckbox but not from pop-os.

Recovered 2026-08-03. These had been orphaned since the personal projects moved into
`personal/`, which changed this project's memory slug and silently stopped them loading.
