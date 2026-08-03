---
name: Pi SSH access
description: How to SSH into the two Raspberry Pis in this project
type: project
originSessionId: bd0ffdc6-f25a-444e-a41a-22200439769f
---
There are two Pis:

- **192.168.1.60** — Pi Zero running pyInkDisplay (the e-ink display project). This is the primary target for deployments and logs. Machine name in Seq: `pizero`.
- **192.168.1.50** — Server Pi running Docker (Seq, Home Assistant, Traefik, etc.)

SSH requires the `dwalsh` username explicitly: `ssh dwalsh@192.168.1.60` (not `pi` or bare hostname — SSH agent key lookup requires the username to match).

The project on pizero lives at `/home/dwalsh/pyInkDisplay` — this is where the service runs from and where you should rsync to. There is also a `/home/dwalsh/Development/pyInkDisplay` but the service does NOT use that path.

Service name: `pyInkPictureFrame.service`

**How to apply:** Use `ssh 192.168.1.60` for pyInkDisplay work, `ssh 192.168.1.50` for server/Docker work. Deploy with rsync to `dwalsh@192.168.1.60:/home/dwalsh/pyInkDisplay`.
