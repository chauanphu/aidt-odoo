from unittest.mock import patch
import requests

from odoo.tests.common import TransactionCase


class TestAiTrigger(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Recording = cls.env['aidt.meeting.recording']
        cls.user = cls.env['res.users'].create({
            'name': 'Test User',
            'login': 'testuser@example.com',
        })
        cls.channel = cls.env['discuss.channel'].create({
            'name': 'Test Channel',
            'channel_type': 'channel',
        })
        cls.channel.add_members(partner_ids=[cls.user.partner_id.id])
        cls.member = cls.env['discuss.channel.member'].search([
            ('channel_id', '=', cls.channel.id),
            ('partner_id', '=', cls.user.partner_id.id)
        ], limit=1)
        cls.env['discuss.channel.rtc.session'].sudo().create({
            'channel_member_id': cls.member.id,
        })
        cls.recording = cls.Recording.with_user(cls.user)._start_for_channel(cls.channel)

        # Create 2 test chunks
        cls.env['aidt.meeting.chunk'].sudo().create({
            'recording_id': cls.recording.id,
            'partner_id': cls.user.partner_id.id,
            'seq': 0,
            'offset_ms': 0,
            'duration_ms': 30000,
        })
        cls.env['aidt.meeting.chunk'].sudo().create({
            'recording_id': cls.recording.id,
            'partner_id': cls.user.partner_id.id,
            'seq': 1,
            'offset_ms': 30000,
            'duration_ms': 30000,
        })

    def test_action_stop_triggers_ai_service(self):
        with patch('requests.post') as mock_post:
            result = self.recording.with_user(self.user).action_stop()
            self.assertTrue(result)
            self.assertEqual(self.recording.state, 'processing')

            mock_post.assert_called_once()
            args, kwargs = mock_post.call_args
            base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
            expected_webhook = f"{base_url}/aidt_meeting/api/webhook/summary/{self.recording.id}"

            self.assertEqual(args[0], "http://localhost:8000/jobs/process_meeting")
            self.assertEqual(kwargs['json'], {
                'meeting_id': self.recording.id,
                'total_chunks': 2,
                'webhook_url': expected_webhook
            })
            self.assertEqual(kwargs['timeout'], 5)

    def test_action_stop_handles_ai_service_failure_gracefully(self):
        with patch('requests.post', side_effect=requests.exceptions.RequestException("Connection refused")):
            result = self.recording.with_user(self.user).action_stop()
            self.assertTrue(result)
            self.assertEqual(self.recording.state, 'processing')
