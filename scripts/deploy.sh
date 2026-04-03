#!/usr/bin/env bash
# deploy.sh — Rsync the working directory to a Raspberry Pi and run it directly.
#
# Stops the systemd service and runs pyinkdisplay directly via SSH so that
# console output streams back to your terminal. Press Ctrl+C to stop.
# Run ./scripts/revert.sh to restore the service-managed production setup.
#
# Usage: ./scripts/deploy.sh pi@raspberrypi.local
#        ./scripts/deploy.sh pi@192.168.1.100
#
# Default remote directory: /home/pi/pyInkDisplay
# Override with a second argument: ./deploy.sh pi@host /home/myuser/pyInkDisplay

set -euo pipefail

TARGET="${1:-}"
if [[ -z "$TARGET" ]]; then
    echo "Usage: $0 <user@host> [remote-dir]"
    exit 1
fi

REMOTE_DIR="${2:-/home/pi/pyInkDisplay}"
MARKER_PATH="/tmp/pyinkdisplay_dev_mode"
SERVICE_NAME="pyInkDisplay.service"

echo "Deploying to $TARGET:$REMOTE_DIR ..."

rsync -avz --delete \
    --exclude='.git' \
    --exclude='__pycache__' \
    --exclude='*.pyc' \
    --exclude='.venv' \
    --exclude='*.egg-info' \
    --exclude='.mypy_cache' \
    --exclude='.pytest_cache' \
    . "$TARGET:$REMOTE_DIR"

echo "Writing dev mode marker on $TARGET ..."
ssh "$TARGET" "touch $MARKER_PATH"

echo "Stopping $SERVICE_NAME on $TARGET ..."
ssh "$TARGET" "sudo systemctl stop $SERVICE_NAME"

echo "Deploy complete. Running directly (Ctrl+C to stop) ..."
ssh "$TARGET" "cd $REMOTE_DIR && python3 -m pyinkdisplay -c config/config.yaml"

echo ""
echo "Run ./scripts/revert.sh $TARGET to restore the latest release and restart the service."
