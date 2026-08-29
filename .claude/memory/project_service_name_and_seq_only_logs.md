---
name: project_service_name_and_seq_only_logs
description: The systemd unit is pyInkPictureFrame.service, and app logs go only to Seq, so journalctl looks empty
metadata:
  type: project
---

On pizero the unit is **`pyInkPictureFrame.service`**, not `pyinkdisplay.service`. Guessing
the latter returns "Unit could not be found" and wastes a round trip.

`config_local.yaml` sets `logging.backend: "seq"`, so **journald holds almost nothing**: just
systemd's own "Started ..." line. Every application log (power mode, image fetch, EPD update,
shutdown reason) goes to Seq and nowhere else. Debugging this service from `journalctl -u`
alone will look like the process is silent when it is actually logging normally.

Query the app's real logs from tuckbox (see the Seq reference in claude-dotfiles `_root`):

```bash
curl -s -H "X-Seq-ApiKey: FzHQ3OWzSganMBbDPEj8" \
  "http://seq.home/api/events?count=150&filter=MachineName%20%3D%20'pizero'"
```

Message text lives in `MessageTemplateTokens[].Text`, **not** in `MessageTemplate` (which comes
back empty for these events). Timestamps are UTC, so add two hours for SAST.

Use journald for boot-level facts instead: `journalctl --list-boots` and service start/stop
ordering. Related: [[project_pi_ssh]], [[project_unit_file_is_not_auto_deployed]].
