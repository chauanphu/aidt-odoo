import json
from unittest.mock import patch

from odoo.tests.common import TransactionCase

from odoo.addons.aidt_meeting_minutes.models.summary_client import SummaryError

PATH = ('odoo.addons.aidt_meeting_minutes.models.summary_client.'
        'AidtMeetingSummaryClient._chat')


class FakeResponse:
    def __init__(self, payload):
        self._payload = json.dumps(payload).encode('utf-8')

    def read(self):
        return self._payload

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class SummaryCase(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.client = cls.env['aidt.meeting.summary.client']
        cls.env['ir.config_parameter'].sudo().set_param(
            'aidt_meeting.llm_url', 'http://llm:8003/v1/')
        cls.channel = cls.env['discuss.channel'].create({
            'name': 'Cuộc gọi', 'channel_type': 'channel',
        })
        cls.recording = cls.env['aidt.meeting.recording'].sudo().create({
            'channel_id': cls.channel.id, 'secrecy_at_start': 'thuong',
            'state': 'processing',
        })
        cls.partner = cls.env['res.partner'].create({'name': 'An'})
        cls.env['aidt.meeting.segment'].sudo().create({
            'recording_id': cls.recording.id, 'partner_id': cls.partner.id,
            'start_ms': 0, 'end_ms': 1000, 'text': 'Nội dung cuộc họp',
        })


class TestSummaryClient(SummaryCase):
    def test_ghep_dung_duong_dan_chat_completions(self):
        captured = {}

        def fake_urlopen(req, timeout=None):
            captured['url'] = req.full_url
            return FakeResponse(
                {'choices': [{'message': {'content': 'tóm tắt'}}]})

        with patch('urllib.request.urlopen', side_effect=fake_urlopen):
            self.client._chat('xin chào')
        self.assertEqual(captured['url'], 'http://llm:8003/v1/chat/completions')

    def test_phan_hoi_la_thi_nem_summary_error(self):
        def fake_urlopen(req, timeout=None):
            return FakeResponse({'khong_biet': 1})

        with patch('urllib.request.urlopen', side_effect=fake_urlopen):
            with self.assertRaises(SummaryError):
                self.client._chat('xin chào')

    def test_ban_dai_thi_chia_cua_so_roi_tom_tat_lai(self):
        """Map-reduce không chỉ để lách giới hạn context — nó là thứ giữ cho
        KV cache đủ nhỏ để ba model cùng vừa trên card 16 GB."""
        long_text = '\n'.join(f'[00:{i:02d}] An: câu {i}' for i in range(400))
        calls = []

        def fake_chat(prompt, system_prompt=None):
            calls.append(prompt)
            if system_prompt and 'JSON' in system_prompt:
                return '{"title": "tóm tắt"}'
            return 'tóm tắt phần'

        with patch(PATH, side_effect=fake_chat):
            result = self.client._summarize(long_text)
        self.assertGreater(len(calls), 1)
        self.assertTrue(result)
        # Không chỉ đếm số lần gọi: phải chứng minh CUỘC GỌI CUỐI CÙNG thật
        # sự là bước reduce trên các bản tóm tắt từng phần, chứ không phải
        # một lỗi trả thẳng bản tóm tắt phần cuối — bug kiểu đó vẫn qua được
        # nếu chỉ kiểm tra len(calls) > 1 và assertTrue(result).
        map_calls, reduce_call = calls[:-1], calls[-1]
        for prompt in map_calls:
            self.assertNotIn('tóm tắt phần', prompt)
        self.assertEqual(reduce_call.count('tóm tắt phần'), len(map_calls))


class TestSummaryStage(SummaryCase):
    def test_llm_chet_van_giu_duoc_transcript(self):
        """Lỗi của bộ tóm tắt KHÔNG BAO GIỜ được làm mất transcript — hai
        giai đoạn tách rời chính là để sản phẩm khó tạo lại nhất sống sót."""
        with patch(PATH, side_effect=SummaryError('LLM chết')):
            self.recording._finalize()
        self.assertEqual(self.recording.state, 'done')
        self.assertIn('Nội dung cuộc họp', self.recording.transcript_text)
        self.assertFalse(self.recording.title)
        self.assertIn('LLM chết', self.recording.summary_error)

    def test_tao_lai_tom_tat_duoc_sau_khi_loi(self):
        with patch(PATH, side_effect=SummaryError('chết')):
            self.recording._finalize()
        json_resp = json.dumps({'title': 'tóm tắt lại', 'overview': 'nội dung'})
        with patch(PATH, return_value=json_resp):
            self.recording.action_retry_summary()
        self.assertEqual(self.recording.title, 'tóm tắt lại')
        self.assertFalse(self.recording.summary_error)

    def test_loi_csdl_that_trong_tom_tat_khong_lam_mat_transcript(self):
        """Regression cho savepoint trong `_run_summary`: một câu SQL thật sự
        lỗi ở tầng CSDL (không phải SummaryError của Python) làm cursor rơi
        vào InFailedSqlTransaction — nếu `_run_summary` không tự bọc
        savepoint, `self.sudo().write({'summary_error': ...})` ở khối except
        sẽ tự ném ngoại lệ thứ hai, thoát ra ngoài và bị savepoint của
        `_cron_sweep` bắt lấy, rollback luôn transcript_text/state='done'
        vừa ghi — đúng mất mát mà `_run_summary` cam kết không xảy ra."""
        def db_error(prompt, **kwargs):
            self.env.cr.execute('SELECT 1/0')

        with patch(PATH, side_effect=db_error):
            self.recording._finalize()
        self.assertEqual(self.recording.state, 'done')
        self.assertIn('Nội dung cuộc họp', self.recording.transcript_text)
        self.assertFalse(self.recording.title)
        self.assertTrue(self.recording.summary_error)

    def test_summary_khong_dang_message_vao_chatter(self):
        """Tóm tắt cuộc họp KHÔNG đăng message vào channel hay event chatter."""
        json_resp = json.dumps({'title': 'Tóm tắt họp', 'overview': 'nội dung', 'action_items': [{'task': 'Việc 1'}]})
        with patch(PATH, return_value=json_resp):
            self.recording._run_summary()
        bodies = self.channel.message_ids.mapped('body')
        self.assertFalse(any('Tóm tắt cuộc họp' in (b or '') for b in bodies))
