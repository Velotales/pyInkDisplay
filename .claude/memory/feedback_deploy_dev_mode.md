---
name: deploy.sh dev mode — run directly, not via service restart
description: When deploying dev builds to the Pi, the script should run directly (not via systemd restart) so console output is visible in the terminal
type: feedback
---

Don't restart the systemd service after a dev deploy. Instead, stop the service and run the Python script directly via SSH so stdout/stderr streams back to the developer's terminal. Config file is sufficient — no need to pass extra CLI args.

**Why:** Restarting the service hides output in journald; direct execution gives immediate, visible feedback during dev iteration.

**How to apply:** In deploy.sh, replace `sudo systemctl restart` with `sudo systemctl stop`, then run `python3 -m pyinkdisplay -c <config>` via SSH as a blocking call. Press Ctrl+C to stop.
