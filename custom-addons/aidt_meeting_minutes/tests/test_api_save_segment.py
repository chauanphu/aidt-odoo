import json
from unittest.mock import patch
import odoo.tests
from odoo.tests.common import HttpCase


@odoo.tests.tagged('post_install', '-at_install')
class TestApiSaveSegment(HttpCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.speaker = cls.env['res.users'].create({
            'name': 'Test Speaker',
            'login': 'test_speaker_segment@test.local',
        })
        cls.channel = cls.env['discuss.channel'].create({
            'name': 'Test Channel Segment',
            'channel_type': 'channel',
        })
        cls.channel.add_members(partner_ids=[cls.speaker.partner_id.id])

    def test_save_segment_api(self):
        payload = {
            "session_id": "test_sess_123",
            "text": "Hello world",
            "speaker_id": self.speaker.partner_id.id,
            "channel_id": self.channel.id
        }
        json_rpc_payload = {
            "jsonrpc": "2.0",
            "method": "call",
            "params": payload,
            "id": 1
        }
        BusBus = type(self.env['bus.bus'])
        with patch.object(BusBus, '_sendone') as mock_sendone:
            response = self.url_open(
                '/aidt_meeting/api/save_segment',
                data=json.dumps(json_rpc_payload),
                headers={'Content-Type': 'application/json'}
            )
            self.assertEqual(response.status_code, 200)
            resp_json = response.json()
            result = resp_json.get('result', resp_json)
            self.assertTrue(result.get('ok'))

            mock_sendone.assert_called_once_with(
                self.channel,
                'aidt_meeting_minutes/subtitle_update',
                {
                    'text': 'Hello world',
                    'speaker_id': self.speaker.partner_id.id,
                    'speaker_name': self.speaker.partner_id.name,
                    'partner_id': self.speaker.partner_id.id,
                    'session_id': 'test_sess_123',
                    'channel_id': self.channel.id,
                }
            )

    def test_save_segment_api_missing_data(self):
        payload = {
            "session_id": "test_sess_123",
            "text": "",
            "channel_id": self.channel.id
        }
        json_rpc_payload = {
            "jsonrpc": "2.0",
            "method": "call",
            "params": payload,
            "id": 1
        }
        response = self.url_open(
            '/aidt_meeting/api/save_segment',
            data=json.dumps(json_rpc_payload),
            headers={'Content-Type': 'application/json'}
        )
        self.assertEqual(response.status_code, 200)
        resp_json = response.json()
        result = resp_json.get('result', resp_json)
        self.assertEqual(result.get('error'), 'missing_data')

    def test_save_segment_api_invalid_channel_id(self):
        payload = {
            "text": "Hello world",
            "channel_id": "invalid_id"
        }
        json_rpc_payload = {
            "jsonrpc": "2.0",
            "method": "call",
            "params": payload,
            "id": 1
        }
        response = self.url_open(
            '/aidt_meeting/api/save_segment',
            data=json.dumps(json_rpc_payload),
            headers={'Content-Type': 'application/json'}
        )
        self.assertEqual(response.status_code, 200)
        resp_json = response.json()
        result = resp_json.get('result', resp_json)
        self.assertEqual(result.get('error'), 'invalid_channel_id')

    def test_save_segment_creates_db_record_with_invalid_timestamps(self):
        # Create an active recording for the channel
        member = self.env['discuss.channel.member'].search([
            ('channel_id', '=', self.channel.id),
            ('partner_id', '=', self.speaker.partner_id.id),
        ], limit=1)
        self.env['discuss.channel.rtc.session'].sudo().create({
            'channel_member_id': member.id,
        })
        recording = self.env['aidt.meeting.recording'].with_user(
            self.speaker)._start_for_channel(self.channel)

        payload = {
            "session_id": "test_sess_456",
            "text": "Saved segment transcript with bad timestamps",
            "speaker_id": self.speaker.partner_id.id,
            "channel_id": self.channel.id,
            "start_ms": "not_an_int",
            "end_ms": "also_invalid"
        }
        json_rpc_payload = {
            "jsonrpc": "2.0",
            "method": "call",
            "params": payload,
            "id": 2
        }
        response = self.url_open(
            '/aidt_meeting/api/save_segment',
            data=json.dumps(json_rpc_payload),
            headers={'Content-Type': 'application/json'}
        )
        self.assertEqual(response.status_code, 200)
        resp_json = response.json()
        result = resp_json.get('result', resp_json)
        self.assertTrue(result.get('ok'))

        # Verify segment was created with fallback timestamps 0, 0
        segment = self.env['aidt.meeting.segment'].search([
            ('recording_id', '=', recording.id),
            ('text', '=', 'Saved segment transcript with bad timestamps')
        ], limit=1)
        self.assertTrue(segment.exists())
        self.assertEqual(segment.partner_id.id, self.speaker.partner_id.id)
        self.assertEqual(segment.start_ms, 0)
        self.assertEqual(segment.end_ms, 0)
