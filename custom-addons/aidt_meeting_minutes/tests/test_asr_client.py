import json
from unittest.mock import patch

from odoo.tests.common import TransactionCase

from odoo.addons.aidt_meeting_minutes.models.asr_client import AsrError


class FakeResponse:
    def __init__(self, payload):
        self._payload = json.dumps(payload).encode('utf-8')

    def read(self):
        return self._payload

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class AsrCase(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.client = cls.env['aidt.meeting.asr.client']
        cls.env['ir.config_parameter'].sudo().set_param(
            'aidt_meeting.asr_url', 'http://asr:8002/v1/')

    def _call(self, payload, api_key=''):
        self.env['ir.config_parameter'].sudo().set_param(
            'aidt_meeting.asr_api_key', api_key)
        captured = {}

        def fake_urlopen(req, timeout=None):
            captured['url'] = req.full_url
            captured['headers'] = dict(req.headers)
            return FakeResponse(payload)

        with patch('urllib.request.urlopen', side_effect=fake_urlopen):
            result = self.client._transcribe(b'AUDIO', 'a.mp3')
        return result, captured


class TestAsrClient(AsrCase):
    def test_ghep_dung_duong_dan_va_bo_gach_cheo_thua(self):
        _, captured = self._call({'text': 'xin chào'})
        self.assertEqual(captured['url'],
                         'http://asr:8002/v1/audio/transcriptions')

    def test_co_api_key_thi_gui_bearer(self):
        _, captured = self._call({'text': 'a'}, api_key='sk-abc')
        header = {k.lower(): v for k, v in captured['headers'].items()}
        self.assertEqual(header['authorization'], 'Bearer sk-abc')

    def test_khong_co_api_key_thi_bo_han_header(self):
        """Dịch vụ nội bộ không cần key; gửi 'Bearer ' rỗng làm một số
        gateway trả 401 thay vì bỏ qua."""
        _, captured = self._call({'text': 'a'}, api_key='')
        header = {k.lower(): v for k, v in captured['headers'].items()}
        self.assertNotIn('authorization', header)

    def test_doc_duoc_segment_co_moc_thoi_gian(self):
        payload = {'segments': [
            {'start': 0.0, 'end': 1.5, 'text': 'câu một'},
            {'start': 1.5, 'end': 3.0, 'text': 'câu hai'},
        ]}
        result, _ = self._call(payload)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]['start_ms'], 0)
        self.assertEqual(result[1]['end_ms'], 3000)
        self.assertEqual(result[1]['text'], 'câu hai')

    def test_khong_co_segment_thi_lui_ve_mot_doan_duy_nhat(self):
        """Timestamp bên trong Whisper là thứ dễ suy giảm nhất ở một bản
        fine-tune. Thiết kế lấy mốc từ offset của chunk nên vẫn dùng được:
        chỉ cần trả một đoạn phủ trọn chunk."""
        result, _ = self._call({'text': 'toàn bộ nội dung'})
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['start_ms'], 0)
        self.assertIsNone(result[0]['end_ms'])
        self.assertEqual(result[0]['text'], 'toàn bộ nội dung')

    def test_phan_hoi_la_khong_nem_asr_error(self):
        with self.assertRaises(AsrError):
            self._call({'khong_biet': 1})
