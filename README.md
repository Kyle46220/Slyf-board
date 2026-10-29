# Slyf Board

Send a Signal message to a dedicated bot account; it appears as a card on the existing rainbow-bordered masonry gallery. Text, links, images and videos are supported. The bot replies with the post link after storage succeeds.

This backend uses **[mautrix-signal](https://github.com/mautrix/signal)**, the official Signal bridge listed by [Beeper's bridge manager](https://github.com/beeper/bridge-manager#official-bridge-list). The former signal-cli, log parsing, FastAPI service and browser-shared TOTP implementation are replaced.

```text
Signal users → mautrix-signal → private local Synapse → Python relay
                                                        │ HTTPS + ingest token
                                                        ▼
React gallery ← Cloudflare Worker → existing D1 + R2
```

The frontend retains its existing cards, typography and masonry layout. It refreshes every 30 seconds while visible and paginates 100 cards at a time. D1 list queries are cached at the edge for 15 seconds. A new post normally appears within 45 seconds.

The Cloudflare portion is serverless and designed for modest usage within free allowances. **The Signal bridge needs an always-on host** with persistent storage; Cloudflare Workers cannot run its native Go/Rust process or Signal session database. Use an existing computer or a suitable free VM for the private bridge stack. Neither free hosting nor a particular usage allowance is guaranteed.

- [Deployment, Signal linking and migration](docs/DEPLOYMENT.md)
- [Architecture, privacy boundaries and limits](docs/ARCHITECTURE.md)
- [Upstream Signal bridge setup](https://docs.mau.fi/bridges/go/setup.html?bridge=signal)

## Development

```sh
cd frontend && npm ci && npm run build
cd ../backend && npm install && npm test
# Configure D1/R2 bindings and local .dev.vars before running wrangler dev.
cd ../relay && pip install -r requirements.txt && python -m unittest -v
```

Backend tests require Node 24+ and exercise actual SQLite queries with an in-memory R2 adapter. Relay tests cover trusted bridge events, outage recovery, metadata removal and sender-data exclusion. CI also builds the frontend. A real linked Signal account is required for the live acceptance checklist in the deployment guide.

Messages sent to this dedicated bot are public submissions. Use a new Signal account/profile that says this clearly; do not connect a personal chat account. No sender identities are stored in the board's D1 records, but the private bridge and Matrix server necessarily retain Signal/session/chat data. This is not a zero-knowledge system.
