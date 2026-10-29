const MAX_BYTES = 12 * 1024 * 1024;
const HASH = /^[a-f0-9]{64}$/;
const columns = 'hash, content_type, body, media_path, og_title, og_description, og_image_path, created_at';
const json = (data, status = 200, headers = {}) => Response.json(data, {status, headers});
class HttpError extends Error { constructor(status, message) { super(message); this.status = status; } }
export async function authorized(request, secret) {
  if (!secret || secret.length < 32) return false;
  const actual = request.headers.get('Authorization') || '';
  const digest = async value => new Uint8Array(await crypto.subtle.digest('SHA-256', new TextEncoder().encode(value)));
  const [a, b] = await Promise.all([digest(actual), digest(`Bearer ${secret}`)]);
  return a.reduce((diff, byte, i) => diff | (byte ^ b[i]), 0) === 0;
}
async function limitedBody(request) {
  if (Number(request.headers.get('content-length')) > MAX_BYTES) throw new HttpError(413, 'Message too large');
  const reader = request.body?.getReader();
  if (!reader) throw new HttpError(400, 'Missing body');
  let size = 0; const chunks = [];
  try {
    while (true) {
      const {done, value} = await reader.read(); if (done) break;
      size += value.byteLength;
      if (size > MAX_BYTES) { await reader.cancel(); throw new HttpError(413, 'Message too large'); }
      chunks.push(value);
    }
  } finally { reader.releaseLock(); }
  return new Blob(chunks);
}
export function validatePost(form) {
  const hash = form.get('event_id'); const body = form.get('body'); const file = form.get('media');
  if (typeof hash !== 'string' || !HASH.test(hash)) throw new HttpError(400, 'Invalid event ID');
  if (typeof body !== 'string' || body.length > 50000) throw new HttpError(400, 'Invalid text');
  if (!body.trim() && !file) throw new HttpError(400, 'Empty message');
  if (file && (typeof file === 'string' || !file.size || !['image/webp', 'video/mp4'].includes(file.type))) throw new HttpError(415, 'Unsupported media');
  const content_type = file ? (file.type === 'video/mp4' ? 'video' : 'image') : (/https?:\/\/\S+/i.test(body) ? 'link' : 'text');
  return {hash, body: body.trim(), file, content_type};
}
async function ingest(request, env) {
  if (!await authorized(request, env.INGEST_TOKEN)) return json({error: 'Unauthorized'}, 401);
  const blob = await limitedBody(request);
  let form;
  try { form = await new Response(blob, {headers: {'Content-Type': request.headers.get('Content-Type') || ''}}).formData(); }
  catch { throw new HttpError(400, 'Expected multipart form'); }
  const post = validatePost(form);
  // A tombstone is deliberately retained after deletion, so retries cannot resurrect it.
  const existing = await env.DB.prepare('SELECT hash FROM posts WHERE hash = ?').bind(post.hash).first();
  if (existing) return json({hash: post.hash, duplicate: true});
  let key = null;
  if (post.file) {
    const bytes = new Uint8Array(await post.file.arrayBuffer());
    const webp = bytes.length >= 12 && new TextDecoder().decode(bytes.slice(0, 4)) === 'RIFF' && new TextDecoder().decode(bytes.slice(8, 12)) === 'WEBP';
    const mp4 = bytes.length >= 12 && new TextDecoder().decode(bytes.slice(4, 8)) === 'ftyp';
    if ((post.content_type === 'image' && !webp) || (post.content_type === 'video' && !mp4)) throw new HttpError(415, 'Invalid media signature');
    key = `${post.hash}/${post.content_type === 'video' ? 'media.mp4' : 'media.webp'}`;
    // Deterministic object key makes retries safe if D1 fails after R2 succeeds.
    await env.MEDIA.put(key, bytes, {httpMetadata: {contentType: post.file.type}});
  }
  await env.DB.prepare(`INSERT OR IGNORE INTO posts (hash, content_type, body, media_path, created_at) VALUES (?, ?, ?, ?, ?)`)
    .bind(post.hash, post.content_type, post.body || null, key ? `/media/${key}` : null, new Date().toISOString()).run();
  return json({hash: post.hash}, 201);
}
async function route(request, env) {
  const url = new URL(request.url); const path = url.pathname;
  if (path === '/api/ingest' && request.method === 'POST') return ingest(request, env);
  const admin = path.match(/^\/api\/admin\/posts\/([a-f0-9]{64})$/);
  if (admin && request.method === 'DELETE') {
    if (!await authorized(request, env.ADMIN_TOKEN)) return json({error: 'Unauthorized'}, 401);
    const post = await env.DB.prepare('SELECT media_path FROM posts WHERE hash = ?').bind(admin[1]).first();
    if (!post) return json({error: 'Not found'}, 404);
    await env.DB.prepare('UPDATE posts SET deleted = 1 WHERE hash = ?').bind(admin[1]).run();
    // Only delete objects owned by this implementation. Existing external media is left alone.
    if (post.media_path?.startsWith(`/media/${admin[1]}/`)) await env.MEDIA.delete(post.media_path.slice(7));
    return new Response(null, {status: 204});
  }
  if (!['GET', 'HEAD'].includes(request.method)) return json({error: 'Method not allowed'}, 405);
  if (path === '/api/health') return json({status: 'ok'});
  if (path === '/api/posts') {
    const limit = Number(url.searchParams.get('limit') || 100);
    const before = url.searchParams.get('before');
    if (!Number.isInteger(limit) || limit < 1 || limit > 100 || (before && !HASH.test(before))) throw new HttpError(400, 'Invalid pagination');
    const statement = before
      ? env.DB.prepare(`SELECT ${columns} FROM posts WHERE deleted = 0 AND id < (SELECT id FROM posts WHERE hash = ?) ORDER BY id DESC LIMIT ?`).bind(before, limit)
      : env.DB.prepare(`SELECT ${columns} FROM posts WHERE deleted = 0 ORDER BY id DESC LIMIT ?`).bind(limit);
    const {results} = await statement.all();
    return json(results, 200, {'Cache-Control': 'public, max-age=0, s-maxage=15'});
  }
  const single = path.match(/^\/api\/posts\/([a-f0-9]{64})$/);
  if (single) {
    const post = await env.DB.prepare(`SELECT ${columns} FROM posts WHERE hash = ? AND deleted = 0`).bind(single[1]).first();
    return post ? json(post) : json({error: 'Not found'}, 404);
  }
  const media = path.match(/^\/media\/([a-f0-9]{64})\/(media\.(?:webp|mp4)|og.webp)$/);
  if (media) {
    const post = await env.DB.prepare('SELECT hash FROM posts WHERE hash = ? AND deleted = 0').bind(media[1]).first();
    if (!post) return json({error: 'Not found'}, 404);
    const key = `${media[1]}/${media[2]}`;
    const object = request.method === 'HEAD' ? await env.MEDIA.head(key) : await env.MEDIA.get(key, {range: request.headers});
    if (!object) return json({error: 'Not found'}, 404);
    const headers = new Headers({'Cache-Control': 'no-store', 'Accept-Ranges': 'bytes'});
    object.writeHttpMetadata(headers); headers.set('ETag', object.httpEtag);
    let status = 200;
    if (object.range) {
      status = 206;
      headers.set('Content-Range', `bytes ${object.range.offset}-${object.range.offset + object.range.length - 1}/${object.size}`);
      headers.set('Content-Length', String(object.range.length));
    } else headers.set('Content-Length', String(object.size));
    return new Response(request.method === 'HEAD' ? null : object.body, {status, headers});
  }
  if (path.startsWith('/api/') || path.startsWith('/media/')) return json({error: 'Not found'}, 404);
  return env.ASSETS.fetch(request);
}
export default {
  async fetch(request, env, ctx) {
    let response;
    try {
      // Shared edge caching avoids one D1 query per display per poll.
      const cacheable = request.method === 'GET' && new URL(request.url).pathname === '/api/posts';
      const cache = cacheable && globalThis.caches?.default;
      response = cache ? await cache.match(request) : null;
      if (!response) {
        response = await route(request, env);
        if (cache && response.ok) ctx.waitUntil(cache.put(request, response.clone()));
      }
    } catch (error) {
      // Do not log message bodies, Matrix IDs, credentials or storage errors containing SQL parameters.
      response = json({error: error instanceof HttpError ? error.message : 'Service unavailable'}, error.status || 503);
    }
    response = new Response(response.body, response);
    response.headers.set('X-Content-Type-Options', 'nosniff');
    response.headers.set('Referrer-Policy', 'no-referrer');
    response.headers.set('X-Frame-Options', 'DENY');
    if (!response.headers.has('Cache-Control')) response.headers.set('Cache-Control', 'no-store');
    return response;
  }
};
