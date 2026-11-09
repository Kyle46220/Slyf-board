import base64
import hashlib
import io
import urllib.error
import json
import os
from pathlib import Path
import tempfile
import shutil
import subprocess
import unittest
from unittest.mock import patch
from PIL import Image
import relay

class RelayTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.env = patch.dict(os.environ, {
            'MATRIX_URL': 'http://synapse:8008', 'MATRIX_TOKEN': 'private',
            'MATRIX_USER': '@board:board.local', 'BRIDGE_BOT': '@signalbot:board.local',
            'BOARD_URL': 'https://board.example', 'INGEST_TOKEN': 'a' * 64,
            'STATE_DIR': self.directory.name, 'ALLOWED_ROOMS': '',
            'GROUP_POSTING': 'disabled', 'BOT_MENTION_IDS': ''})
        self.env.start()
        self.r = relay.Relay()
        self.event = {'type': 'm.room.message', 'event_id': '$event',
                      'sender': '@signal_aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee:board.local',
                      'origin_server_ts': self.r.started + 1,
                      'content': {'msgtype': 'm.text', 'body': 'Hello public board'}}

    def board_response(self, url, token, method='GET', data=None, *args, **kwargs):
        if method == 'POST':
            key = data.split(b'name="event_id"\r\n\r\n')[1][:64].decode()
        else:
            key = url.rsplit('/', 1)[-1]
        return json.dumps({'hash': key}).encode()

    def group_state(self):
        return [{'type': 'm.bridge', 'sender': self.r.bot, 'content': {
            'protocol': {'id': 'signal'}, 'channel': {'id': base64.b64encode(b'g' * 32).decode()}}}]

    def enable_group(self):
        self.r.group_posting = 'mentions'
        with patch.object(self.r, 'matrix_json', return_value=self.group_state()):
            self.assertTrue(self.r.trusted('!group'))

    def tearDown(self):
        self.r.db.close()
        self.env.stop()
        self.directory.cleanup()

    def test_ingest_payload_never_contains_sender_and_retry_id_is_stable(self):
        with patch.object(relay, 'request', side_effect=self.board_response) as req, patch.object(self.r, 'reply') as reply:
            self.r.handle('!room:board.local', self.event)
            first = req.call_args_list[0].args[3]
            self.r.handle('!room:board.local', self.event)
            second = req.call_args_list[2].args[3]
            self.assertIn(b'Hello public board', first)
            self.assertNotIn(self.event['sender'].encode(), first)
            self.assertNotIn(b'$event', first)
            self.assertEqual(first.split(b'name="event_id"\r\n\r\n')[1][:64], second.split(b'name="event_id"\r\n\r\n')[1][:64])
            self.assertIn('https://board.example/post/', reply.call_args.args[2])
            self.assertNotIn('/#/', reply.call_args.args[2])
            self.assertEqual(req.call_args_list[1].args[0], 'https://board.example/api/posts/' + hashlib.sha256(('!room:board.local\0' + self.event['event_id']).encode()).hexdigest())

    def test_ignores_old_non_signal_own_echoes_and_edits(self):
        cases = [dict(self.event, sender='@other:board.local'), dict(self.event, origin_server_ts=0),
                 dict(self.event, content={'m.relates_to': {'rel_type': 'm.replace'}})]
        with patch.object(relay, 'request') as req:
            for event in cases: self.r.handle('!room', event)
            self.r.own_ghosts = {self.event['sender']}
            self.r.handle('!room', self.event)
            req.assert_not_called()

    def test_bridge_state_authentication_dm_group_and_encryption(self):
        state = [{'type': 'm.bridge', 'sender': self.r.bot, 'content': {
            'protocol': {'id': 'signal'}, 'channel': {'id': 'aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee'}}}]
        with patch.object(self.r, 'matrix_json', return_value=state):
            self.assertTrue(self.r.trusted('!room'))
            state[0]['content']['channel']['id'] = base64.b64encode(b'g' * 32).decode()
            self.assertFalse(self.r.trusted('!room'))
            self.r.group_posting = 'mentions'
            self.r.allowed_rooms = {'!room'}
            self.assertTrue(self.r.trusted('!room'))
            state.append({'type': 'm.room.encryption'})
            with self.assertRaises(RuntimeError): self.r.trusted('!room')
            state[0]['sender'] = '@fake:board.local'
            self.assertFalse(self.r.trusted('!room'))

    def test_media_cannot_fetch_arbitrary_urls(self):
        self.event['content'] = {'msgtype': 'm.image', 'url': 'https://internal/secret', 'body': 'file'}
        with patch.object(relay, 'request') as req, patch.object(self.r, 'reply') as reply:
            self.r.handle('!room', self.event)
            req.assert_not_called()
            self.assertIn('private bridge', reply.call_args.args[2])

    def test_image_reencoding_removes_exif(self):
        source = io.BytesIO()
        image = Image.new('RGB', (5, 5), 'red')
        exif = Image.Exif(); exif[270] = 'private metadata'
        image.save(source, format='JPEG', exif=exif)
        raw, mime = relay.normalize(source.getvalue(), 'm.image')
        self.assertEqual(mime, 'image/webp')
        with Image.open(io.BytesIO(raw)) as clean:
            self.assertEqual(dict(clean.getexif()), {})
        self.assertNotIn(b'private metadata', raw)

    @unittest.skipUnless(shutil.which('ffmpeg'), 'ffmpeg unavailable')
    def test_video_transcodes_to_mp4(self):
        source = Path(self.directory.name) / 'source.mp4'
        subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i', 'color=c=red:s=32x32:d=0.1',
                        '-metadata', 'title=private metadata', '-c:v', 'libx264', str(source)], check=True)
        raw, mime = relay.normalize(source.read_bytes(), 'm.video')
        self.assertEqual(mime, 'video/mp4')
        self.assertEqual(raw[4:8], b'ftyp')
        self.assertNotIn(b'private metadata', raw)

    def test_failed_ingest_does_not_advance_sync_checkpoint(self):
        self.r.set('since', 'previous')
        data = {'next_batch': 'next', 'rooms': {'join': {'!room': {'timeline': {'events': [self.event]}}}}}
        with patch.object(self.r, 'matrix_json', return_value=data), patch.object(self.r, 'trusted', return_value=True), patch.object(relay, 'request', side_effect=OSError('offline')):
            with self.assertRaises(OSError): self.r.sync_once()
        self.assertEqual(self.r.get('since'), 'previous')

    def test_limited_sync_recovers_gap_in_chronological_order(self):
        older = dict(self.event, event_id='$older')
        self.r.set('room:!room', '$marker')
        with patch.object(self.r, 'matrix_json', return_value={'chunk': [older, {'event_id': '$marker'}], 'end': 'end'}):
            events = self.r.events('!room', {'limited': True, 'prev_batch': 'prev', 'events': [self.event]})
        self.assertEqual([e['event_id'] for e in events], ['$older', '$event'])

    def test_reply_fallback_is_removed(self):
        self.event['content'] = {'msgtype': 'm.text', 'body': '> <@private:server> secret\n\npublic',
                                 'm.relates_to': {'m.in_reply_to': {'event_id': '$old'}}}
        with patch.object(relay, 'request', side_effect=self.board_response) as req, patch.object(self.r, 'reply'):
            self.r.handle('!room', self.event)
            self.assertNotIn(b'secret', req.call_args_list[0].args[3])
            self.assertIn(b'public', req.call_args_list[0].args[3])


    def test_group_only_publishes_structured_bot_mentions(self):
        self.enable_group()
        cases = [
            ({'msgtype': 'm.text', 'body': '@board plain text'}, False),
            ({'msgtype': 'm.text', 'body': 'everyone', 'm.mentions': {'room': True}}, False),
            ({'msgtype': 'm.text', 'body': 'other', 'm.mentions': {'user_ids': [self.event['sender']]}}, False),
            ({'msgtype': 'm.text', 'body': 'malformed', 'm.mentions': {'user_ids': self.r.user}}, False),
            ({'msgtype': 'm.text', 'body': 'public', 'm.mentions': {'user_ids': [self.r.user]}}, True),
        ]
        for content, expected in cases:
            with self.subTest(content=content), patch.object(relay, 'request', side_effect=self.board_response) as req, patch.object(self.r, 'reply') as reply:
                self.r.handle('!group', dict(self.event, content=content))
                self.assertEqual(req.called, expected)
                self.assertEqual(reply.called, expected)

    def test_reply_notification_and_quoted_bot_mention_are_not_triggers(self):
        self.enable_group()
        content = {'msgtype': 'm.text', 'body': '> quoted bot\n\nprivate reply',
                   'm.mentions': {'user_ids': [self.r.user]},
                   'm.relates_to': {'m.in_reply_to': {'event_id': '$reply'}}}
        for html in [None, '<mx-reply><a href="https://matrix.to/#/@board:board.local">bot</a></mx-reply>private reply']:
            c = dict(content)
            if html: c.update(format='org.matrix.custom.html', formatted_body=html)
            with patch.object(relay, 'request') as req:
                self.r.handle('!group', dict(self.event, content=c))
                req.assert_not_called()
        content.update(format='org.matrix.custom.html', formatted_body='<mx-reply>quote</mx-reply><a href="https://matrix.to/#/%40board%3Aboard.local">bot</a> public')
        with patch.object(relay, 'request', side_effect=self.board_response) as req, patch.object(self.r, 'reply'):
            self.r.handle('!group', dict(self.event, content=content))
            self.assertIn(b'private reply', req.call_args_list[0].args[3])
            self.assertNotIn(b'quoted bot', req.call_args_list[0].args[3])

    def test_group_ghost_alias_and_own_echo(self):
        self.enable_group()
        own = '@signal_11111111-2222-3333-4444-555555555555:board.local'
        self.r.mention_ids.add(own)
        self.r.own_ghosts.add(own)
        content = {'msgtype': 'm.text', 'body': 'publish', 'm.mentions': {'user_ids': [own]}}
        with patch.object(relay, 'request', side_effect=self.board_response) as req, patch.object(self.r, 'reply'):
            self.r.handle('!group', dict(self.event, content=content))
            self.assertTrue(req.called)
            req.reset_mock()
            self.r.handle('!group', dict(self.event, content=content, sender=own))
            req.assert_not_called()

    def test_group_media_requires_mention_and_preserves_caption(self):
        self.enable_group()
        source = io.BytesIO(); Image.new('RGB', (5, 5), 'red').save(source, format='JPEG')
        content = {'msgtype': 'm.image', 'body': 'bot public caption', 'filename': 'image.jpg',
                   'url': 'mxc://board.local/media123', 'm.mentions': {'user_ids': [self.r.user]}}
        def response(url, token, *args, **kwargs):
            return source.getvalue() if '/media/download/' in url else self.board_response(url, token, *args, **kwargs)
        with patch.object(relay, 'request', side_effect=response) as req, patch.object(self.r, 'reply'):
            self.r.handle('!group', dict(self.event, content=content))
            upload = next(c for c in req.call_args_list if c.args[0].endswith('/api/ingest'))
            self.assertIn(b'bot public caption', upload.args[3])
            self.assertIn(b'image/webp', upload.args[3])
            req.reset_mock(); content.pop('m.mentions')
            self.r.handle('!group', dict(self.event, content=content)); req.assert_not_called()

    def test_group_cutoff_skips_history_and_allowlist_still_restricts(self):
        self.enable_group()
        self.r.group_started = self.event['origin_server_ts'] + 1
        content = {'msgtype': 'm.text', 'body': 'old', 'm.mentions': {'user_ids': [self.r.user]}}
        with patch.object(relay, 'request') as req:
            self.r.handle('!group', dict(self.event, content=content)); req.assert_not_called()
        self.r.allowed_rooms = {'!different'}
        with patch.object(self.r, 'matrix_json', return_value=self.group_state()):
            self.assertFalse(self.r.trusted('!group'))
        self.r.allowed_rooms.clear()
        with patch.object(self.r, 'matrix_json', return_value=[{'type':'m.bridge','sender':'@fake:board.local','content':self.group_state()[0]['content']}]):
            self.assertFalse(self.r.trusted('!group'))

    def test_invites_accept_bridge_bot_and_local_ghost_only(self):
        self.r.group_posting = 'mentions'
        def invite(sender, target=None):
            return {'invite_state': {'events': [{'type': 'm.room.member', 'state_key': target or self.r.user,
                    'sender': sender, 'content': {'membership': 'invite'}}]}}
        invites = {'!bot': invite(self.r.bot), '!group': invite(self.event['sender']),
                   '!other': invite('@other:board.local'), '!foreign': invite('@signal_abc:evil.example'),
                   '!wrongtarget': invite(self.event['sender'], '@other:board.local')}
        with patch.object(self.r, 'matrix_json') as req:
            self.r.join_invites(invites)
            self.assertEqual({c.args[0] for c in req.call_args_list}, {'/join/%21bot', '/join/%21group'})
        self.r.group_posting = 'disabled'
        with patch.object(self.r, 'matrix_json') as req:
            self.r.join_invites({'!group': invite(self.event['sender'])}); req.assert_not_called()

    def test_invalid_ingest_response_or_unreadable_post_never_confirms(self):
        key = hashlib.sha256(('!room\0' + self.event['event_id']).encode()).hexdigest()
        for replies in [[b'<html>wrong page</html>'], [b'{}'], [b'{"hash":"wrong"}'],
                        [json.dumps({'hash':key}).encode(), b'{"hash":"wrong"}']]:
            with self.subTest(replies=replies), patch.object(relay, 'request', side_effect=replies), patch.object(self.r, 'reply') as reply:
                with self.assertRaises((RuntimeError, ValueError)):
                    self.r.handle('!room', self.event)
                reply.assert_not_called()
        missing = urllib.error.HTTPError('https://board.example', 404, 'missing', {}, None)
        with patch.object(relay, 'request', side_effect=[json.dumps({'hash':key}).encode(), missing]), patch.object(self.r, 'reply') as reply:
            with self.assertRaises(urllib.error.HTTPError): self.r.handle('!room', self.event)
            reply.assert_not_called()

    def test_deleted_duplicate_is_not_reported_as_posted(self):
        key = hashlib.sha256(('!room\0' + self.event['event_id']).encode()).hexdigest()
        missing = urllib.error.HTTPError('https://board.example', 404, 'missing', {}, None)
        with patch.object(relay, 'request', side_effect=[json.dumps({'hash':key, 'duplicate': True}).encode(), missing]), patch.object(self.r, 'reply') as reply:
            self.r.handle('!room', self.event)
            self.assertIn('previously removed', reply.call_args.args[2])
            self.assertNotIn('Posted to', reply.call_args.args[2])

    def test_http_client_identifies_itself_and_public_reads_have_no_token(self):
        with patch.object(relay.OPENER, 'open', return_value=io.BytesIO(b'{}')) as opener:
            relay.request('https://board.example/api/posts', '')
            headers = dict(opener.call_args.args[0].header_items())
            self.assertEqual(headers['User-agent'], 'SlyfBoard-Relay/1.0')
            self.assertNotIn('Authorization', headers)

if __name__ == '__main__': unittest.main()
