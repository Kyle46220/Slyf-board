import test from 'node:test';
import assert from 'node:assert/strict';
import {DatabaseSync} from 'node:sqlite';
import {readFileSync} from 'node:fs';
import worker from '../src/worker.js';

const secret = 'a'.repeat(64), hash = 'b'.repeat(64);
function setup() {
  const db = new DatabaseSync(':memory:');
  const migration = readFileSync(new URL('../migrations/0001_posts.sql', import.meta.url), 'utf8');
  db.exec(migration); db.exec(migration);
  const objects = new Map();
  const env = {
    INGEST_TOKEN: secret, ADMIN_TOKEN: 'c'.repeat(64),
    DB: {prepare(sql) {
      let params = [];
      return {bind(...values) { params = values; return this; },
        async first() { return db.prepare(sql).get(...params); },
        async all() { return {results: db.prepare(sql).all(...params)}; },
        async run() { return db.prepare(sql).run(...params); }};
    }},
    MEDIA: {async put(key, bytes) {objects.set(key, bytes);}, async delete(key) {objects.delete(key);}, async get() {return null;}},
    ASSETS: {fetch: () => new Response('frontend')}
  };
  const call = (path, options) => worker.fetch(new Request('https://board.test' + path, options), env, {waitUntil() {}});
  function post(id = hash, body = 'hello', file) {
    const form = new FormData(); form.set('event_id', id); form.set('body', body);
    if (file) form.set('media', file, 'media');
    return call('/api/ingest', {method: 'POST', headers: {Authorization: `Bearer ${secret}`}, body: form});
  }
  return {call, post, db, env, objects};
}

test('ingestion persists content, deduplicates retries, and exposes no sender data', async () => {
  const {post, call} = setup();
  assert.equal((await post()).status, 201);
  assert.equal((await post()).status, 200);
  const response = await call('/api/posts');
  const rows = await response.json();
  assert.equal(rows.length, 1); assert.equal(rows[0].body, 'hello');
  assert.equal(rows[0].hash, hash); assert.equal(rows[0].content_type, 'text');
  assert.equal('id' in rows[0], false); assert.equal('sender' in rows[0], false);
  assert.equal(response.headers.get('X-Content-Type-Options'), 'nosniff');
});

test('auth fails closed for missing, incorrect and short configured tokens', async () => {
  const {call, env} = setup();
  for (const token of ['', 'wrong']) assert.equal((await call('/api/ingest', {method: 'POST', headers: {Authorization: token}})).status, 401);
  env.INGEST_TOKEN = 'short';
  assert.equal((await call('/api/ingest', {method: 'POST', headers: {Authorization: 'Bearer short'}})).status, 401);
});

test('delete is authenticated and tombstone prevents replay resurrection', async () => {
  const {post, call} = setup(); await post();
  assert.equal((await call(`/api/admin/posts/${hash}`, {method: 'DELETE'})).status, 401);
  assert.equal((await call(`/api/admin/posts/${hash}`, {method: 'DELETE', headers: {Authorization: `Bearer ${'c'.repeat(64)}`}})).status, 204);
  assert.equal((await post()).status, 200);
  assert.deepEqual(await (await call('/api/posts')).json(), []);
  assert.equal((await call(`/api/posts/${hash}`)).status, 404);
  assert.equal((await call(`/media/${hash}/media.webp`)).status, 404);
});

test('validates limits, content, pagination and media signatures before writes', async () => {
  const {post, call, objects} = setup();
  assert.equal((await post('bad')).status, 400);
  assert.equal((await post(hash, '')).status, 400);
  assert.equal((await post(hash, 'x'.repeat(50001))).status, 400);
  assert.equal((await post(hash, '', new Blob(['bad'], {type: 'image/webp'}))).status, 415);
  assert.equal((await post(hash, '', new Blob(['svg'], {type: 'image/svg+xml'}))).status, 415);
  assert.equal(objects.size, 0);
  for (const query of ['limit=0', 'limit=101', 'before=bad', 'limit=NaN']) assert.equal((await call('/api/posts?' + query)).status, 400);
  assert.equal((await call('/api/ingest', {method: 'POST', headers: {Authorization: `Bearer ${secret}`, 'Content-Length': String(13 * 1024 * 1024)}, body: 'x'})).status, 413);
});

test('stores normalized media in R2 and preserves old D1 posts', async () => {
  const {post, call, objects, db} = setup();
  db.prepare('INSERT INTO posts(hash, content_type, body) VALUES (?, ?, ?)').run('d'.repeat(64), 'text', 'old post');
  const webp = new Blob(['RIFF1234WEBPdata'], {type: 'image/webp'});
  assert.equal((await post(hash, 'caption', webp)).status, 201);
  assert.equal(objects.size, 1);
  const rows = await (await call('/api/posts')).json();
  assert.equal(rows.length, 2); assert.equal(rows[0].media_path, `/media/${hash}/media.webp`);
  const page = await (await call('/api/posts?before=' + hash)).json();
  assert.equal(page[0].body, 'old post');
});

test('D1 failure returns retryable error, never false success', async () => {
  const {post, env} = setup();
  env.DB.prepare = () => {throw Error('database down');};
  const response = await post();
  assert.equal(response.status, 503);
  assert.deepEqual(await response.json(), {error: 'Service unavailable'});
});
