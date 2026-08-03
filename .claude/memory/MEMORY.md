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

Seq logging is not here. It is shared infrastructure and lives in the `_root` memory of
claude-dotfiles, which also records that Seq is reachable from tuckbox but not from pop-os.

Recovered 2026-08-03. These had been orphaned since the personal projects moved into
`personal/`, which changed this project's memory slug and silently stopped them loading.
