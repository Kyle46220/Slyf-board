#!/bin/bash
set -euo pipefail

echo "==> Sourcing GCP SDK..."
if [ -f "./google-cloud-sdk/path.bash.inc" ]; then
    source ./google-cloud-sdk/path.bash.inc
else
    echo "GCP SDK not found at ./google-cloud-sdk/path.bash.inc. Assuming gcloud is in PATH."
fi

echo "==> Deploying backend/app/media.py and main.py..."
gcloud compute scp backend/app/media.py board-server:/tmp/media.py --zone=australia-southeast1-a
gcloud compute scp backend/app/main.py board-server:/tmp/main.py --zone=australia-southeast1-a

echo "==> Deploying deploy/board.service..."
gcloud compute scp deploy/board.service board-server:/tmp/board.service --zone=australia-southeast1-a

echo "==> Applying fixes securely via SSH..."
gcloud compute ssh board-server --zone=australia-southeast1-a --command "sudo cp /tmp/media.py /opt/backend/app/media.py && sudo cp /tmp/main.py /opt/backend/app/main.py && sudo chown root:root /opt/backend/app/media.py /opt/backend/app/main.py && sudo cp /tmp/board.service /etc/systemd/system/board.service && sudo systemctl daemon-reload && sudo systemctl restart board"

echo "==> Checking board service status..."
gcloud compute ssh board-server --zone=australia-southeast1-a --command "sudo systemctl status board --no-pager"

echo "==> Deployment Complete."
