#!/bin/bash
cd /home/kyle46220/board
source ./google-cloud-sdk/path.bash.inc
gcloud compute ssh board-server --zone=australia-southeast1-a --command 'echo "BYPASS_TOTP=true" | sudo tee -a /opt/backend/.env && sudo systemctl restart board'
