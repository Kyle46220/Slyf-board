# Secure Anonymous Board

## Purpose
Zero-knowledge anonymous bulletin board. Signal messages + TOTP authentication = secure posting. No sender metadata stored.

## Repo Map
```
board/
├── backend/           # FastAPI + PostgreSQL
├── frontend/          # React + Vite
├── token-generator/   # React + Vite (Netlify)
├── .claude/          # Skills, hooks, configuration
└── docs/             # Current operational documentation
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

## Key Technologies
- **Backend:** FastAPI, SQLAlchemy, PostgreSQL, pyotp
- **Frontend:** React 18, Vite, Tailwind CSS 4
- **Signal:** Signal CLI 0.14.3 (Unix socket + log parsing)
- **Deployment:** GCP Compute (e2-micro), Netlify (token generator)
- **Auth:** TOTP (6-digit, 15-min windows, SHA1)

## Detailed Documentation
For complete project documentation, deployment details, troubleshooting procedures, and operational status, see **[AGENTS.md](AGENTS.md)**.

## Quick Access
- **Board:** http://35.213.252.2/
- **Token Generator:** https://qwe-rty.netlify.app/
- **Signal Phone:** +61485676958

## Reusable Workflows
Use `.claude/skills/` for expert guidance:
- `debug-signal.md` - Signal integration troubleshooting
- `deploy-changes.md` - Deployment procedures
- `test-totp.md` - TOTP authentication testing
