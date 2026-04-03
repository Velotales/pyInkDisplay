#!/usr/bin/env bash
# revert.sh — Restore the Pi to the latest git release tag and remove dev mode.
#
# Usage: ./scripts/revert.sh pi@raspberrypi.local

set -euo pipefail

TARGET="${1:-}"
if [[ -z "$TARGET" ]]; then
    echo "Usage: $0 <user@host>"
    exit 1
fi

REMOTE_DIR="/home/pi/pyInkDisplay"
MARKER_PATH="/tmp/pyinkdisplay_dev_mode"
SERVICE_NAME="pyInkDisplay.service"

echo "Reverting $TARGET to latest release tag ..."

ssh "$TARGET" bash <<EOF
set -euo pipefail
cd $REMOTE_DIR
git fetch --tags
LATEST_TAG=\$(git tag --sort=-v:refname | head -1)
if [[ -z "\$LATEST_TAG" ]]; then
    echo "No release tags found. Cannot revert."
    exit 1
fi
echo "Checking out \$LATEST_TAG ..."
git checkout "\$LATEST_TAG"
rm -f $MARKER_PATH
echo "Dev mode marker removed."
sudo systemctl restart $SERVICE_NAME
echo "Service restarted. Now running \$LATEST_TAG."
EOF

echo "Revert complete."
