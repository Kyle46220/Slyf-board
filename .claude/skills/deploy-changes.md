---
name: deploy-changes
description: Deploy changes to board system - backend, frontend, or signal configuration
triggers:
  - "deploy changes"
  - "push to production"
  - "update board"
  - "restart services"
---

# Board Deployment Workflow

## 1. Backend Changes
```bash
# Copy files to GCP
source google-cloud-sdk/path.bash.inc
gcloud compute scp backend/app/<file> board-server:/opt/backend/app/<file> --zone=australia-southeast1-a

# Restart board service
gcloud compute ssh board-server --zone=australia-southeast1-a --command "sudo systemctl restart board"

# Verify
gcloud compute ssh board-server --zone=australia-southeast1-a --command "sudo systemctl status board"
gcloud compute ssh board-server --zone=australia-southeast1-a --command "sudo journalctl -u board -n 20"
```

## 2. Frontend Changes
```bash
# Build locally
cd frontend && npm run build

# Create package
cd dist && tar -czf /tmp/frontend.tar.gz .

# Upload to GCP
source google-cloud-sdk/path.bash.inc
gcloud compute scp /tmp/frontend.tar.gz board-server:/tmp/ --zone=australia-southeast1-a

# Extract and reload nginx
gcloud compute ssh board-server --zone=australia-southeast1-a --command "sudo tar -xzf /tmp/frontend.tar.gz -C /var/www/board/dist/ && sudo chown -R www-data:www-data /var/www/board && sudo systemctl reload nginx"

# Verify
curl -I http://35.213.252.2/
```

## 3. Signal CLI Changes
```bash
# Update service config
gcloud compute ssh board-server --zone=australia-southeast1-a --command "sudo tee /etc/systemd/system/signal-cli.service"
# Paste new config
gcloud compute ssh board-server --zone=australia-southeast1-a --command "sudo systemctl daemon-reload && sudo systemctl restart signal-cli"

# Restart board to reconnect
gcloud compute ssh board-server --zone=australia-southeast1-a --command "sudo systemctl restart board"
```

## 4. Token Generator Changes
```bash
cd token-generator

# Build with secret
VITE_TOTP_SECRET=3MEW54GCJ5ATGUYEOYCGZ27AN6NQMSIZ npm run build

# Deploy to Netlify
netlify deploy --prod --dir=dist --site=qwe-rty.netlify.app

# Verify
curl -s https://qwe-rty.netlify.app/ | grep -o '\d{6}' | head -1
```

## Pre-Deployment Checklist
- [ ] Changes tested locally
- [ ] Environment variables match (TOTP_SECRET, DATABASE_URL)
- [ ] No sensitive data in code
- [ ] Database migrations planned if needed
- [ ] Rollback plan ready

## Post-Deployment Verification
```bash
# Check services
gcloud compute ssh board-server --zone=australia-southeast1-a --command "sudo systemctl status board signal-cli nginx postgresql"

# Test API
curl -s http://35.213.252.2/api/posts | head -5

# Check logs for errors
gcloud compute ssh board-server --zone=australia-southeast1-a --command "sudo journalctl -u board -n 30 | grep -i error"

# Test Signal (send message with fresh TOTP)
```

## Rollback Procedure
```bash
# Backend: revert code and restart
gcloud compute ssh board-server --zone=australia-southeast1-a --command "sudo systemctl restart board"

# Frontend: redeploy previous build
# (Keep previous dist tarballs or use git revert)

# Signal: restore service config
gcloud compute ssh board-server --zone=australia-southeast1-a --command "sudo systemctl restart signal-cli"
```
