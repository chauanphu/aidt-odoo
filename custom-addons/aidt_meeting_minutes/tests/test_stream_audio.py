import io
import json
from unittest.mock import MagicMock, patch

import odoo.tests
from odoo.http import Response
from odoo.tests.common import TransactionCase
from odoo.addons.aidt_meeting_minutes.controllers.main import AidtMeetingController


@odoo.tests.tagged('post_install', '-at_install', 'stream_audio')
class TestStreamAudioEndpoint(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.controller = AidtMeetingController()
        cls.user = cls.env['res.users'].create({
            'name': 'Test User Stream',
            'login': 'test_user_stream@test.local',
        })
        cls.channel = cls.env['discuss.channel'].create({
            'name': 'Test Stream Channel',
            'channel_type': 'channel',
        })

    def _call_endpoint(self, channel_id, audio_bytes, user=None):
        user = user or self.user
        audio_file = io.BytesIO(audio_bytes)

        mock_request = MagicMock()
        mock_request.env = self.env(user=user)

        def fake_make_json_response(data, status=200, headers=None):
            return Response(json.dumps(data), status=status, headers=headers or [('Content-Type', 'application/json')])

        mock_request.make_json_response = fake_make_json_response

        with patch('odoo.addons.aidt_meeting_minutes.controllers.main.request', mock_request):
            return self.controller.stream_audio_subtitle(channel_id, audio_file)

    def test_channel_not_found(self):
        resp = self._call_endpoint(channel_id=999999, audio_bytes=b'A' * 200)
        self.assertEqual(resp.status_code, 404)
        data = json.loads(resp.data)
        self.assertEqual(data, {'error': 'not_found'})

    def test_missing_audio_payload(self):
        mock_request = MagicMock()
        mock_request.env = self.env(user=self.user)

        def fake_make_json_response(data, status=200, headers=None):
            return Response(json.dumps(data), status=status, headers=headers or [('Content-Type', 'application/json')])

        mock_request.make_json_response = fake_make_json_response

        with patch('odoo.addons.aidt_meeting_minutes.controllers.main.request', mock_request):
            resp = self.controller.stream_audio_subtitle(self.channel.id, audio=None)
            self.assertEqual(resp.status_code, 400)
            data = json.loads(resp.data)
            self.assertEqual(data, {'error': 'bad_request'})

    def test_short_audio_chunk(self):
        BusBus = type(self.env['bus.bus'])
        with patch.object(BusBus, '_sendone') as mock_sendone:
            resp = self._call_endpoint(channel_id=self.channel.id, audio_bytes=b'short')
            self.assertEqual(resp.status_code, 200)
            data = json.loads(resp.data)
            self.assertEqual(data, {'ok': True})
            mock_sendone.assert_not_called()

    def test_valid_audio_chunk_broadcasts_bus(self):
        BusBus = type(self.env['bus.bus'])
        with patch.object(BusBus, '_sendone') as mock_sendone:
            resp = self._call_endpoint(channel_id=self.channel.id, audio_bytes=b'A' * 150)
            self.assertEqual(resp.status_code, 200)
            data = json.loads(resp.data)
            self.assertEqual(data, {'ok': True})
            mock_sendone.assert_called_once_with(
                self.channel,
                'aidt_meeting_minutes/subtitle_update',
                {
                    'text': '...',
                    'speaker_name': self.user.partner_id.name,
                    'partner_id': self.user.partner_id.id,
                }
            )
