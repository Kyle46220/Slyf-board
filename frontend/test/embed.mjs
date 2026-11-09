import { chromium } from "playwright";
import http from "node:http";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { DatabaseSync } from "node:sqlite";
import assert from "node:assert/strict";
import worker from "../../backend/src/worker.js";
const project = fileURLToPath(new URL("../../", import.meta.url));
const db = new DatabaseSync(":memory:");
db.exec(readFileSync(project + "/backend/migrations/0001_posts.sql", "utf8"));
for (let i = 1; i <= 102; i++)
  db.prepare(
    "INSERT INTO posts(hash,content_type,body,media_path,created_at) VALUES(?,?,?,?,?)",
  ).run(
    i.toString(16).padStart(64, "0"),
    i === 102 ? "image" : "text",
    i === 102
      ? "Image caption"
      : i === 101
        ? "A long URL: https://example.org/" +
          "a".repeat(250) +
          "\n\n```\n" +
          "x".repeat(300) +
          "\n```"
        : "Fixture post " + i,
    i === 102
      ? "/media/" + i.toString(16).padStart(64, "0") + "/media.webp"
      : null,
    new Date().toISOString(),
  );
let releaseImages;
const imagesReady = new Promise((resolve) => {
  releaseImages = resolve;
});
const image =
  '<svg xmlns="http://www.w3.org/2000/svg" width="800" height="1200"><rect width="800" height="1200" fill="#dbeafe"/></svg>';
const env = {
  MEDIA: {
    async get() {
      await imagesReady;
      return {
        body: image,
        size: Buffer.byteLength(image),
        httpEtag: "fixture",
        writeHttpMetadata(headers) {
          headers.set("Content-Type", "image/svg+xml");
        },
      };
    },
  },
  DB: {
    prepare(sql) {
      let params = [];
      return {
        bind(...p) {
          params = p;
          return this;
        },
        async first() {
          return db.prepare(sql).get(...params);
        },
        async all() {
          return { results: db.prepare(sql).all(...params) };
        },
      };
    },
  },
  ASSETS: {
    async fetch(request) {
      const requestedPath = new URL(request.url).pathname;
      const path =
        requestedPath === "/" || /^\/post\/[a-f0-9]{64}$/.test(requestedPath)
          ? "/index.html"
          : requestedPath;
      try {
        return new Response(readFileSync(project + "/frontend/dist" + path), {
          headers: {
            "Content-Type": path.endsWith(".js")
              ? "application/javascript; charset=utf-8"
              : path.endsWith(".css")
                ? "text/css; charset=utf-8"
                : "text/html; charset=utf-8",
          },
        });
      } catch {
        return new Response("Not found", { status: 404 });
      }
    },
  },
};
const assetServer = http.createServer(async (req, res) => {
  try {
    const response = await worker.fetch(
      new Request("http://127.0.0.1:" + assetServer.address().port + req.url),
      env,
      { waitUntil() {} },
    );
    res.writeHead(response.status, Object.fromEntries(response.headers));
    res.end(Buffer.from(await response.arrayBuffer()));
  } catch (e) {
    res.writeHead(500);
    res.end(String(e));
  }
});
await new Promise((r) => assetServer.listen(0, "127.0.0.1", r));
const origin = "http://127.0.0.1:" + assetServer.address().port;
const blogServer = http.createServer((req, res) => {
  res.setHeader("Content-Type", "text/html");
  res.end(
    `<!doctype html><html><head><meta charset="utf-8"><style>body{max-width:720px;margin:20px auto;background:#f4eee3;color:purple}*{font-family:Georgia;font-size:20px}img{width:5000px!important}button{background:red}a{color:purple}.first{width:100%}.second{width:320px;max-width:100%}</style></head><body><h1 id="title">Bear blog fixture</h1><p id="intro">This blog style must stay unchanged.</p><section class="first"><script src="${origin}/embed.js"></script></section><section class="second"><script async src="${origin}/embed.js"></script></section><p id="after">Content after the boards.</p></body></html>`,
  );
});
await new Promise((r) => blogServer.listen(0, "127.0.0.1", r));
const browser = await chromium.launch({
  headless: true,
  executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH,
  args: ["--no-sandbox"],
});
const page = await browser.newPage({ viewport: { width: 1280, height: 900 } });
const errors = [];
page.on("pageerror", (e) => errors.push(e.message));
try {
  await page.goto(
    "http://127.0.0.1:" + blogServer.address().port + "/#chapter",
  );
  const first = page.locator(".first slyf-board");
  const second = page.locator(".second slyf-board");
  await first.locator(".masonry > div").nth(99).waitFor();
  await second.locator(".masonry > div").nth(99).waitFor();
  assert.equal(await page.locator("iframe").count(), 0);
  assert.equal(
    await first
      .locator(".masonry")
      .evaluate((e) => getComputedStyle(e).columnCount),
    "2",
  );
  assert.equal(
    await second
      .locator(".masonry")
      .evaluate((e) => getComputedStyle(e).columnCount),
    "1",
  );
  assert.equal(
    await page.locator("#intro").evaluate((e) => getComputedStyle(e).color),
    "rgb(128, 0, 128)",
  );
  const beforeImageHeight = await first.evaluate(
    (e) => e.getBoundingClientRect().height,
  );
  releaseImages();
  await first.locator("img").evaluate(async (e) => {
    if (!e.complete)
      await new Promise((r) => e.addEventListener("load", r, { once: true }));
  });
  assert.ok(
    await first.locator("img").evaluate((e) => e.naturalWidth > 0),
    "Media decoded successfully",
  );
  assert.ok(
    (await first.evaluate((e) => e.getBoundingClientRect().height)) >
      beforeImageHeight,
    "Board expands when media loads",
  );
  assert.ok(
    await first
      .locator(".masonry > div")
      .first()
      .evaluate(
        (e) =>
          getComputedStyle(e).borderStyle === "solid" &&
          parseFloat(getComputedStyle(e).borderWidth) > 0,
      ),
    "Rainbow card border is visible inside shadow DOM",
  );
  assert.equal(
    await first.locator("img").evaluate((e) => e.currentSrc),
    origin + "/media/" + (102).toString(16).padStart(64, "0") + "/media.webp",
  );
  assert.equal(
    await first.evaluate((e) => e.scrollWidth <= e.clientWidth + 1),
    true,
    "No horizontal overflow at 720px",
  );
  const oldUrl = page.url();
  await first.locator(".masonry > div").first().click();
  await first.getByText("← Back to board").waitFor();
  assert.equal(page.url(), oldUrl, "Host URL unchanged");
  assert.equal(
    await second.locator(".masonry > div").count(),
    100,
    "Other embed stays on gallery",
  );
  await first.getByText("← Back to board").click();
  await first.locator(".masonry > div").nth(99).waitFor();
  await first.getByRole("button", { name: "Older posts" }).click();
  await first.getByRole("button", { name: "Newer posts" }).waitFor();
  assert.equal(await first.locator(".masonry > div").count(), 2);
  await page.setViewportSize({ width: 360, height: 800 });
  await page.waitForTimeout(200);
  assert.equal(
    await first
      .locator(".masonry")
      .evaluate((e) => getComputedStyle(e).columnCount),
    "1",
  );
  assert.equal(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
    true,
    "Blog has no horizontal overflow on mobile",
  );
  await first.getByRole("button", { name: "Newer posts" }).click();
  await first.locator(".masonry > div").nth(99).waitFor();
  await first.locator("img").evaluate(async (e) => {
    if (!e.complete)
      await new Promise((r) => e.addEventListener("load", r, { once: true }));
  });
  if (process.env.EMBED_SCREENSHOT)
    await page.screenshot({
      path: process.env.EMBED_SCREENSHOT,
      fullPage: false,
    });
  // A restored mobile tab must refresh immediately instead of waiting for a timer.
  const insert = (id, body) =>
    db
      .prepare(
        "INSERT INTO posts(hash,content_type,body,created_at) VALUES(?,?,?,?)",
      )
      .run(
        id.toString(16).padStart(64, "0"),
        "text",
        body,
        new Date().toISOString(),
      );
  insert(500, "Resumed mobile post");
  await page.evaluate(() =>
    window.dispatchEvent(
      new PageTransitionEvent("pageshow", { persisted: true }),
    ),
  );
  await first.getByText("Resumed mobile post", { exact: true }).waitFor();
  await second.getByText("Resumed mobile post", { exact: true }).waitFor();
  insert(501, "Focused mobile post");
  await page.evaluate(() => window.dispatchEvent(new Event("focus")));
  await first.getByText("Focused mobile post", { exact: true }).waitFor();

  const mobile = await browser.newPage({
    viewport: { width: 360, height: 800 },
    isMobile: true,
    hasTouch: true,
  });
  mobile.on("pageerror", (e) => errors.push(e.message));
  const hash = (102).toString(16).padStart(64, "0");
  await mobile.goto(origin + "/#/post/" + hash);
  await mobile.getByText("Image caption", { exact: true }).waitFor();
  assert.equal(
    new URL(mobile.url()).pathname,
    "/post/" + hash,
    "Old confirmation links resolve to the post",
  );
  assert.equal(new URL(mobile.url()).hash, "");
  assert.equal(
    await mobile.locator(".masonry").count(),
    0,
    "Confirmation opens details, not the whole gallery",
  );
  await mobile.goto(origin + "/");
  await mobile.getByText("Focused mobile post", { exact: true }).waitFor();
  insert(502, "Standalone resumed post");
  await mobile.evaluate(() =>
    window.dispatchEvent(
      new PageTransitionEvent("pageshow", { persisted: true }),
    ),
  );
  await mobile.getByText("Standalone resumed post", { exact: true }).waitFor();
  await mobile.close();
  assert.deepEqual(errors, []);
  console.log(
    "PASS: real cross-origin fetches, 100-card pagination, isolated blog styles, resolved media URLs, responsive 720/320/360px widths, no iframe/overflow, independent navigation, host hash preserved, mobile tab restoration/focus refresh, legacy confirmation links, zero browser errors.",
  );
} catch (e) {
  console.log("Browser errors:", errors);
  console.log(
    "Embed state:",
    await page
      .locator(".first slyf-board")
      .evaluate((e) => e.shadowRoot.textContent.slice(-1500)),
  );
  if (process.env.EMBED_SCREENSHOT)
    await page
      .screenshot({ path: process.env.EMBED_SCREENSHOT, timeout: 5000 })
      .catch(() => {});
  throw e;
} finally {
  await browser.close();
  assetServer.close();
  blogServer.close();
  db.close();
}
