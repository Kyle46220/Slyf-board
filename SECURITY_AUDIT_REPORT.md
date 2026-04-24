# Security Audit Report
## Secure Anonymous Board

**Date:** 2026-04-23
**Project:** Secure Anonymous Board
**Severity Distribution:**
- 🔴 CRITICAL: 3
- 🔴 HIGH: 7
- 🟡 MEDIUM: 4
- 🟢 GOOD: 7

---

## CRITICAL Issues

### 1. Secrets Exposure in Git
**Severity:** 🔴 CRITICAL
**Location:** Root `.gitignore`, `backend/.env`

**Issue:** `.env` file is not excluded from git. Real secrets committed:
```
TOTP_SECRET=JBSWY3DPEHPK3PXP
ADMIN_TOKEN=localdevtoken
DATABASE_URL=postgresql+asyncpg://board@/board?host=/tmp
MEDIA_DIR=/tmp/board_media
```

**Impact:** Credentials exposed in version control. Anyone with repo access can authenticate as admin or access database.

**Fix:** Update `.gitignore`:
```gitignore
.env
*.pyc
__py__/
*.db
.venv/
node_modules/
dist/
build/
```

**Action Required:** 
1. Immediately rotate all exposed secrets
2. Remove from git history: `git filter-branch` or BFG Repo-Cleaner
3. Force push with caution

---

### 2. Weak TOTP Secret in .env.example
**Severity:** 🔴 CRITICAL
**Location:** `backend/.env.example`

**Issue:** Example TOTP secret is a well-known base64 string:
```
TOTP_SECRET=JBSWY3DPEHPK3PXP  # decodes to "HELLO WORLD"
```

**Impact:** Users may copy this weak secret, making authentication trivial to bypass.

**Fix:** Generate random 32-byte base32 secret:
```bash
python -c "import pyotp; print(pyotp.random_base32())"
```

Update `.env.example`:
```
TOTP_SECRET=JWSY4DPEHPK3PXP  # Replace with generated secret
```

---

### 3. No Rate Limiting
**Severity:** 🔴 HIGH (reclassified from CRITICAL due to limited attack surface)
**Location:** All API endpoints

**Issue:** No rate limiting on:
- `GET /api/posts` - can be abused to enumerate all posts rapidly
- `GET /api/posts/{hash}` - vulnerable to random hash attacks
- `GET /api/stream` - SSE connections can exhaust server resources

**Impact:** DoS attacks, data scraping, resource exhaustion.

**Fix:** Add rate limiting using `slowapi` or `fastapi-limiter`:
```python
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

@app.get("/api/posts")
@limiter.limit("100/minute")
async def list_posts(...):
    ...
```

---

## HIGH Issues

### 4. Missing CORS Configuration
**Severity:** 🔴 HIGH
**Location:** `backend/app/main.py`

**Issue:** FastAPI app has no CORS middleware. Any origin can make requests.

**Impact:** CSRF attacks, data theft from malicious sites.

**Fix:** Add CORS middleware with strict origins:
```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://yourdomain.com"],
    allow_methods=["GET"],
    allow_headers=["*"],
    credentials=False,
)
```

---

### 5. TOTP Acceptance Window Too Permissive
**Severity:** 🔴 HIGH
**Location:** `backend/app/totp.py:8`

**Issue:** `valid_window=1` accepts codes from previous/next interval = 15 minute window (3 × 5min).

**Impact:** Weak authentication, replay attacks possible.

**Fix:** Reduce to `valid_window=0` for 5-minute window only:
```python
return totp.verify(code, valid_window=0)
```

---

### 6. No Input Size Limits
**Severity:** 🔴 HIGH
**Location:** `backend/app/main.py`, `backend/app/media.py`

**Issue:** 
- No file upload size limits (image/video)
- No body text length validation
- `scrape_og` fetches arbitrary URLs without size limits

**Impact:** DoS via large uploads, memory exhaustion, infinite downloads.

**Fix:**
```python
# In main.py or request validation
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB
MAX_TEXT_LENGTH = 10000  # characters
MAX_OG_IMAGE_SIZE = 5 * 1024 * 1024  # 5MB

# In scrape_og, add:
if len(img_resp.content) > MAX_OG_IMAGE_SIZE:
    return None
```

---

### 7. Path Traversal Risk in process_video
**Severity:** 🔴 HIGH
**Location:** `backend/app/media.py:34`

**Issue:** `ffmpeg` command accepts unvalidated paths from user-controlled attachments.

**Impact:** Potential command injection, arbitrary file access.

**Fix:** Sanitize and validate paths:
```python
import os

def safe_path(path: Path) -> bool:
    """Ensure path is within allowed directory."""
    try:
        path.resolve().relative_to(settings.media_dir.resolve())
        return True
    except ValueError:
        return False

# In process_video:
if not safe_path(src):
    raise ValueError("Invalid file path")
```

---

### 8. Admin Token Simple Bearer
**Severity:** 🟡 MEDIUM
**Location:** `backend/app/routers/admin.py:14-19`

**Issue:** Static token in header, no expiration, no rotation mechanism.

**Impact:** Long-lived credential, hard to revoke if leaked.

**Fix:** Consider:
- Short-lived JWT with rotation
- IP whitelisting for admin endpoints
- Request signing with timestamps
- Or keep as-is but implement rotation in secrets management

---

### 9. No Request Timeout on SSE
**Severity:** 🟡 MEDIUM
**Location:** `backend/app/routers/posts.py:32-39`

**Issue:** SSE connections can hang indefinitely, exhausting connections.

**Impact:** DoS via connection exhaustion.

**Fix:** Add timeout:
```python
@router.get("/stream")
async def stream_events():
    q = broadcaster.subscribe()
    return StreamingResponse(
        broadcaster.stream(q),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        timeout=300,  # 5 minutes
    )
```

---

### 10. No Security Headers
**Severity:** 🟡 MEDIUM
**Location:** `backend/app/main.py`

**Issue:** Missing security headers:
- `Content-Security-Policy`
- `X-Content-Type-Options`
- `X-Frame-Options`
- `Strict-Transport-Security`

**Impact:** XSS, clickjacking, protocol downgrade attacks.

**Fix:** Add middleware:
```python
from starlette.middleware.base import BaseHTTPMiddleware

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response

app.add_middleware(SecurityHeadersMiddleware)
```

---

### 11. No Dependency Scanning
**Severity:** 🟡 MEDIUM
**Location:** CI/CD pipeline

**Issue:** No automated vulnerability scanning of dependencies.

**Impact:** Supply chain attacks go undetected.

**Fix:** Add to CI:
```yaml
- name: Run npm audit
  run: npm audit --production

- name: Run pip-audit
  run: pip-audit
```

---

## GOOD Practices Found

1. ✅ EXIF stripping on images (`process_image`)
2. ✅ Metadata removal from videos (`process_video` with `-map_metadata -1`)
3. ✅ Sender metadata stripped in Signal listener (line 70-76)
4. ✅ UUID-based post hashes (not predictable IDs)
5. ✅ Soft delete pattern (preserves data integrity)
6. ✅ Async database operations (non-blocking)
7. ✅ No SQL injection (using SQLAlchemy ORM)

---

## Recommended Fix Priority

1. **Immediate (Today):**
   - Update `.gitignore` and rotate secrets
   - Change `.env.example` TOTP secret
   - Add CORS configuration

2. **This Week:**
   - Implement rate limiting
   - Add input size validation
   - Reduce TOTP window
   - Fix path traversal

3. **Next Sprint:**
   - Add security headers
   - Implement SSE timeout
   - Set up dependency scanning
   - Review admin authentication strategy

---

## Summary

**Overall Risk Level:** HIGH

The application has solid privacy fundamentals (anonymity, metadata stripping) but lacks basic web security hardening. The CRITICAL issues around secrets management must be addressed immediately. The HIGH issues around input validation and rate limiting are necessary for production deployment.

**Estimated Fix Time:** 2-3 days for all issues, 4-6 hours for critical/high priority items.
