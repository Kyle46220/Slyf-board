# Secure Anonymous Board - Project Documentation

## Project Overview
Secure anonymous media-rich bulletin board. Users post via Signal messages with TOTP authentication. Posts display in reverse-chronological masonry grid. Zero-knowledge architecture - sender metadata stripped immediately.

## Architecture
- **Token Generator**: Client-side TOTP generator (http://localhost:5173)
- **Backend**: FastAPI/Python + PostgreSQL (http://47.84.234.54:8000)
- **Frontend**: React + Tailwind CSS (http://47.84.234.54/)
- **Message Ingestion**: Signal CLI (NOT YET CONFIGURED)

## Current Status
✅ Backend deployed and working
✅ Frontend deployed and working  
✅ TOTP authentication validated
✅ Security fixes implemented
🔲 Signal CLI installation pending
🔲 Signal phone registration pending
🔲 Full integration testing pending

## Key Technologies
- **Backend**: FastAPI, SQLAlchemy, asyncpg, pyotp, slowapi
- **Frontend**: React 18, Vite, Tailwind CSS 4, React Router
- **Database**: PostgreSQL 15
- **Message Platform**: Signal (via signal-cli)
- **Media Processing**: Pillow, ffmpeg (images/video), BeautifulSoup (OG scraping)

## Security Architecture
- TOTP codes valid for 15 minutes (current + previous 5-min windows)
- Sender metadata stripped immediately (phone number, name, UUID)
- EXIF/metadata removed from all media
- Rate limiting: 1000 req/hour for posts, 100 req/hour for single post
- Input validation: 25MB images, 100MB videos, 50k chars text
- Security headers: CSP, X-Frame-Options, X-Content-Type-Options
- CORS: GET requests from any origin (public board)
- Path traversal protection on file operations

## VPS Details
- **Provider**: Alibaba Cloud
- **IP**: 47.84.234.54
- **SSH**: `ssh -i /tmp/board-keypair.pem root@47.84.234.54`
- **OS**: CentOS/RHEL (based on yum usage in docs)
- **Services**: nginx, board (backend), signal-cli (pending)

## Environment Variables
Backend `.env`:
```
TOTP_SECRET=3MEW54GCJ5ATGUYEOYCGZ27AN6NQMSIZ
ADMIN_TOKEN=localdevtoken
DATABASE_URL=postgresql+asyncpg://board@/board?host=/tmp
MEDIA_DIR=/tmp/board_media
```

## Project Structure
```
board/
├── backend/              # FastAPI backend
│   ├── app/
│   │   ├── main.py      # FastAPI app + middleware
│   │   ├── config.py    # Settings
│   │   ├── database.py  # DB connection
│   │   ├── models.py    # SQLAlchemy models
│   │   ├── routers/     # API endpoints
│   │   ├── media.py     # Media processing
│   │   ├── sse.py       # Server-sent events
│   │   ├── security.py  # Security headers
│   │   └── validators.py # Input validation
│   └── pyproject.toml   # Dependencies
├── frontend/            # React frontend
│   └── src/
│       ├── api.ts       # API client + SSE
│       └── components/  # React components
├── token-generator/     # TOTP generator
│   └── src/main.ts      # Client-side TOTP
├── deploy/              # Deployment scripts
├── nginx/               # Nginx configs
└── docs/                # Documentation
```

## API Endpoints
- `GET /api/posts` - List all posts (reverse chronological)
- `GET /api/posts/{hash}` - Get single post
- `GET /api/stream` - SSE stream for real-time updates
- `DELETE /api/admin/posts/{hash}` - Delete post (requires auth)

## Post Formats
Signal message format: `<TOTP_CODE> <content>`

- **Text**: `123456 Hello world` (Markdown supported)
- **Image**: Attach image + caption `123456 optional caption`
- **Video**: Attach video + caption `123456 optional caption`  
- **Link**: `123456 https://example.com/article` (OG tags scraped)

## Development Workflow
1. Backend: `cd backend && source .venv/bin/activate && uvicorn app.main:app --reload`
2. Frontend: `cd frontend && npm run dev`
3. Token Generator: `cd token-generator && npm run dev`

## Deployment Workflow
1. Build frontend: `cd frontend && npm run build`
2. Build token-gen: `cd token-generator && VITE_TOTP_SECRET=<secret> npm run build`
3. Deploy to VPS: `scp -r dist/* root@47.84.234.54:/var/www/board/`
4. Restart services: `systemctl restart board`

## Current Priority
**Complete Signal integration:**
1. Install Signal CLI on VPS
2. Register Signal phone number
3. Configure backend to connect to Signal socket
4. Test message ingestion
5. Verify posts appear on board

## Important Notes
- TOTP secret must match between backend and token-generator
- Signal number should be dedicated (can receive spam)
- No logs of sender identity (privacy-first design)
- Media files stored in `/var/board/media/` on VPS
- Database backups: `pg_dump board > backup.sql`
- Signal config backups: `/var/signal-cli/`

## Known Issues
- Signal CLI not yet installed (blocking feature)
- Need to rotate exposed secrets (see SECRETS.md)
- TOTP window kept at 15min per PRD (security trade-off)

## References
- PRD.md - Product requirements
- DEPLOY.md - Deployment guide
- SIGNAL_SETUP_GUIDE.md - Signal integration steps
- SECURITY_AUDIT_REPORT.md - Security analysis
- SECURITY_FIXES_IMPLEMENTED.md - Security fixes applied