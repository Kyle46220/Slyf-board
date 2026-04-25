# Secure Anonymous Board - Agent Documentation
## For AI Agents Working on This Project

---

## Project Overview

**Purpose:** Secure anonymous media-rich bulletin board
**Architecture:** TOTP-authenticated posting via Signal messages, zero-knowledge metadata stripping
**Current Status:** Fully operational on GCP (Google Cloud Platform)

**Key Technology Stack:**
- **Backend:** FastAPI (Python), SQLAlchemy (asyncpg), PostgreSQL 15
- **Frontend:** React 18, Vite, Tailwind CSS 4, React Router
- **Message Platform:** Signal CLI (Java-based)
- **Authentication:** TOTP (Time-based One-Time Password) via pyotp
- **Deployment:** GCP Compute Engine (australia-southeast1)

---

## Current Deployment

### GCP Instance Details
- **Project ID:** board-494314
- **Instance ID:** i-t4n5ingnysc7rl9690yh
- **Public IP:** 35.213.252.2
- **Region:** australia-southeast1 (Sydney)
- **Machine Type:** e2-micro (2 vCPUs, 1GB RAM)
- **OS:** Debian 12 (Bookworm)

### Services Running
- **Signal CLI:** Daemon running for +61485676958
- **PostgreSQL:** Database for posts storage
- **Nginx:** Reverse proxy for frontend and API
- **Board Service:** FastAPI backend on port 8000

### External Services
- **Token Generator:** https://qwe-rty.netlify.app/ (Netlify deployment)
- **Signal Phone:** +61485676958 (registered on GCP)

### Access Methods
- **Frontend:** http://35.213.252.2/
- **API:** http://35.213.252.2/api/
- **SSE Stream:** http://35.213.252.2/api/stream
- **GCP Access:** `gcloud compute ssh board-server --zone=australia-southeast1-a`

---

## Key Components

### 1. Token Generator
**Location:** https://qwe-rty.netlify.app/
**Purpose:** Generates TOTP codes for post authentication
**Technology:** React + Vite + OTPAuth library
**TOTP Secret:** `3MEW54GCJ5ATGUYEOYCGZ27AN6NQMSIZ`
**Update Frequency:** Every 5 minutes (300 seconds)
**Build Command:** `VITE_TOTP_SECRET=$VITE_TOTP_SECRET npm run build`

**Important:** Environment variables must be set at build time in Netlify, not runtime.

### 2. Signal CLI
**Location:** GCP instance `/usr/local/bin/signal-cli`
**Version:** 0.14.3 (native)
**Config Path:** `/var/signal-cli/`
**Socket:** `/var/run/signal-cli/socket`
**Account:** +61485676958 (registered on GCP to avoid Chinese IP blocking)
**Service:** systemd service `signal-cli`

**Key Commands:**
```bash
# Check registration status
signal-cli --config /var/signal-cli listAccounts

# Start daemon
signal-cli -u +61485676958 --config /var/signal-cli daemon --socket /var/run/signal-cli/socket

# Restart service
systemctl restart signal-cli
```

### 3. Backend API
**Location:** `/opt/backend/` on GCP
**Framework:** FastAPI
**Port:** 8000
**Service:** systemd service `board`
**Environment:** `/opt/backend/.env`

**Key Endpoints:**
- `GET /api/posts` - List all posts (rate limited: 1000/hour)
- `GET /api/posts/{hash}` - Get single post (rate limited: 100/hour)
- `GET /api/stream` - SSE stream for real-time updates
- `DELETE /api/admin/posts/{hash}` - Delete post (requires ADMIN_TOKEN)

**Rate Limiting:**
- Posts list: 1000 requests/hour per IP
- Single post: 100 requests/hour per IP
- Uses slowapi with exponential backoff

### 4. Frontend
**Location:** `/var/www/board/dist/` on GCP
**Framework:** React 18 + Vite + Tailwind CSS 4
**Routing:** React Router (hash-based)
**API Client:** `/frontend/src/api.ts`

**Key Features:**
- Masonry grid layout for posts
- Real-time updates via SSE
- Automatic reconnection with exponential backoff (max 10 attempts, 30s max delay)
- 15-second timeout for initial fetch
- Connection status display

### 5. SSE (Server-Sent Events)
**Implementation:** `/opt/backend/app/sse.py`
**Purpose:** Real-time post updates to connected clients
**Features:**
- 30-second timeout with keep-alive pings
- Queue status tracking to prevent dead connections
- Automatic cleanup on disconnect

### 6. Nginx Configuration
**Location:** `/etc/nginx/sites-available/board` on GCP
**Purpose:** Reverse proxy and static file serving
**Key Settings:**
- `/` → Serves frontend from `/var/www/board/dist`
- `/api/` → Proxies to backend (port 8000)
- `/api/stream` → SSE support with no buffering
- `/tokens/` → Redirects to Netlify

---

## Security Architecture

### Zero-Knowledge Design
- **Metadata Stripping:** Sender phone number, name, UUID removed immediately
- **EXIF/Metadata Removal:** All media files stripped of identifying information
- **TOTP Authentication:** Time-based codes valid for 15 minutes (current + previous windows)

### Security Headers
- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: DENY`
- `X-XSS-Protection: 1; mode=block`
- `Referrer-Policy: strict-origin-when-cross-origin`

### Input Validation
- Images: 25MB maximum
- Videos: 100MB maximum  
- Text: 50,000 characters maximum
- OG images: 10MB maximum
- Path traversal protection on all file operations

### CORS Configuration
- Allow: `GET` requests from any origin
- Block: All other methods (POST, PUT, DELETE, etc.)
- Reason: Public read-only board

### Rate Limiting
- Posts: 1000 req/hour per IP
- Single post: 100 req/hour per IP
- Exponential backoff for rate limit violations

---

## Development Guidelines

### Local Development
```bash
# Backend
cd backend
source .venv/bin/activate
pip install -e .
uvicorn app.main:app --reload

# Frontend  
cd frontend
npm run dev

# Token Generator
cd token-generator
VITE_TOTP_SECRET=3MEW54GCJ5ATGUYEOYCGZ27AN6NQMSIZ npm run dev
```

### Environment Variables
**Backend (.env):**
```
DATABASE_URL=postgresql+asyncpg://board:board@localhost/board
TOTP_SECRET=<GENERATE_NEW_SECRET>
ADMIN_TOKEN=<GENERATE_NEW_TOKEN>
SIGNAL_SOCKET=/var/run/signal-cli/socket
SIGNAL_PHONE_NUMBER=+61485676958
MEDIA_DIR=/var/board/media
```

**Token Generator (Netlify):**
- `VITE_TOTP_SECRET` - Must be set in Netlify environment variables

### Database Management
```bash
# Connect to PostgreSQL on GCP
gcloud compute ssh board-server --zone=australia-southeast1-a
sudo -u postgres psql board

# Create tables (if needed)
cd /opt/backend
source venv/bin/activate
python -c "from app.database import engine; from app.models import Base; import asyncio; asyncio.run(Base.metadata.create_all(engine))"
```

### Signal CLI Management
```bash
# Check status
signal-cli --config /var/signal-cli listAccounts

# View logs
journalctl -u signal-cli -f

# Restart service
systemctl restart signal-cli
```

---

## Common Issues and Solutions

### Issue: Token Generator Shows Dashes
**Cause:** VITE_TOTP_SECRET not set at build time in Netlify
**Solution:** Set environment variable in Netlify dashboard:
```bash
netlify env:set VITE_TOTP_SECRET <your_secret> --site=qwe-rty.netlify.app
netlify deploy --prod
```

### Issue: Board Shows "Connection Error"
**Cause:** SSE connection failing or timeout
**Solutions:**
1. Check backend service: `systemctl status board`
2. Check nginx configuration: `sudo nginx -t && sudo systemctl reload nginx`
3. Check backend logs: `journalctl -u board -f`
4. Check Signal CLI: `journalctl -u signal-cli -f`

### Issue: "Failed to Load Posts"
**Cause:** API timeout or database connection issue
**Solutions:**
1. Check database: `sudo systemctl status postgresql`
2. Test API directly: `curl http://localhost:8000/api/posts`
3. Check backend logs: `journalctl -u board -f`
4. Restart board service: `sudo systemctl restart board`

### Issue: Signal Not Receiving Messages
**Cause:** Signal CLI daemon not running or socket issues
**Solutions:**
1. Check Signal service: `systemctl status signal-cli`
2. Check socket exists: `ls -la /var/run/signal-cli/socket`
3. Check Signal logs: `journalctl -u signal-cli -f`
4. Restart Signal: `sudo systemctl restart signal-cli`

### Issue: Connection Drops Intermittently
**Cause:** Network issues or SSE timeout
**Solutions:**
1. Check nginx logs: `sudo tail -f /var/log/nginx/error.log`
2. Check SSE implementation in `backend/app/sse.py`
3. Increase nginx proxy timeout in configuration
4. Check firewall rules: `gcloud compute firewall-rules list`

### Issue: GCP Instance Low Memory (e2-micro)
**Cause:** e2-micro has only 1GB RAM
**Solutions:**
1. Monitor memory usage: `free -h`
2. Consider upgrading to e2-small (2GB RAM) if issues persist
3. Check for memory leaks in Signal CLI or Python processes

---

## Deployment Procedures

### Deploying Frontend Updates
```bash
# Locally build
cd frontend
npm run build

# Create tar file
tar -czf /tmp/frontend-build.tar.gz -C frontend dist

# Copy to GCP
cd ..
source ./google-cloud-sdk/path.bash.inc
gcloud compute scp /tmp/frontend-build.tar.gz board-server:/tmp/ --zone=australia-southeast1-a

# Extract and deploy on GCP
gcloud compute ssh board-server --zone=australia-southeast1-a --command "sudo tar -xzf /tmp/frontend-build.tar.gz -C /var/www/board/ && sudo chown -R www-data:www-data /var/www/board && sudo systemctl reload nginx"
```

### Deploying Backend Updates
```bash
# Copy updated files
source ./google-cloud-sdk/path.bash.inc
gcloud compute scp backend/app/sse.py board-server:/opt/backend/app/sse.py --zone=australia-southeast1-a

# Restart service
gcloud compute ssh board-server --zone=australia-southeast1-a --command "sudo systemctl restart board"

# Check logs
gcloud compute ssh board-server --zone=australia-southeast1-a --command "sudo journalctl -u board -n 30 --no-pager"
```

### Deploying Token Generator Updates
```bash
# Build with secret
cd token-generator
VITE_TOTP_SECRET=3MEW54GCJ5ATGUYEOYCGZ27AN6NQMSIZ npm run build

# Deploy to Netlify
netlify deploy --prod --site=qwe-rty.netlify.app --dir=dist
```

### Updating Nginx Configuration
```bash
# Create new config
# Edit /etc/nginx/sites-available/board on GCP

# Test configuration
sudo nginx -t

# Reload nginx
sudo systemctl reload nginx

# Verify
curl -I http://35.213.252.2/
```

---

## Important Files

### Configuration Files
- `/opt/backend/.env` - Backend environment variables (GCP only)
- `token-generator/.env.local` - Token generator environment (local only)
- `token-generator/netlify.toml` - Netlify build configuration
- `/etc/nginx/sites-available/board` - Nginx configuration (GCP)
- `/etc/systemd/systemd/board.service` - Backend systemd service
- `/etc/systemd/systemd/signal-cli.service` - Signal CLI systemd service

### Source Code Structure
- `backend/app/` - FastAPI application
  - `main.py` - Application setup and middleware
  - `sse.py` - SSE streaming implementation
  - `routers/posts.py` - API endpoints
  - `totp.py` - TOTP validation
  - `security.py` - Security headers
  - `validators.py` - Input validation
- `frontend/src/` - React application
  - `api.ts` - API client and SSE connection
  - `components/` - React components
- `token-generator/src/` - Token generator

### Documentation
- `CLAUDE.md` - Project overview and current status
- `AGENTS.md` - This file (agent documentation)
- `DEPLOY.md` - Deployment procedures
- `FIXES_IMPLEMENTATION.md` - Recent fixes and changes
- `PRD.md` - Product requirements
- `SECURITY_AUDIT_REPORT.md` - Security findings
- `SECURITY_FIXES_IMPLEMENTED.md` - Security fixes
- `TOTP_VALIDATION_COMPLETE.md` - TOTP validation status

---

## Signal Integration Details

### Message Format
Signal messages must follow this format:
```
<TOTP_CODE> <content>
```

**Examples:**
- Text: `123456 Hello world`
- Image: Attach image + `123456 ` (with image attachment)
- Video: Attach video + `123456 ` (with video attachment)
- Link: `123456 https://example.com/article`

### TOTP Validation
- **Code Length:** 6 digits
- **Validity Period:** 15 minutes (current + previous 5-minute windows)
- **Secret:** `3MEW54GCJ5ATGUYEOYCGZ27AN6NQMSIZ`
- **Algorithm:** SHA1
- **Period:** 300 seconds (5 minutes)

### Signal CLI Registration
**Completed:** Phone number +61485676958 registered on GCP
**Method:** Captcha verification + SMS code
**Reason:** GCP Australian IP avoids Chinese IP blocking that was causing 429 rate limiting errors

### Signal Service Management
```bash
# Check if running
systemctl status signal-cli

# Start manually (for debugging)
sudo -u signal signal-cli -u +61485676958 --config /var/signal-cli daemon --socket /var/run/signal-cli/socket

# View logs
journalctl -u signal-cli -f

# Restart service
sudo systemctl restart signal-cli
```

---

## Performance Considerations

### Resource Limits (e2-micro)
- **CPU:** 2 vCPUs (10% billing)
- **RAM:** 1 GB (may need upgrade under heavy load)
- **Disk:** 20GB (plenty for media files)
- **Network:** Standard tier (sufficient for moderate traffic)

### Optimization Tips
1. **Database Connection Pooling:** Configured in database.py
2. **Media File Cleanup:** Implement periodic cleanup of old media files
3. **Caching:** Nginx caching configured for static assets
4. **Rate Limiting:** Prevents API abuse
5. **SSE Efficiency:** Timeout prevents hanging connections

### Monitoring Commands
```bash
# System resources
free -h
df -h

# Service status
systemctl status board signal-cli nginx postgresql

# Process monitoring
ps aux | grep -E 'python|node|signal-cli|nginx'

# Network connections
netstat -tunlp | grep -E '8000|80|22'
```

---

## Git Workflow

### Commit Guidelines
- Use descriptive commit messages
- Reference issues or documentation when applicable
- Include Co-Authored-By for contributions

### Branch Strategy
- **main:** Production deployments
- Feature branches for major changes

### Common Git Commands
```bash
# Check status
git status

# View recent commits
git log --oneline -10

# Create new branch
git checkout -b feature/new-feature

# Push changes
git push origin main

# Pull latest changes
git pull origin main
```

---

## Troubleshooting Commands

### Quick Diagnostics
```bash
# Check all services
systemctl status board signal-cli nginx postgresql

# Check backend logs
journalctl -u board -n 50 --no-pager

# Check nginx logs
sudo tail -f /var/log/nginx/error.log

# Check Signal logs
journalctl -u signal-cli -n 50 --no-pager

# Test API locally
curl -s http://localhost:8000/api/posts | head -20

# Test database
sudo -u postgres psql board -c "SELECT COUNT(*) FROM posts;"

# Check disk space
df -h /var/board/media
```

### Connection Debugging
```bash
# Test API from GCP
curl -v http://localhost:8000/api/posts

# Test SSE stream
curl -N http://localhost:8000/api/stream

# Check nginx proxy
curl -I http://localhost/api/posts

# Test Signal socket
echo '{"jsonrpc":"2.0","method":"listAccounts","id":1}' | nc -U /var/run/signal-cli/socket
```

---

## Emergency Procedures

### Backend Service Down
```bash
# Restart board service
sudo systemctl restart board

# Check logs
sudo journalctl -u board -n 50 --no-pager

# If needed, restart entire stack
sudo systemctl restart board signal-cli nginx postgresql
```

### Signal Service Down
```bash
# Restart Signal CLI
sudo systemctl restart signal-cli

# Check socket
ls -la /var/run/signal-cli/socket

# If socket missing, restart manually
sudo -u signal signal-cli -u +61485676958 --config /var/signal-cli daemon --socket /var/run/signal-cli/socket
```

### Nginx Issues
```bash
# Test configuration
sudo nginx -t

# Reload nginx
sudo systemctl reload nginx

# If needed, restart nginx
sudo systemctl restart nginx
```

### Database Issues
```bash
# Check PostgreSQL status
sudo systemctl status postgresql

# Connect to database
sudo -u postgres psql board

# Check table structure
\dt

# Run queries manually
SELECT COUNT(*) FROM posts;
SELECT * FROM posts ORDER BY created_at DESC LIMIT 10;
```

---

## Contact and Support

### GCP Console
- Project: https://console.cloud.google.com/
- Instance: https://console.cloud.google.com/compute/instances?zone=australia-southeast1

### Netlify
- Site: https://app.netlify.com/sites/qwe-rty
- Environment variables: https://app.netlify.com/sites/qwe-rty/site-settings

### Documentation
- GitHub Repository: Check CLAUDE.md for repository link
- Issue Tracker: Check CLAUDE.md for issue tracker link

---

## Last Updated
**Date:** 2026-04-25
**Deployment:** GCP (australia-southeast1) + Netlify
**Status:** Fully operational

---

## Quick Reference Card

### Board Access
- **URL:** http://35.213.252.2/
- **Token Generator:** https://qwe-rty.netlify.app/
- **API:** http://35.213.252.2/api/

### GCP Access
```bash
cd /home/kyle46220/board
source ./google-cloud-sdk/path.bash.inc
gcloud compute ssh board-server --zone=australia-southeast1-a
```

### Service Management
```bash
systemctl status board signal-cli nginx postgresql
systemctl restart board signal-cli
journalctl -u board -f
```

### Testing Signal Integration
1. Get TOTP code from: https://qwe-rty.netlify.app/
2. Send Signal to: +61485676958
3. Format: `CODE your_message`
4. Check board: http://35.213.252.2/

### Quick Troubleshooting
```bash
# All services status
systemctl status board signal-cli nginx postgresql

# Board service logs
journalctl -u board -n 30

# Test API
curl http://35.213.252.2/api/posts

# Test Signal CLI
signal-cli --config /var/signal-cli listAccounts
```

---

*This AGENTS.md is maintained as part of the Secure Anonymous Board project*
*Last updated: 2026-04-25*
