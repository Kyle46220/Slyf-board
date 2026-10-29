import io
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
            'STATE_DIR': self.directory.name, 'ALLOWED_ROOMS': ''})
        self.env.start()
        self.r = relay.Relay()
        self.event = {'type': 'm.room.message', 'event_id': '$event',
                      'sender': '@signal_aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee:board.local',
                      'origin_server_ts': self.r.started + 1,
                      'content': {'msgtype': 'm.text', 'body': 'Hello public board'}}

    def tearDown(self):
        self.r.db.close()
        self.env.stop()
        self.directory.cleanup()

    def test_ingest_payload_never_contains_sender_and_retry_id_is_stable(self):
        with patch.object(relay, 'request', return_value=b'{}') as req, patch.object(self.r, 'reply') as reply:
            self.r.handle('!room:board.local', self.event)
            first = req.call_args.args[3]
            self.r.handle('!room:board.local', self.event)
            second = req.call_args.args[3]
            self.assertIn(b'Hello public board', first)
            self.assertNotIn(self.event['sender'].encode(), first)
            self.assertNotIn(b'$event', first)
            self.assertEqual(first.split(b'name="event_id"\r\n\r\n')[1][:64], second.split(b'name="event_id"\r\n\r\n')[1][:64])
            self.assertIn('/#/post/', reply.call_args.args[2])

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
            state[0]['content']['channel']['id'] = 'group-id'
            self.assertFalse(self.r.trusted('!room'))
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
        with patch.object(relay, 'request', return_value=b'{}') as req, patch.object(self.r, 'reply'):
            self.r.handle('!room', self.event)
            self.assertNotIn(b'secret', req.call_args.args[3])
            self.assertIn(b'public', req.call_args.args[3])

if __name__ == '__main__': unittest.main()
