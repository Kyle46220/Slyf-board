# Slyf Board development

The active implementation is the Cloudflare Worker in backend/src, the mautrix-signal Matrix relay in relay/, and the existing React frontend in frontend/. See README.md and docs/DEPLOYMENT.md. Earlier docs under docs/runbooks and docs/ADR describe the retired system and are historical only.

- Preserve the existing frontend appearance unless explicitly asked to redesign it.
- Use Beeper's official mautrix-signal bridge. Do not reintroduce signal-cli, journalctl parsing or the retired FastAPI service.
- Preserve existing D1/R2 data; migrations must be additive and compatible with the existing posts table.
- Never commit credentials, generated bridge config/registration, Signal databases or Matrix tokens.
- The linked Signal account must be dedicated to public submissions. Do not claim zero-knowledge storage.
- Run backend tests, relay tests and the frontend production build when tooling permits. Clearly report unavailable checks.
- Make substantial changes on feature branches and include a descriptive commit and Co-Authored-By attribution.
