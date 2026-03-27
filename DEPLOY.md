# Deployment, Setup & Usage Guide

## Table of Contents

1. [Order of Operations](#order-of-operations)
2. [1984.is VPS](#1984is-vps)
3. [DNS](#dns)
4. [Server Bootstrap](#server-bootstrap)
5. [Signal Registration](#signal-registration)
6. [Backend Deployment](#backend-deployment)
7. [Frontend & Token Generator Deployment](#frontend--token-generator-deployment)
8. [TLS Certificates](#tls-certificates)
9. [Start Services](#start-services)
10. [Smoke Test](#smoke-test)
11. [Ongoing Operations](#ongoing-operations)
12. [Usage Guide for Posters](#usage-guide-for-posters)

---

## Order of Operations

```
1984.is → DNS → server bootstrap → signal registration → backend deploy
→ run migrations → build & deploy frontends → TLS certs → start services → smoke test
```

Do not skip steps. Signal registration must happen before starting the signal-cli service.
TLS certs must happen before nginx will serve HTTPS.

---

## 1984.is VPS

### Signing Up

1. Go to **https://1984.is/product/vps/**
2. Choose a plan — the smallest (1 vCPU / 2 GB RAM / 20 GB SSD, ~$5/mo) is sufficient.
3. **Payment:** 1984.is accepts Monero (XMR), Bitcoin, and credit card. Use Monero for maximum anonymity. Payment is via their invoice flow — send exact XMR amount to the displayed address.
4. **Account details:** You do not need to provide real ID. Use a throwaway email (e.g. a ProtonMail address created over Tor). They do not require KYC.
5. **OS:** Select **Debian 12** (Bookworm) or **Ubuntu 24.04 LTS**. The setup script targets Debian/Ubuntu.
6. After payment clears, you receive SSH credentials by email.

### First Login

```bash
ssh root@<your-vps-ip>
```

Set a strong root password or add your SSH public key immediately:

```bash
echo "ssh-ed25519 AAAA...yourkey..." >> ~/.ssh/authorized_keys
chmod 600 ~/.ssh/authorized_keys
```

Disable password SSH login (optional but recommended):

```bash
sed -i 's/^#\?PasswordAuthentication.*/PasswordAuthentication no/' /etc/ssh/sshd_config
systemctl restart sshd
```

### Networking Notes

1984.is assigns a static IPv4. IPv6 is also available. Nginx listens on both by default.
There is no firewall by default — you may want to add `ufw`:

```bash
apt-get install -y ufw
ufw allow 22/tcp
ufw allow 80/tcp
ufw allow 443/tcp
ufw enable
```

---

## DNS

Point two domain names (or subdomains) at your VPS IP. Example using a registrar like Njalla
(also Iceland-based, accepts Monero):

| Record | Name | Value |
|--------|------|-------|
| A | `board.example.com` | `<vps-ip>` |
| A | `token.example.com` | `<vps-ip>` |

TTL 300 is fine. Wait for propagation before running certbot (usually < 5 min).

**The token generator domain should not be publicly listed anywhere.** Share it only with
authorised posters. Its only purpose is generating TOTP codes.

---

## Server Bootstrap

Copy the repo to the server, then run the setup script:

```bash
# on your local machine
scp -r /path/to/board root@<vps-ip>:/opt/board-src
ssh root@<vps-ip>

# on the server
cd /opt/board-src
bash deploy/setup.sh
```

The script installs: nginx, certbot, ffmpeg, PostgreSQL, Python 3.12, Java (required by
signal-cli), signal-cli, creates system users and directories, installs systemd units, and
copies nginx configs.

It does **not** start services yet — that comes after Signal registration and env setup.

---

## Signal Registration

Signal requires a phone number. Use a **prepaid SIM** purchased with cash, or a VoIP number
that accepts SMS (e.g. JMP.chat, MySudo). The number only needs to receive one SMS at setup
time; it can be a SIM you put away afterwards.

### Register the Number

```bash
sudo -u signal signal-cli --config /var/signal-cli \
    -u +1XXXXXXXXXX register
```

Replace `+1XXXXXXXXXX` with the full international format (e.g. `+447700900000` for UK).

Signal will send an SMS with a 6-digit code.

### Verify

```bash
sudo -u signal signal-cli --config /var/signal-cli \
    -u +1XXXXXXXXXX verify 123456
```

Replace `123456` with the code from SMS.

### Confirm the Socket Works

```bash
sudo systemctl start signal-cli
sleep 3
sudo systemctl status signal-cli
# should show: Active: active (running)
```

Send a test Signal message from any phone to the board number. Check it arrives:

```bash
sudo journalctl -u signal-cli -f
# you should see JSON-RPC messages in the log
```

---

## Backend Deployment

### Create the Environment File

```bash
cat > /etc/board.env << 'EOF'
TOTP_SECRET=<your-base32-secret>
ADMIN_TOKEN=<a-long-random-string>
DATABASE_URL=postgresql+asyncpg://board:board@localhost/board
MEDIA_DIR=/var/board/media
EOF
chmod 600 /etc/board.env
```

**Generating a TOTP secret:**

```bash
python3 -c "import base64, os; print(base64.b32encode(os.urandom(20)).decode())"
```

Copy the output. This goes in `TOTP_SECRET` here AND in `VITE_TOTP_SECRET` when building
the token generator (see below). Keep a secure offline copy — losing it means posters
cannot authenticate.

**Generating an admin token:**

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
```

### Install the Backend

```bash
cp -r /opt/board-src/backend /opt/board/backend
python3.12 -m venv /opt/board/venv
/opt/board/venv/bin/pip install -e /opt/board/backend
```

### Set the PostgreSQL Password

The setup script creates the `board` user and database but does not set a password.
If your `pg_hba.conf` uses `md5` or `scram-sha-256` for TCP connections, set one:

```bash
sudo -u postgres psql -c "ALTER USER board PASSWORD 'board';"
```

Or use peer auth (local socket only) by changing the DATABASE_URL to use `+psycopg2` with
`postgresql://board@/board` (no password, Unix socket). Your `.env` already uses asyncpg
for the app; alembic uses psycopg2. Adjust as needed for your pg_hba config.

### Run Migrations

```bash
cd /opt/board/backend
/opt/board/venv/bin/alembic upgrade head
```

Expected: `Running upgrade -> 001, create posts table`

---

## Frontend & Token Generator Deployment

These are built **locally** (on your development machine) and deployed as static files.
This keeps build tools and secrets off the server.

### Build the Token Generator

```bash
# on your local machine, in the board/ repo
cd token-generator
VITE_TOTP_SECRET=<your-base32-secret> npm run build
```

The secret is inlined into the JS bundle at build time. Verify it is not visible as a
variable name (the value will be there, but not the env var name):

```bash
grep -r "VITE_TOTP_SECRET" dist/   # should return nothing
```

Deploy to the server:

```bash
scp -r dist/* root@<vps-ip>:/var/www/token-generator/
```

### Build the React Frontend

```bash
# on your local machine
cd frontend
npm run build
scp -r dist/* root@<vps-ip>:/var/www/board/
```

Set correct ownership on the server:

```bash
ssh root@<vps-ip> chown -R www-data:www-data /var/www/board /var/www/token-generator
```

---

## TLS Certificates

Nginx must be running with the configs in place before certbot can validate domains.
The setup script already copied configs and reloaded nginx.

```bash
certbot --nginx -d board.example.com -d token.example.com
```

Certbot will:
1. Write cert files to `/etc/letsencrypt/live/`.
2. Modify the nginx server blocks to reference the certs (or you can point it to your
   existing configs — it recognises the `ssl_certificate` directives).
3. Install an auto-renewal cron or systemd timer.

Verify auto-renewal works:

```bash
certbot renew --dry-run
```

---

## Start Services

```bash
systemctl start signal-cli
systemctl start board
systemctl reload nginx

# verify
systemctl status signal-cli board nginx
```

Check the backend log:

```bash
journalctl -u board -f
```

You should see uvicorn start lines. If you see a signal-cli connection error, confirm the
socket path `/var/run/signal-cli/socket` exists:

```bash
ls -la /var/run/signal-cli/
```

---

## Smoke Test

### 1. Public board loads

Open `https://board.example.com` in a browser — blank masonry grid, no errors.

### 2. Post via Signal

On the token generator site (`https://token.example.com`), copy the current 6-digit code.

From any Signal account, send a message to the board phone number:

```
<code> hello world
```

Within a few seconds the post should appear on the board without refreshing (SSE push).

### 3. Image post

```
<code> optional caption
[attach an image]
```

The board should show the image (EXIF stripped, converted to WebP).

### 4. Link post

```
<code> https://example.com/some-article
```

The board should show the OG title, description, and preview image.

### 5. Admin delete

```bash
curl -X DELETE https://board.example.com/api/admin/posts/<hash> \
    -H "Authorization: Bearer <ADMIN_TOKEN>"
# expected: {"ok":true}
```

The post should disappear from all open browsers without refresh.

### 6. Invalid TOTP rejected

Send a message with a wrong or expired TOTP code — no post should appear.

---

## Ongoing Operations

### Re-deploying the Frontend

```bash
# local
cd frontend && npm run build
scp -r dist/* root@<vps-ip>:/var/www/board/

# local
cd token-generator
VITE_TOTP_SECRET=<secret> npm run build
scp -r dist/* root@<vps-ip>:/var/www/token-generator/
```

No server restart needed — nginx serves static files directly.

### Re-deploying the Backend

```bash
# copy updated source
scp -r backend/ root@<vps-ip>:/opt/board/backend/

# on server
/opt/board/venv/bin/pip install -e /opt/board/backend
systemctl restart board
```

### Viewing Logs

```bash
# backend (uvicorn + ingestion loop)
journalctl -u board -f

# signal-cli (raw message traffic)
journalctl -u signal-cli -f

# nginx errors only (access logging is off by design)
tail -f /var/log/nginx/board_error.log
```

### Rotating the TOTP Secret

1. Generate a new secret: `python3 -c "import base64,os; print(base64.b32encode(os.urandom(20)).decode())"`
2. Update `/etc/board.env` on the server: `TOTP_SECRET=<new-secret>`
3. Rebuild and redeploy the token generator with the new `VITE_TOTP_SECRET`.
4. `systemctl restart board`
5. Distribute the new token generator URL to authorised posters.

Old codes will immediately stop working.

### Rotating the Admin Token

```bash
sed -i "s/^ADMIN_TOKEN=.*/ADMIN_TOKEN=$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')/" /etc/board.env
systemctl restart board
```

### Backups

The only stateful data is:
- **PostgreSQL:** `pg_dump board > board_$(date +%F).sql`
- **Media files:** `tar czf media_$(date +%F).tar.gz /var/board/media/`
- **Signal config:** `tar czf signal_$(date +%F).tar.gz /var/signal-cli/`
- **`/etc/board.env`** (keep this secret)

Cron example (daily at 3am):

```bash
0 3 * * * pg_dump board | gzip > /root/backups/board_$(date +\%F).sql.gz
```

---

## Usage Guide for Posters

### What You Need

- A Signal account (any phone number)
- Access to the token generator site (URL shared privately)
- The board's Signal number (shared privately)

### How to Post

1. **Get a code.** Open the token generator site. You will see a 6-digit code and a countdown
   timer. The code is valid for up to ~10 minutes (two 5-minute windows).

2. **Compose your Signal message.** The first word must be the 6-digit code:

   | Post type | Format |
   |-----------|--------|
   | Text | `123456 your message here` (Markdown supported) |
   | Image | Attach image file, caption: `123456 optional caption` |
   | Video | Attach video file, caption: `123456 optional caption` |
   | Link | `123456 https://example.com/article` |
   | Code only | `123456` (posts with no body or attachment) |

3. **Send to the board number** via Signal.

4. Your post appears on the board within seconds. No confirmation is sent back.

### Tips

- **Refresh the code** if the timer runs out before you send — copy the new code and resend.
- **Markdown works** in text posts: `**bold**`, `_italic_`, `` `code` ``, `> blockquote`.
- **Chain code + caption** for media: `123456 check this out` with an attached photo.
- **Link posts** auto-fetch the page title and preview image. The URL must start with
  `http://` or `https://` and be the only thing after the code (no extra text).
- **Your identity is never recorded.** The backend zeroes your phone number, name, and
  Signal UUID before writing anything to the database. There is no way to trace a post
  back to you after the fact.
- **Codes are single-use in spirit** — the same code cannot be replayed within its window
  (the clock advances and old windows expire), but you do not need to worry about this in
  practice.

### Copying a Direct Link

Each post has a **Copy Link** button. The link format is:

```
https://board.example.com/post/<hash>
```

This URL is stable and can be shared directly to a specific post.

### What Happens to Deleted Posts

If the admin deletes a post, it disappears from all open browsers immediately (SSE event).
The database row is kept but all content is nulled. The media files are deleted from disk.
There is no way to recover a deleted post.
