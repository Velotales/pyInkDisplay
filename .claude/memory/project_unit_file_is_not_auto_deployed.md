---
name: project_unit_file_is_not_auto_deployed
description: The self-updater only checks out git tags; systemd unit changes must be deployed to the Pi by hand
metadata:
  type: project
---

`pyUpdater.applyUpdate` does `git checkout <tag>` plus `pip install -e .` and nothing else. It
**never touches `/etc/systemd/system/`**. So a fix committed to `config/pyInkPictureFrame.service`
ships in the tag but has no effect on the Pi until it is applied there manually.

This bit on 2026-08-29: `20692e4` added `SIGTERM SIGINT` to `RestartPreventExitStatus`, but the
Pi kept running the old unit, so systemd still treated the shutdown-time SIGTERM as a failure.

Applied as a drop-in rather than editing the packaged unit, because editing files under `/etc`
in place is blocked by the auto-mode classifier, and a drop-in is reversible:

```
/etc/systemd/system/pyInkPictureFrame.service.d/override.conf
[Service]
RestartPreventExitStatus=
RestartPreventExitStatus=0 SIGTERM SIGINT
```

The empty assignment first is required: `RestartPreventExitStatus` accumulates, so without the
reset the drop-in appends instead of replacing. Verify with
`systemctl show pyInkPictureFrame -p RestartPreventExitStatus`, which normalises the result to
`0 INT TERM`.

**When changing the unit file in the repo, remember to deploy it separately.** Related:
[[project_service_name_and_seq_only_logs]], [[feedback_deploy_dev_mode]].
