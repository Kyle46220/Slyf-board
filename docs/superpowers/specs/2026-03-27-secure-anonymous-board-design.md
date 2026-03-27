# Design Spec: Secure Anonymous Notice Board
**Date:** 2026-03-27
**Status:** Approved

---

## 1. Overview

A strictly anonymous, media-rich digital bulletin board. Trusted posters submit content via Signal using a TOTP code for authentication. The backend strips all sender metadata before persisting. The public frontend displays posts in a real-time masonry grid.

---

## 2. Architecture

Single FastAPI monolith on a 1984.is VPS. Four logical components:

1. **Token Generator (Website A)** — static HTML/JS page served by Nginx. Generates 6-digit TOTP client-side using the `otpauth` JS library with a shared secret injected via `VITE_TOTP_SECRET` environment variable at build time (not committed to version control). No server calls. URL shared privately with trusted posters only.

2. **signal-cli daemon** — systemd service registered to a dedicated Signal number (prepaid SIM for anonymity). Exposes a JSON-RPC socket that FastAPI connects to on startup.

3. **FastAPI backend** — single Python process handling:
   - Signal message ingestion via signal-cli JSON-RPC
   - TOTP validation (`pyotp`)
   - Metadata stripping
   - Media processing (`Pillow`, `ffmpeg`)
   - OG tag scraping (`httpx` + `BeautifulSoup`)
   - PostgreSQL persistence
   - SSE endpoint for real-time frontend updates
   - Admin delete endpoint (Bearer token auth)

4. **React frontend (Website B)** — static build served by Nginx. Masonry grid with SSE-driven real-time updates, lazy loading, and direct post links.

### Data Flow

```
Poster → Signal message (TOTP + content)
       → signal-cli daemon (JSON-RPC socket)
       → FastAPI: validate TOTP
           → invalid: discard silently, no DB write
           → valid: strip sender metadata
                  → write stub row to PostgreSQL
                  → process media synchronously
                  → update row with final paths
                  → broadcast SSE event
                  → React board prepends new post
```

Note: The SSE broadcast is held until media processing completes. The frontend never receives a post in an intermediate "processing" state. For images this is near-instant; video re-encoding may take a few seconds before the post appears on the board.

---

## 3. Database Schema

Single `posts` table in PostgreSQL. No sender columns exist at any point.

| Column | Type | Notes |
|---|---|---|
| `id` | SERIAL PRIMARY KEY | Immutable position anchor |
| `hash` | UUID | Public-facing ID for direct links |
| `content_type` | ENUM(`text`,`image`,`video`,`link`) | Primary content type (attachment type takes precedence over text body) |
| `body` | TEXT | Markdown text; NULL for attachment-only posts; may be non-null alongside any content_type |
| `media_path` | TEXT | Filesystem path to processed file, e.g. `/var/board/media/{hash}/media.webp` |
| `og_title` | TEXT | Link posts only |
| `og_description` | TEXT | Link posts only |
| `og_image_path` | TEXT | Locally cached OG image, e.g. `/var/board/media/{hash}/og.webp` |
| `created_at` | TIMESTAMPTZ | Server-generated; never sourced from Signal |
| `deleted` | BOOLEAN DEFAULT FALSE NOT NULL | Soft delete; content purged, row retained to preserve ordering |

**Key decisions:**
- `created_at` is set by the server at ingestion time, not from the Signal message timestamp
- Deletion is soft — the row is kept but `deleted = true` and all files under `/var/board/media/{hash}/` are removed, preventing position gaps in the grid
- `hash` is a UUID generated at insert; not derivable from content or position
- No Argon2 or temporary identifier hashing is required — no temporary identifiers exist in this design
- `content_type` reflects the primary/attachment type; `body` can coexist with any type (e.g. a video with a caption)

---

## 4. Signal Ingestion & TOTP Validation

**Message format:**
```
123456 <text or link>
```
Or a 6-digit code sent alongside a media attachment (with optional caption). The first 6 characters are the TOTP; everything after the code (trimmed) becomes `body`. If no text follows the code and there is no caption, `body` is NULL.

**Mixed posts (attachment + text):** `content_type` is set to the attachment type (`image` or `video`); `body` stores the caption if present.

**TOTP configuration:**
- Step size: **300 seconds (5 minutes)** — matching the PRD's "5-minute time window"
- Validated against: current window + 1 previous window = up to **10 minutes** total validity
- Implemented via `pyotp.TOTP(secret, interval=300).verify(code, valid_window=1)`
- Invalid code: entire message discarded, no DB write, no response to sender

**Sender metadata handling:**
- Sender phone number, profile name, and message timestamp are overwritten with `None` in the message object immediately after successful TOTP validation, before any further processing or DB write

**Media processing pipeline** (runs synchronously before SSE broadcast):
- **Images:** `Pillow` strips all EXIF data, converts to WebP, saved to `/var/board/media/{hash}/media.webp`
- **Video:** `ffmpeg` strips metadata tracks, re-encodes to MP4, saved to `/var/board/media/{hash}/media.mp4`
- **Links:** `httpx` fetches URL, `BeautifulSoup` parses OG tags; OG image downloaded, EXIF-stripped, saved to `/var/board/media/{hash}/og.webp`
- **Text:** stored as-is, rendered as Markdown on frontend

Media is served to the frontend via Nginx static file serving at `/media/{hash}/media.webp` etc.

**Failure handling:**
- Media processing failure → post published as text-only (`media_path` remains NULL), media silently dropped
- OG scrape failure → post published as plain link, no preview card
- signal-cli disconnect → FastAPI reconnects automatically with exponential backoff (cap: 60s, max 10 retries; after max retries, error logged to stderr)

**Rate limiting:** TOTP's 5-minute step size provides natural rate limiting — only one valid code exists per window, making rapid bulk submissions impossible without knowing future codes. No additional rate limiting is required.

---

## 5. Frontend

### Public Board (`/`)
- CSS `column-count` masonry layout — no JS library. Items are prepended to the DOM in newest-first order. Since `column-count` fills columns top-to-bottom left-to-right in DOM order, the first item in the DOM (the newest post) always renders at the top of the first column.
- `EventSource` connects to `/api/stream` on load; SSE events insert new cards at the top of the DOM without page refresh
- Media lazy-loaded via `IntersectionObserver` — assets only fetched when entering viewport
- Each card has a "Copy Link" button writing `/post/{hash}` to clipboard

### Post Card Types
| Type | Rendering |
|---|---|
| `text` | Markdown via `react-markdown` |
| `image` | WebP `<img>`, lazy loaded |
| `video` | MP4 `<video>`, lazy loaded, autoplay off |
| `link` | OG preview card (title, description, thumbnail) |

Cards with both an attachment and a `body` render the media above the text caption.

### Single Post View (`/post/{hash}`)
- Fetches post from `/api/posts/{hash}`
- Full post rendered in isolation
- Returns 404 if hash not found or `deleted = true`

---

## 6. Admin

No UI. Deletion via direct HTTP call:

```bash
curl -X DELETE https://<domain>/api/admin/posts/<hash> \
  -H "Authorization: Bearer <admin_token>"
```

On delete:
- `deleted` set to `TRUE`
- `body`, `media_path`, `og_title`, `og_description`, `og_image_path` set to NULL
- All files under `/var/board/media/{hash}/` deleted from filesystem (covers both media and OG images)
- SSE event broadcast to remove post from all active frontends

Admin token stored as environment variable on the server, never in the codebase.

---

## 7. Security Configuration

- **Nginx:** `access_log off;` on all endpoints
- **TLS:** Let's Encrypt via certbot, TLS 1.3 only
- **TOTP shared secret:** stored as `TOTP_SECRET` environment variable on the server; injected as `VITE_TOTP_SECRET` at Token Generator build time; never committed to version control
- **Admin token:** `ADMIN_TOKEN` environment variable only, never committed
- **Zero sender data:** no sender columns in DB schema; sender fields set to `None` in memory immediately after TOTP validation, before any DB write
- **Media metadata:** all EXIF/metadata stripped before storage; `created_at` is server-assigned

---

## 8. Tech Stack

| Layer | Choice |
|---|---|
| VPS | 1984.is (Iceland, crypto payment) |
| Backend | Python 3.12, FastAPI |
| Signal | signal-cli (systemd daemon, JSON-RPC) |
| TOTP | `pyotp` (backend, interval=300), `otpauth` JS (Token Generator) |
| Media | `Pillow` (images), `ffmpeg` (video), `httpx` + `BeautifulSoup` (OG) |
| Database | PostgreSQL |
| Frontend | React, Tailwind CSS, `react-markdown` |
| Reverse Proxy | Nginx (access logs disabled) |
| TLS | Let's Encrypt / certbot |
