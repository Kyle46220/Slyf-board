"""Private Matrix -> Cloudflare relay for Beeper's official mautrix-signal bridge.

Only normalized content leaves this host. No signal-cli or log parsing is used.
"""
import hashlib
import io
import json
import logging
import os
from pathlib import Path
import random
import re
import sqlite3
import subprocess
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid

MAX_MEDIA = 10 * 1024 * 1024
LOG = logging.getLogger('relay')

class Rejected(ValueError):
    """A permanent content rejection; safe to acknowledge and advance past."""

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None

OPENER = urllib.request.build_opener(NoRedirect)

def request(url, token, method='GET', data=None, content_type='application/json', limit=32 * 1024 * 1024):
    headers = {'Authorization': f'Bearer {token}'}
    if data is not None:
        headers['Content-Type'] = content_type
        if isinstance(data, dict):
            data = json.dumps(data).encode()
    req = urllib.request.Request(url, headers=headers, data=data, method=method)
    with OPENER.open(req, timeout=60) as response:
        raw = response.read(limit + 1)
        if len(raw) > limit:
            raise Rejected('File exceeds the board size limit.')
        return raw

def multipart(event_id, body, media=None):
    boundary = uuid.uuid4().hex
    parts = []
    for name, value in [('event_id', event_id), ('body', body)]:
        parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n{value}\r\n'.encode())
    if media:
        raw, mime = media
        parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="media"; filename="media"\r\nContent-Type: {mime}\r\n\r\n'.encode() + raw + b'\r\n')
    parts.append(f'--{boundary}--\r\n'.encode())
    return b''.join(parts), f'multipart/form-data; boundary={boundary}'

def normalize(raw, msgtype):
    if msgtype == 'm.image':
        from PIL import Image, ImageOps, UnidentifiedImageError
        Image.MAX_IMAGE_PIXELS = 25_000_000
        try:
            with Image.open(io.BytesIO(raw)) as image:
                if image.width * image.height > Image.MAX_IMAGE_PIXELS:
                    raise Rejected('Image dimensions are too large.')
                # Publish a single frame; re-encoding strips EXIF, profiles and filenames.
                image = ImageOps.exif_transpose(image).convert('RGB')
                image.thumbnail((4096, 4096))
                output = io.BytesIO()
                image.save(output, format='WEBP', quality=85)
                result = output.getvalue()
        except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as error:
            raise Rejected('Unsupported image.') from error
        mime = 'image/webp'
    else:
        with tempfile.TemporaryDirectory() as directory:
            source, target = Path(directory) / 'input', Path(directory) / 'output.mp4'
            source.write_bytes(raw)
            try:
                subprocess.run(['ffmpeg', '-v', 'error', '-nostdin', '-y', '-protocol_whitelist', 'file,pipe',
                                '-i', str(source), '-map', '0:v:0', '-map', '0:a:0?', '-map_metadata', '-1',
                                '-map_chapters', '-1', '-vf', 'scale=trunc(iw/2)*2:trunc(ih/2)*2',
                                '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '28', '-threads', '1',
                                '-c:a', 'aac', '-movflags', '+faststart', '-fs', str(MAX_MEDIA + 1), str(target)],
                               check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=120)
                result = target.read_bytes()
            except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as error:
                raise Rejected('Video could not be processed within the board limits.') from error
        mime = 'video/mp4'
    if len(result) > MAX_MEDIA:
        raise Rejected('Processed media exceeds 10 MiB.')
    return result, mime

class Relay:
    def __init__(self):
        self.matrix = os.environ['MATRIX_URL'].rstrip('/')
        self.token = os.environ['MATRIX_TOKEN']
        self.user = os.environ['MATRIX_USER']
        self.bot = os.environ['BRIDGE_BOT']
        self.domain = self.user.split(':', 1)[1]
        self.ghost = re.compile(r'^@signal_[a-zA-Z0-9_-]+:' + re.escape(self.domain) + r'$')
        self.board = os.environ['BOARD_URL'].rstrip('/')
        self.ingest_token = os.environ['INGEST_TOKEN']
        if not self.board.startswith('https://') or len(self.ingest_token) < 32:
            raise ValueError('BOARD_URL must use HTTPS and INGEST_TOKEN must have at least 32 characters')
        self.allowed_rooms = set(filter(None, os.getenv('ALLOWED_ROOMS', '').split(',')))
        state = Path(os.getenv('STATE_DIR', '/data'))
        state.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(state / 'relay.sqlite3')
        self.db.execute('CREATE TABLE IF NOT EXISTS state (key TEXT PRIMARY KEY, value TEXT NOT NULL)')
        if not self.get('started'):
            self.set('started', str(int(time.time() * 1000)))
        self.started = int(self.get('started'))

    def get(self, key):
        row = self.db.execute('SELECT value FROM state WHERE key=?', (key,)).fetchone()
        return row[0] if row else None

    def set(self, key, value):
        with self.db:
            self.db.execute('INSERT OR REPLACE INTO state VALUES (?, ?)', (key, value))

    def matrix_json(self, path, method='GET', data=None):
        return json.loads(request(self.matrix + '/_matrix/client/v3' + path, self.token, method, data))

    def trusted(self, room):
        state = self.matrix_json('/rooms/' + urllib.parse.quote(room, safe='') + '/state')
        bridge = any(e['type'] in ('m.bridge', 'uk.half-shot.bridge') and e.get('sender') == self.bot
                     and e.get('content', {}).get('protocol', {}).get('id') == 'signal' for e in state)
        if not bridge:
            return False
        if any(e['type'] == 'm.room.encryption' for e in state):
            raise RuntimeError('Encrypted Matrix portal: use the documented private unencrypted homeserver')
        self.own_ghosts = {'@signal_' + e.get('content', {}).get('channel', {}).get('receiver', '') + ':' + self.domain
                           for e in state if e.get('sender') == self.bot and e['type'] in ('m.bridge', 'uk.half-shot.bridge')}
        if self.allowed_rooms:
            return room in self.allowed_rooms
        # Default: only direct-message portals. Explicit room allowlisting enables groups.
        info = [e.get('content', {}) for e in state if e['type'] in ('m.bridge', 'uk.half-shot.bridge') and e.get('sender') == self.bot]
        return any(re.fullmatch(r'(?:PNI:)?[a-fA-F0-9-]{36}', e.get('channel', {}).get('id', '')) for e in info)

    def reply(self, room, event_id, body):
        txn = hashlib.sha256(('reply:' + event_id).encode()).hexdigest()
        self.matrix_json('/rooms/' + urllib.parse.quote(room, safe='') + '/send/m.room.message/' + txn,
                         'PUT', {'msgtype': 'm.text', 'body': body})

    def handle(self, room, event):
        if event.get('sender') in getattr(self, 'own_ghosts', set()):
            return
        if event.get('origin_server_ts', 0) < self.started or not self.ghost.fullmatch(event.get('sender', '')):
            return
        if event.get('type') == 'm.room.encrypted':
            raise RuntimeError('Encrypted Matrix events are not supported by this private relay')
        if event.get('type') != 'm.room.message':
            return
        content = event.get('content', {})
        # Edits/reactions are not new cards. Never publish quoted reply fallbacks.
        if content.get('m.relates_to', {}).get('rel_type') == 'm.replace':
            return
        event_id = event['event_id']
        key = hashlib.sha256((room + '\0' + event_id).encode()).hexdigest()
        try:
            kind = content.get('msgtype')
            if kind not in ('m.text', 'm.image', 'm.video'):
                raise Rejected('Supported posts: text, links, images and videos up to 10 MiB.')
            body = content.get('body', '')
            if not isinstance(body, str) or len(body) > 50000:
                raise Rejected('Text must be at most 50,000 characters.')
            if content.get('m.relates_to', {}).get('m.in_reply_to') and body.startswith('> '):
                body = body.split('\n\n', 1)[1] if '\n\n' in body else ''
            media = None
            if kind != 'm.text':
                if 'file' in content:
                    raise RuntimeError('Encrypted Matrix attachments require the documented unencrypted setup')
                mxc = urllib.parse.urlsplit(content.get('url', ''))
                if mxc.scheme != 'mxc' or mxc.netloc != self.domain or not re.fullmatch(r'/[A-Za-z0-9_-]+', mxc.path):
                    raise Rejected('Media must originate from the private bridge server.')
                if content.get('info', {}).get('size', 0) > MAX_MEDIA:
                    raise Rejected('Media exceeds 10 MiB.')
                # Authenticated Matrix media API; never fetch message-provided HTTP URLs.
                raw = request(self.matrix + '/_matrix/client/v1/media/download/' + urllib.parse.quote(mxc.netloc, safe='') + mxc.path,
                              self.token, limit=MAX_MEDIA)
                media = normalize(raw, kind)
                # Matrix uses body as filename unless a distinct filename accompanies a caption.
                if 'filename' not in content or content.get('filename') == body:
                    body = ''
            elif not body.strip():
                raise Rejected('Send a non-empty message.')
            payload, content_type = multipart(key, body, media)
            request(self.board + '/api/ingest', self.ingest_token, 'POST', payload, content_type)
            self.reply(room, event_id, 'Posted to the public board: ' + self.board + '/#/post/' + key)
        except Rejected as error:
            self.reply(room, event_id, str(error))

    def events(self, room, timeline):
        events = timeline.get('events', [])
        if not timeline.get('limited'):
            return events
        # /sync may truncate a room after downtime. Recover the gap before advancing the global cursor.
        marker = self.get('room:' + room)
        token = timeline.get('prev_batch')
        recovered = []
        for _ in range(1000):
            if not token:
                break
            page = self.matrix_json('/rooms/' + urllib.parse.quote(room, safe='') + '/messages?' +
                                    urllib.parse.urlencode({'from': token, 'dir': 'b', 'limit': 100}))
            chunk = page.get('chunk', [])
            stop = False
            for event in chunk:
                if event.get('event_id') == marker or event.get('origin_server_ts', 0) < self.started:
                    stop = True
                    break
                recovered.append(event)
            if stop or not chunk:
                break
            next_token = page.get('end')
            if next_token == token:
                raise RuntimeError('Matrix history cursor did not advance')
            token = next_token
        else:
            raise RuntimeError('Matrix backlog exceeds recovery limit; operator intervention required')
        return list(reversed(recovered)) + events

    def sync_once(self):
        since = self.get('since')
        query = {'timeout': 30000, 'filter': json.dumps({'room': {'timeline': {'limit': 100}}, 'presence': {'types': []}})}
        if since:
            query['since'] = since
        data = self.matrix_json('/sync?' + urllib.parse.urlencode(query))
        for room, invite in data.get('rooms', {}).get('invite', {}).items():
            members = invite.get('invite_state', {}).get('events', [])
            if any(e.get('type') == 'm.room.member' and e.get('state_key') == self.user
                   and e.get('sender') == self.bot and e.get('content', {}).get('membership') == 'invite' for e in members):
                self.matrix_json('/join/' + urllib.parse.quote(room, safe=''), 'POST', {})
        for room, joined in data.get('rooms', {}).get('join', {}).items():
            timeline = joined.get('timeline', {})
            if not timeline.get('events'):
                continue
            if self.trusted(room):
                for event in self.events(room, timeline):
                    self.handle(room, event)
            # Only committed after every event in this room has been handled successfully.
            self.set('room:' + room, timeline['events'][-1]['event_id'])
        self.set('since', data['next_batch'])

    def run(self):
        delay = 1
        while True:
            try:
                self.sync_once()
                delay = 1
            except Exception as error:
                # Exception messages/HTTP URLs may contain personal IDs or tokens: log only class/status.
                LOG.error('Sync failed (%s, status=%s); cursor retained, retrying', type(error).__name__, getattr(error, 'code', '-'))
                time.sleep(delay + random.random())
                delay = min(delay * 2, 60)

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    Relay().run()
