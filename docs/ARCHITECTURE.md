# Architecture and limits

## Message flow

Beeper lists mautrix-signal as its official Signal bridge. This repository runs that upstream bridge unchanged against a private local Synapse instance. It does not use signal-cli, subprocess log parsing, the legacy Python API, or a guessed Signal webhook API.

The dedicated Matrix account owns the linked Signal session. The relay reads its standard Matrix `/sync` feed, verifies portal bridge metadata authored by `@signalbot`, checks the Signal ghost namespace, and accepts direct-message portals by default. Group publication requires explicit room IDs. Bridge management messages, own-account echoes, old history and edits are excluded. Incoming text and link bodies remain plain text/Markdown; the Worker does not fetch arbitrary URLs for link previews. Multiple Signal attachments bridged as multiple Matrix events produce separate cards.

Each publication ID is SHA-256 of the private room/event IDs. Only that opaque ID, message content and normalized media go to the Worker. Bearer authentication separates ingestion from public reads and moderation. The relay receives a successful storage response before sending a confirmation link through Matrix and the Signal bridge. Stable Matrix reply transaction IDs prevent duplicate confirmation events on retry.

The Worker stores media under a deterministic R2 key before inserting its D1 record. A unique hash and `INSERT OR IGNORE` deduplicate retries. Deleted rows remain as tombstones. R2/D1 do not offer a cross-service transaction: failed database writes may leave an unpublished object, which retries reuse. A concurrent delete can leave an inaccessible orphan after an in-flight upload; public media requests always verify the post is still visible.

## Privacy boundary

Signal encryption ends at the linked bridge. The private Matrix hop is intentionally unencrypted and contained on the host's Docker network; the relay refuses encrypted portal rooms. The hop to Cloudflare uses HTTPS. Posts on the board are public, including any names/locations that users write in message content. There is no browser-shared TOTP secret or claim that the host cannot see senders.

Synapse and mautrix-signal retain private account/session/message data. The relay keeps private sync checkpoints locally and does not log content or sender IDs. Image decoding/re-encoding drops EXIF and original filenames; animated images become a single frame. Videos are transcoded to MP4 without source metadata/chapters. This cannot remove identifying content visible or audible in the media itself. The publishing bot must be a dedicated account with a clear public-submission notice.

## Free-tier intent

Cloudflare Workers handles API requests and serves the existing frontend with Workers Static Assets. D1 is accessed through native bindings; R2 stores media. There are no paid Queues, Durable Objects, always-running Cloudflare containers, or image-transformation services in this design.

Cloudflare has commonly offered 100,000 Worker requests/day, D1 free allowances of 5 million rows read/day, 100,000 rows written/day and 5 GB storage, and an R2 monthly free allowance of 10 GB storage with operation allowances. **Verify current plan limits and pricing before deployment**: [Workers](https://developers.cloudflare.com/workers/platform/pricing/), [D1](https://developers.cloudflare.com/d1/platform/pricing/), [R2](https://developers.cloudflare.com/r2/pricing/). R2 enablement may require billing details and overages may be billed. This code does not impose a billing cap.

A continuously visible screen polls every 30 seconds: about 2,880 API requests/day before media/detail requests. Edge caching shares a 15-second list response between viewers at the same location, reducing D1 reads but not Worker request counts. Hidden tabs stop polling. Pages are bounded at 100 records, with an index on visibility and ID. Media requests check D1 visibility and are not cached so deleted files are denied; repeated large video playback can consume considerable operations. Free-tier suitability depends on viewers, posts and media volume.

The always-on bridge/Synapse/relay host is separate from Cloudflare. Native Signal cryptography, persistent device keys and long-lived network connections make an entirely Workers-based deployment impractical with the upstream bridge.

## Scope

Supported: text/links, image cards, MP4 video cards, caption preservation when supplied by the bridge, pagination, polling, confirmations, authenticated deletion and retry recovery.

Limits: 50,000 text characters; 10 MiB original and processed media; 25 million image pixels; 120-second video processing deadline. Unsupported messages receive a rejection. No audio/file cards, scraped OG previews, Matrix E2EE decryption, Signal edit/redaction synchronization, user-level quotas or moderation queue are implemented. The admin endpoint is the moderation path. Add access rules/quotas if opening the bot to high-volume public traffic.
