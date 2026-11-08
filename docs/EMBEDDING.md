# Embed the board in Bear Blog

Paste this as raw HTML on its own line, with a blank line before and after it,
wherever the board should appear in a Bear post or page. Do not put it in a
Markdown code fence:

```html
<script src="https://slyf-board.kyle4068.workers.dev/embed.js" async></script>
```

Bear requires an upgraded account to run scripts in posts and pages:
https://docs.bearblog.dev/markdown-cheatsheet/#html
Check the published page if the editor preview does not run the script.

The script inserts a `slyf-board` element immediately after itself. Each instance
has its own shadow root, React root and in-memory navigation, so it does not
change the blog's CSS, URL, hash or other board instances. Cards retain the
standalone board's appearance. Columns follow the actual available width, with
one column on narrow screens. The board stays in normal page flow: its height
grows when images load, with no iframe, fixed-height box or nested page scrollbar.
It uses the blog's content width; widen that content area in Bear's theme if desired.

Public posts refresh every 30 seconds while the page is visible; the gallery
paginates at 100 cards. Card details open within the embed, with a Back to board
link. External links open in a new tab. Relative media and API URLs resolve to
the Worker hosting `embed.js`, rather than to the blog. No tokens belong in the
tag. You can place the same tag more than once on a page.

## Build and check

`npm ci && npm run build` in `frontend/` builds the standalone site and the
self-contained classic script at `dist/embed.js`. Deploy the same Worker and
static assets using the existing deployment process. Public `GET`/`HEAD`
`/api/posts` and `/api/posts/HASH` responses permit cross-origin reads; ingest
and admin endpoints do not gain cross-origin access or expose credentials.

Run `npx playwright install chromium && npm run test:embed` in `frontend/`
after building. The test uses two local origins and fixture data, never production
storage. It checks narrow containers, mobile overflow, media, independent
instances, navigation and pagination. Node 24+ is required for its SQLite fixture.
`PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH` can select an existing Chromium install.
