import json
from unittest.mock import MagicMock, patch

import odoo.tests
from odoo.tests.common import TransactionCase
from odoo.addons.aidt_meeting_minutes.controllers.main import AidtMeetingController


@odoo.tests.tagged('post_install', '-at_install', 'summary_webhook')
class TestSummaryWebhook(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.controller = AidtMeetingController()
        cls.user = cls.env['res.users'].create({
            'name': 'Test User Webhook',
            'login': 'test_user_webhook@test.local',
        })
        cls.channel = cls.env['discuss.channel'].create({
            'name': 'Test Webhook Channel',
            'channel_type': 'channel',
        })
        cls.recording = cls.env['aidt.meeting.recording'].sudo().create({
            'channel_id': cls.channel.id,
            'state': 'processing',
            'started_by_id': cls.user.id,
            'secrecy_at_start': 'thuong',
        })

    def _call_webhook(self, recording_id, payload):
        mock_request = MagicMock()
        mock_request.env = self.env
        mock_request.jsonrequest = payload

        with patch('odoo.addons.aidt_meeting_minutes.controllers.main.request', mock_request):
            return self.controller.receive_ai_summary(recording_id)

    def test_receive_ai_summary_not_found(self):
        res = self._call_webhook(999999, {})
        self.assertEqual(res, {'status': 'error', 'message': 'Recording not found'})

    def test_receive_ai_summary_success(self):
        payload = {
            'title': 'Project Sync Summary',
            'overview': 'Overview of the project sync meeting.',
            'meeting_minutes': 'Detailed minutes content.',
            'key_points': [{'content': 'Sprint deadline is next Friday'}, {'content': 'Refactoring complete'}],
            'risks': [{'content': 'API latency risk'}],
            'transcript_raw': 'Speaker 1: Hello world\nSpeaker 2: Hi there',
            'action_items': [
                {
                    'task': 'Deploy to staging',
                    'owner': 'Alice',
                    'deadline': '2026-08-12',
                    'priority': 'high',
                    'timestamp': '00:02:15'
                }
            ],
            'decisions': [
                {
                    'content': 'Adopt microservice summary architecture',
                    'timestamp': '00:10:00'
                }
            ]
        }

        res = self._call_webhook(self.recording.id, payload)
        self.assertEqual(res, {'status': 'success'})

        self.recording.invalidate_recordset()
        self.assertEqual(self.recording.state, 'done')
        self.assertEqual(self.recording.title, 'Project Sync Summary')
        self.assertEqual(self.recording.overview, 'Overview of the project sync meeting.')
        self.assertEqual(self.recording.meeting_minutes, 'Detailed minutes content.')
        self.assertEqual(self.recording.transcript_text, 'Speaker 1: Hello world\nSpeaker 2: Hi there')
        self.assertEqual(json.loads(self.recording.key_points), [{'content': 'Sprint deadline is next Friday'}, {'content': 'Refactoring complete'}])
        self.assertEqual(json.loads(self.recording.risks), [{'content': 'API latency risk'}])

        self.assertEqual(len(self.recording.action_item_ids), 1)
        ai = self.recording.action_item_ids[0]
        self.assertEqual(ai.task, 'Deploy to staging')
        self.assertEqual(ai.owner, 'Alice')
        self.assertEqual(ai.deadline, '2026-08-12')
        self.assertEqual(ai.priority, 'high')
        self.assertEqual(ai.timestamp, '00:02:15')

        self.assertEqual(len(self.recording.decision_ids), 1)
        dec = self.recording.decision_ids[0]
        self.assertEqual(dec.content, 'Adopt microservice summary architecture')
        self.assertEqual(dec.timestamp, '00:10:00')

    def test_receive_ai_summary_clears_existing_items(self):
        # Create initial action item and decision
        self.env['aidt.meeting.action.item'].sudo().create({
            'recording_id': self.recording.id,
            'task': 'Old Task',
            'owner': 'Bob',
        })
        self.env['aidt.meeting.decision'].sudo().create({
            'recording_id': self.recording.id,
            'content': 'Old Decision',
        })
        self.assertEqual(len(self.recording.action_item_ids), 1)
        self.assertEqual(len(self.recording.decision_ids), 1)

        payload = {
            'title': 'Updated Title',
            'action_items': [{'task': 'New Task', 'owner': 'Charlie'}],
            'decisions': [{'content': 'New Decision'}],
        }

        res = self._call_webhook(self.recording.id, payload)
        self.assertEqual(res, {'status': 'success'})

        self.recording.invalidate_recordset()
        self.assertEqual(len(self.recording.action_item_ids), 1)
        self.assertEqual(self.recording.action_item_ids[0].task, 'New Task')
        self.assertEqual(len(self.recording.decision_ids), 1)
        self.assertEqual(self.recording.decision_ids[0].content, 'New Decision')
