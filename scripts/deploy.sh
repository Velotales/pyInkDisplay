#!/usr/bin/env bash
# deploy.sh — Rsync the working directory to a Raspberry Pi and run it directly.
#
# Stops the systemd service and runs pyinkdisplay directly via SSH so that
# console output streams back to your terminal. Press Ctrl+C to stop.
# Run ./scripts/revert.sh to restore the service-managed production setup.
#
# Usage: ./scripts/deploy.sh pi@raspberrypi.local
#        ./scripts/deploy.sh pi@192.168.1.100
#        ./scripts/deploy.sh pi@raspberrypi.local /home/pi/pyInkDisplay config/config_dev.yaml
#
# Default remote directory: /home/pi/pyInkDisplay
# Default config file:      config/config.yaml

set -euo pipefail

TARGET="${1:-}"
if [[ -z "$TARGET" ]]; then
    echo "Usage: $0 <user@host> [remote-dir] [config-file]"
    exit 1
fi

REMOTE_DIR="${2:-/home/pi/pyInkDisplay}"
CONFIG_FILE="${3:-config/config.yaml}"
MARKER_PATH="/tmp/pyinkdisplay_dev_mode"
SERVICE_NAME="pyInkPictureFrame.service"

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

echo "Setting up venv on $TARGET ..."
ssh "$TARGET" "cd $REMOTE_DIR && python3 -m venv .venv && .venv/bin/pip install -q -r requirements.in"

echo "Stopping $SERVICE_NAME on $TARGET ..."
ssh "$TARGET" "sudo systemctl stop $SERVICE_NAME"

echo "Deploy complete. Running directly (Ctrl+C to stop) ..."
ssh "$TARGET" "cd $REMOTE_DIR && .venv/bin/python3 -m pyinkdisplay -c $CONFIG_FILE"

echo ""
echo "Run ./scripts/revert.sh $TARGET to restore the latest release and restart the service."
