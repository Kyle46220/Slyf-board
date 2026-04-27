# Secure Anonymous Board

## Purpose
Zero-knowledge anonymous bulletin board. Signal messages + TOTP authentication = secure posting. No sender metadata stored.

## Repo Map
```
board/
├── backend/           # FastAPI + PostgreSQL
│   ├── app/
│   │   ├── main.py          # FastAPI app + lifespan
│   │   ├── routers/         # API endpoints
│   │   ├── models.py        # SQLAlchemy models
│   │   ├── database.py      # DB connection
│   │   ├── signal_listener.py # Signal CLI integration
│   │   ├── media.py         # Image/video processing
│   │   ├── totp.py          # TOTP validation
│   │   └── security.py      # Security headers
├── frontend/          # React + Vite
│   ├── src/
│   │   ├── api.ts           # API client + SSE
│   │   ├── components/
│   │   │   ├── Board.tsx    # Main board
│   │   │   ├── PostCard.tsx # Post display
│   │   │   └── SinglePost.tsx
│   │   └── types.ts
├── token-generator/   # React + Vite (Netlify)
└── docs/             # Architecture, ADRs, runbooks
```

## Working Rules

### Code Changes
- **Backend:** Test locally → Deploy to GCP → Restart board service
- **Frontend:** Build → Deploy dist to GCP → Reload nginx
- **Signal:** Never touch GCP Signal CLI phone number
- **TOTP:** Secret must match between backend and token-generator

### Critical Areas (CAUTION)
- `backend/app/signal_listener.py` - Signal integration, don't break log parsing
- `backend/app/totp.py` - Security, 15-minute windows only
- `backend/.env` - Contains secrets, never commit
- Token generator Netlify env vars - Build-time injection required

### Deployment Commands
```bash
# Backend
source google-cloud-sdk/path.bash.inc
gcloud compute ssh board-server --zone=australia-southeast1-a
sudo systemctl restart board

# Frontend
cd frontend && npm run build
cd dist && tar -czf /tmp/frontend.tar.gz .
gcloud compute scp /tmp/frontend.tar.gz board-server:/tmp/
gcloud compute ssh board-server --command "sudo tar -xzf /tmp/frontend.tar.gz -C /var/www/board/dist/"
```

### Debugging
```bash
# Signal CLI logs
sudo journalctl -u signal-cli -f

# Board service logs
sudo journalctl -u board -f

# Database
sudo -u postgres psql board

# Test API
curl http://35.213.252.2/api/posts
```

### TOTP Testing
Current secret: `3MEW54GCJ5ATGUYEOYCGZ27AN6NQMSIZ`
Generate: https://qwe-rty.netlify.app/ or `backend/venv/bin/python -c "import pyotp; print(pyotp.TOTP('3MEW54GCJ5ATGUYEOYCGZ27AN6NQMSIZ').now())"`

## Key Technologies
- **Backend:** FastAPI, SQLAlchemy, PostgreSQL, pyotp
- **Frontend:** React 18, Vite, Tailwind CSS 4
- **Signal:** Signal CLI 0.14.3 (Unix socket + log parsing)
- **Deployment:** GCP Compute (e2-micro), Netlify (token generator)
- **Auth:** TOTP (6-digit, 15-min windows, SHA1)

## Operational Status
- **Board:** http://35.213.252.2/
- **Token Generator:** https://qwe-rty.netlify.app/
- **Signal Phone:** +61485676958 (GCP registered)
- **Database:** PostgreSQL on GCP instance
