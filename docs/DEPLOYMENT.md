# Deploy Slyf Board

## 1. Cloudflare: reuse D1 and R2

Export/back up the existing D1 database before a production change. Keep the existing R2 bucket. The migration creates the existing `posts` table if absent and adds an index; it does not delete records or rewrite existing media URLs.

1. Install Node 24+, run `npm ci && npm run build` in `frontend/`.
2. In `backend/`, run `npm install` and `npx wrangler login`.
3. Set `database_id` and `database_name` in `backend/wrangler.toml` to the existing D1 database. Set `bucket_name` to the existing R2 bucket (currently `slyfe`). For a fresh install use `npx wrangler d1 create slyf-board` and `npx wrangler r2 bucket create slyfe` first.
4. Run `npx wrangler d1 migrations apply slyf-board --remote` (use your configured database name).
5. Generate **two different** secrets using `openssl rand -hex 32`. Set them through `npx wrangler secret put INGEST_TOKEN` and `npx wrangler secret put ADMIN_TOKEN`. Keep the ingest token for the relay. Never put either token in frontend environment variables.
6. Run `npm run deploy`. Record the HTTPS Worker URL. Assets, API and media are same-origin; no CORS configuration or separate Pages project is needed.

For local development, use `.dev.vars` with the two secrets, apply the migration with `--local`, then run `npm run dev` in backend/. Do not point local experiments at the production D1 database.

## 2. Private bridge host

Use an always-on Linux machine with Docker Compose, persistent disk, outbound HTTPS access to Signal and the Worker, and enough memory for Synapse, mautrix-signal and media conversion. Start with at least 2 GB RAM and measure your load. A laptop/server you already own avoids another cloud bill. A free VM can work if its resource and regional allowances cover this stack; this is not a promise that the former GCP instance is free.

All following commands run from `deploy/`. The Matrix API is bound to host loopback only. Do not publish Synapse or bridge ports to the internet. Keep the host and private data volumes secured and backed up.

```sh
cp .env.example .env
mkdir -p data/synapse data/signal
# Generate Synapse config before Compose mounts the bridge registration.
docker run --rm -v "$PWD/data/synapse:/data" \
  -e SYNAPSE_SERVER_NAME=board.local -e SYNAPSE_REPORT_STATS=no \
  matrixdotorg/synapse:latest generate
# First run creates mautrix-signal's current default config and exits.
docker compose run --rm --no-deps signal
```

Install PyYAML in a local virtualenv, then apply the checked-in config helper:

```sh
python3 -m venv .venv
.venv/bin/pip install 'PyYAML>=6,<7'
sudo .venv/bin/python configure.py
# Second run generates registration.yaml and exits.
docker compose run --rm --no-deps signal
# Registration is now available for Synapse's read-only mount.
docker compose up -d synapse signal
# Interactive password prompt; creates the account that owns the Signal login.
docker compose exec synapse register_new_matrix_user \
  -c /data/homeserver.yaml http://localhost:8008 -u board --no-admin
```

The generator is for a **fresh, dedicated private Matrix server**, not an existing Beeper account or production homeserver. It sets bridge permissions only for `@board:board.local`, SQLite bridge storage, no federation, no historical Signal backfill, and unencrypted **local Matrix portal rooms**. Signal's network encryption is still handled by mautrix-signal. Do not connect this relay to encrypted Beeper-hosted rooms: it deliberately refuses encrypted portals instead of silently losing messages.

The sample uses moving image tags for initial setup. Resolve and pin `SYNAPSE_IMAGE` and `SIGNAL_IMAGE` in `.env` to tested image digests before production use, and repeat the acceptance checks after upgrades. The helper uses current upstream bridgev2 config fields; inspect upstream release notes before changing major versions.

## 3. Link a dedicated Signal bot account

1. Register a dedicated account in the official Signal mobile app. Give it a public-submission name/profile and tell senders that messages to it are published publicly. Signal registration still needs a phone number; the app cannot register an account on the user's behalf.
2. Connect a Matrix client such as Element Desktop to `http://localhost:8008` and log in as `@board:board.local`. If remote, first use an SSH tunnel: `ssh -L 8008:localhost:8008 YOUR_HOST`.
3. Open an **unencrypted** conversation with `@signalbot:board.local`. Send `login`, and follow the bridge's QR linking prompts using Signal → Settings → Linked devices. See [upstream authentication instructions](https://docs.mau.fi/bridges/go/signal/authentication.html). Do not enable Matrix encryption for management or portal rooms.
4. Obtain an access token for the same `@board:board.local` account using the Matrix client or a separate standard `POST /_matrix/client/v3/login` password login. Use a separate relay device/session if possible, and keep that token private. This is a normal Matrix user token, **not** the bridge's `as_token` or `hs_token`.
5. Fill `MATRIX_TOKEN`, `BOARD_URL`, and `INGEST_TOKEN` in `deploy/.env`. The ingest token must match the Worker secret exactly. Keep other defaults unless intentionally using a different private domain.
6. Run `docker compose up -d --build relay`.
7. Send a message from another Signal account to the dedicated bot. Accept any pending Signal message request on the linked phone if Signal requires it. The bridge creates a portal; the relay joins invitations from the bridge bot and publishes messages from Signal ghost users in verified direct-message portals.

By default groups are excluded. To publish from specific group portals, set `ALLOWED_ROOMS` to comma-separated Matrix room IDs. When set, **only** these rooms are eligible, including DMs. Tell all participants these rooms publish publicly. Do not enable backfill on a personal account.

The relay ignores messages timestamped before its first start. Its durable `relay-state` volume holds the start timestamp, sync cursor and room checkpoints. Preserve this volume across upgrades. Deleting it resets the cutoff and can skip messages received during downtime.

## 4. Acceptance checks before cutover

- Send text and a URL; verify cards and confirmation links.
- Send an image with EXIF and a short video under 10 MiB; verify rendering and playback, plus that downloaded normalized image metadata is empty.
- Send an unsupported file or oversized attachment; verify a rejection reply and no card.
- Send another message while the relay is stopped; restart it and verify recovery once. Repeat while the Worker is unavailable; no false success reply should be sent.
- Retry the same Matrix event / restart after storage succeeds; verify one card.
- Delete a card using the admin endpoint, retry its original delivery, and verify it stays deleted. The gallery list cache may show it for up to 15 seconds before the next display refresh.
- Verify a random Matrix room and a non-allowlisted group never publish.
- Verify a fresh Signal sender/message request reaches the board. This can depend on Signal account/message-request state and cannot be established by unit tests.

Delete a post with `DELETE /api/admin/posts/HASH` and `Authorization: Bearer ADMIN_TOKEN` from an operator-side HTTP client. No admin secret belongs in the browser. Deletion hides the record, removes new-style R2 media, and retains the hash tombstone so delivery retries cannot republish it. External legacy media URLs are not deleted automatically; remove their original objects separately if needed.

## 5. Cutover and operations

After the acceptance checks pass, stop the old `board` and `signal-cli` services and retire the old token-generator deployment. Switch the public domain to the Worker. Do not run both ingesters for the same bot account during cutover. The removed service files remain recoverable in Git history; no remote service has been stopped by this code change.

The relay reconnects with backoff and retains its cursor on network/storage failures. It recovers truncated Matrix sync history using `/messages` before advancing. Monitor `docker compose logs relay` for repeated `Sync failed` lines (only exception class/status are logged). A `RuntimeError` may indicate an encrypted portal or a backlog beyond the recovery limit; inspect the private configuration and checkpoints without exposing message data. The health endpoint `/api/health` checks Worker availability only, not Signal connectivity.

Back up Synapse data, the Signal database/registration and relay state together. Synapse stores source messages and media locally; configure an appropriate retention/purge policy and disk monitoring. Do not purge history still needed by an offline relay. New board media are limited to 10 MiB; Cloudflare storage still grows with each accepted upload. R2 writes that succeed immediately before a D1 failure are retried at the same key; a permanently abandoned event can leave an orphan object requiring operator cleanup.

No credentials or live account were available during implementation. Deployment, device linking and the real Signal acceptance checks must be completed in the operator's environment.
