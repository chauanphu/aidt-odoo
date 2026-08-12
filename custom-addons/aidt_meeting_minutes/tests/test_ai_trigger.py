import base64
import json
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

import requests

from odoo import fields
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged('post_install', '-at_install')
class TestAiTrigger(TransactionCase):
    """Bàn giao job sang docker/ai_worker.

    KHÔNG gọi `action_stop()` để kiểm tra payload: `action_stop` đẩy phần
    trigger sang một thread ngủ 10 giây (đợi mẩu cuối của mọi máy tới nơi),
    nên `requests.post` chưa hề được gọi lúc `action_stop` trả về. Test
    trước đây `assert_called_once()` ngay sau đó và vì vậy không thể xanh.
    Ở đây tách đôi: trạng thái kiểm qua `action_stop`, payload kiểm bằng
    cách gọi thẳng `_trigger_ai_service`.
    """

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
        # Kênh phải là PHÒNG HỌP: từ 19.0.1.4.0 (Task 4), `_start_for_channel`
        # đòi có `calendar.event`, và chỉ chủ trì (`event.user_id`) mới bật
        # được. PHẢI gắn event TRƯỚC khi tạo phiên RTC bên dưới — chốt chủ
        # phòng chỉ xảy ra lúc TẠO phiên, không hồi tố khi event đến sau.
        now = fields.Datetime.now()
        cls.event = cls.env['calendar.event'].with_context(
            no_mail_to_attendees=True, mail_create_nolog=True,
            mail_notrack=True,
        ).create({
            'name': 'Cuộc họp thử',
            'start': now - timedelta(minutes=5),
            'stop': now + timedelta(hours=1),
            'user_id': cls.user.id,
            'videocall_channel_id': cls.channel.id,
        })
        cls.member = cls.env['discuss.channel.member'].search([
            ('channel_id', '=', cls.channel.id),
            ('partner_id', '=', cls.user.partner_id.id),
        ], limit=1)
        cls.env['discuss.channel.rtc.session'].sudo().create({
            'channel_member_id': cls.member.id,
        })
        cls.recording = cls.Recording.with_user(cls.user)._start_for_channel(
            cls.channel)

        # Mẩu PHẢI có attachment thật: `_trigger_ai_service` bỏ qua mẩu không
        # có dữ liệu, nên mẩu rỗng không xuất ra tệp nào và cũng không được
        # đếm vào `total_chunks`.
        for seq, offset in ((0, 0), (1, 30000)):
            attachment = cls.env['ir.attachment'].sudo().create({
                'name': f'chunk-{seq}.webm',
                'datas': base64.b64encode(b'FAKE-AUDIO-%d' % seq),
                'mimetype': 'audio/webm',
            })
            cls.env['aidt.meeting.chunk'].sudo().create({
                'recording_id': cls.recording.id,
                'partner_id': cls.user.partner_id.id,
                'seq': seq,
                'offset_ms': offset,
                'duration_ms': 30000,
                'attachment_id': attachment.id,
            })

    def test_action_stop_chuyen_sang_dang_xu_ly(self):
        with patch('requests.post'):
            self.assertTrue(self.recording.with_user(self.user).action_stop())
        self.assertEqual(self.recording.state, 'processing')

    def test_payload_gui_sang_worker(self):
        with patch('requests.post') as mock_post:
            self.recording._trigger_ai_service()

        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        self.assertEqual(args[0], 'http://ai-worker:8000/jobs/process_meeting')
        self.assertEqual(kwargs['timeout'], 5)

        payload = kwargs['json']
        self.assertEqual(payload['meeting_id'], self.recording.id)
        self.assertEqual(payload['total_chunks'], 2)
        self.assertTrue(payload['webhook_url'].endswith(
            f'/aidt_meeting/api/webhook/summary/{self.recording.id}'))
        # Cấu hình phải ĐI KÈM job. Bản trước worker ghim cứng model/prompt
        # nên mọi ô trong Cài đặt đều không điều khiển gì.
        self.assertEqual(payload['asr_model'], 'large-v3')
        self.assertEqual(payload['asr_language'], 'vi')
        self.assertEqual(payload['llm_model'], 'gemma3:12b-it-qat')
        # Mặc định KHÔNG mồi prompt: `initial_prompt` làm Whisper đọc tiếp
        # prompt và nuốt mất lời nói thật (bản ghi 2858, mất 44 giây). Gửi
        # `None` nghĩa là "không đặt", worker để `initial_prompt=None`.
        self.assertIsNone(payload['asr_prompt'])

    def test_xuat_mau_audio_gom_theo_nguoi_noi(self):
        """Tên tệp phải mang partner id + take + `seq` GỐC của chính lần ghi đó.

        `seq` là duy nhất theo TỪNG (NGƯỜI, LẦN GHI) chứ không phải theo bản
        ghi, nên đánh số lại thành một dãy `chunk_{idx}` phẳng (bản cũ nhất)
        sẽ trộn lẫn hai người và làm mất thứ tự thời gian trong mỗi luồng.
        Worker dựa vào đúng cách đặt tên này để nối lại từng luồng một.
        """
        with patch('requests.post'):
            self.recording._trigger_ai_service()

        chunk_dir = Path(f'/var/lib/odoo/meetings/{self.recording.id}')
        partner_id = self.user.partner_id.id
        for seq in (0, 1):
            self.assertTrue(
                (chunk_dir / f'spk{partner_id}_t0_{seq:05d}.webm').exists())

        meta = json.loads((chunk_dir / 'metadata.json').read_text())
        self.assertEqual(len(meta['speakers']), 1)
        speaker = meta['speakers'][0]
        self.assertEqual(speaker['partner_id'], partner_id)
        self.assertEqual(len(speaker['takes']), 1)
        take0 = speaker['takes'][0]
        self.assertEqual(take0['take'], 0)
        self.assertEqual(len(take0['files']), 2)
        # Mốc bắt đầu của LẦN GHI là offset của mẩu sớm nhất, không phải của
        # mẩu cuối cùng được duyệt.
        self.assertEqual(take0['offset_ms'], 0)

    def test_worker_khong_goi_duoc_thi_danh_dau_loi(self):
        """Trước đây lỗi ở bước này chỉ ghi log: bản ghi nằm mãi ở
        `processing` và từ giao diện thì một job hỏng trông giống hệt một
        job đang chạy."""
        with patch('requests.post',
                   side_effect=requests.exceptions.RequestException('refused')):
            self.recording._trigger_ai_service()
        self.assertEqual(self.recording.state, 'failed')

    def test_metadata_gom_theo_nguoi_va_take(self):
        """`seq` đếm lại từ 0 mỗi take, nên thiếu `t{take}` trong tên tệp thì
        lần ghi tiếp GHI ĐÈ tệp của lần trước."""
        import base64
        attachment = self.env['ir.attachment'].sudo().create({
            'name': 'chunk-take1.webm',
            'datas': base64.b64encode(b'TAKE-1-AUDIO'),
            'mimetype': 'audio/webm',
        })
        self.env['aidt.meeting.chunk'].sudo().create({
            'recording_id': self.recording.id,
            'partner_id': self.user.partner_id.id,
            'take': 1, 'seq': 0,
            'offset_ms': 90000, 'duration_ms': 30000,
            'attachment_id': attachment.id,
        })
        self.env['aidt.meeting.pause'].sudo().create({
            'recording_id': self.recording.id,
            'paused_at_ms': 60000, 'resumed_at_ms': 90000,
        })

        with patch('requests.post'):
            self.recording._trigger_ai_service()

        chunk_dir = Path(f'/var/lib/odoo/meetings/{self.recording.id}')
        partner_id = self.user.partner_id.id
        self.assertTrue((chunk_dir / f'spk{partner_id}_t0_00000.webm').exists())
        self.assertTrue((chunk_dir / f'spk{partner_id}_t1_00000.webm').exists())

        meta = json.loads((chunk_dir / 'metadata.json').read_text())
        speaker = meta['speakers'][0]
        self.assertEqual(len(speaker['takes']), 2)
        take0, take1 = speaker['takes']
        self.assertEqual(take0['take'], 0)
        self.assertEqual(take0['offset_ms'], 0)
        self.assertEqual(take1['take'], 1)
        self.assertEqual(take1['offset_ms'], 90000)
        self.assertEqual(meta['pauses'],
                         [{'paused_at_ms': 60000, 'resumed_at_ms': 90000}])

    def test_khoang_dung_chua_ghi_tiep_xuat_null(self):
        """Cuộc họp kết thúc ngay lúc đang dừng (chưa từng ghi tiếp):
        `resumed_at_ms` phải xuất ra `null`, KHÔNG PHẢI `0`.

        Trường `Integer` của Odoo không phân biệt được rỗng với số 0 khi đọc
        — cả hai đều trả về `0`. Nếu xuất thẳng giá trị đó, worker đọc
        `resumed_at_ms: 0` sẽ hiểu nhầm thành "đã ghi tiếp ngay tại mốc 0 ms
        kể từ đầu cuộc họp", tức đảo ngược hoàn toàn ý nghĩa thật: khoảng
        dừng này kéo dài tới hết cuộc họp, không phải dài đúng 0 ms ở đầu.
        """
        self.env['aidt.meeting.pause'].sudo().create({
            'recording_id': self.recording.id,
            'paused_at_ms': 45000,
        })

        with patch('requests.post'):
            self.recording._trigger_ai_service()

        chunk_dir = Path(f'/var/lib/odoo/meetings/{self.recording.id}')
        meta = json.loads((chunk_dir / 'metadata.json').read_text())
        pause = next(p for p in meta['pauses'] if p['paused_at_ms'] == 45000)
        self.assertIsNone(pause['resumed_at_ms'])

    def test_take_toan_mau_rong_khong_sinh_muc_take_rong(self):
        """Một take mà MỌI mẩu đều không có dữ liệu (attachment rỗng) không
        được sinh mục `take` rỗng trong metadata.

        Guard bỏ qua mẩu rỗng (`continue`) phải đứng TRƯỚC bước gom vào
        `speakers`/`takes`; test này khoá thứ tự đó lại — đảo ngược hai dòng
        về sau sẽ làm test đỏ thay vì lặng lẽ sinh ra một take rỗng.
        """
        empty_attachment = self.env['ir.attachment'].sudo().create({
            'name': 'chunk-empty.webm',
            'mimetype': 'audio/webm',
        })
        self.env['aidt.meeting.chunk'].sudo().create({
            'recording_id': self.recording.id,
            'partner_id': self.user.partner_id.id,
            'take': 2, 'seq': 0,
            'offset_ms': 120000, 'duration_ms': 30000,
            'attachment_id': empty_attachment.id,
        })

        with patch('requests.post'):
            self.recording._trigger_ai_service()

        chunk_dir = Path(f'/var/lib/odoo/meetings/{self.recording.id}')
        meta = json.loads((chunk_dir / 'metadata.json').read_text())
        speaker = meta['speakers'][0]
        takes = [t['take'] for t in speaker['takes']]
        self.assertNotIn(2, takes)


@tagged('post_install', '-at_install')
class TestKhongThuDuocTieng(TransactionCase):
    """Người có mặt trong cuộc gọi mà không có mẩu âm thanh nào phải LỘ RA.

    Đây là hỏng IM LẶNG đã xảy ra thật (bản ghi 5641, 12/08/2026): người dự có
    phiên RTC đúng lúc bấm bật ghi nhưng gửi lên 0 mẩu, toàn bộ phần phát biểu
    của họ biến mất khỏi biên bản mà không một dấu hiệu nào. Chủ trì chỉ phát
    hiện khi đọc biên bản thấy mọi câu đều mang một cái tên.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Recording = cls.env['aidt.meeting.recording']
        cls.host = cls.env['res.users'].create({
            'name': 'Chủ trì', 'login': 'chu-tri-khongtieng',
        })
        cls.guest = cls.env['res.users'].create({
            'name': 'Người dự im lặng', 'login': 'nguoi-du-khongtieng',
        })
        cls.channel = cls.env['discuss.channel'].create({
            'name': 'Phòng họp kiểm thiếu tiếng', 'channel_type': 'channel',
        })
        cls.channel.add_members(
            partner_ids=[cls.host.partner_id.id, cls.guest.partner_id.id])
        cls.env['calendar.event'].with_context(
            mail_create_nolog=True).create({
                'name': 'Họp kiểm thiếu tiếng',
                'start': fields.Datetime.now(),
                'stop': fields.Datetime.now() + timedelta(hours=1),
                'user_id': cls.host.id,
                'videocall_channel_id': cls.channel.id,
            })
        # Cả hai đều CÓ MẶT trong cuộc gọi.
        for user in (cls.host, cls.guest):
            member = cls.env['discuss.channel.member'].search([
                ('channel_id', '=', cls.channel.id),
                ('partner_id', '=', user.partner_id.id),
            ], limit=1)
            cls.env['discuss.channel.rtc.session'].sudo().create({
                'channel_member_id': member.id,
            })
        cls.recording = cls.Recording.with_user(cls.host)._start_for_channel(
            cls.channel)
        # ...nhưng CHỈ chủ trì gửi được mẩu lên.
        attachment = cls.env['ir.attachment'].sudo().create({
            'name': 'chunk-0.webm', 'raw': b'FAKE-AUDIO', 'mimetype': 'audio/webm',
        })
        cls.env['aidt.meeting.chunk'].sudo().create({
            'recording_id': cls.recording.id,
            'partner_id': cls.host.partner_id.id,
            'seq': 0, 'offset_ms': 0, 'duration_ms': 30000,
            'attachment_id': attachment.id,
        })

    def test_dang_ghi_thi_chua_canh_bao(self):
        """Im lặng lúc đang họp là bình thường — chưa tới lượt người ta nói."""
        self.assertEqual(self.recording.state, 'recording')
        self.assertFalse(self.recording.no_audio_warning)
        self.assertFalse(self.recording.no_audio_partner_ids)

    def test_hop_xong_thi_neu_dich_danh_nguoi_khong_co_tieng(self):
        self.recording.sudo().state = 'done'
        self.recording.invalidate_recordset(
            ['no_audio_partner_ids', 'no_audio_warning'])
        self.assertEqual(
            self.recording.no_audio_partner_ids, self.guest.partner_id)
        self.assertNotIn(
            self.host.partner_id, self.recording.no_audio_partner_ids)
        self.assertIn('Người dự im lặng', self.recording.no_audio_warning)

    def test_moi_nguoi_deu_co_tieng_thi_khong_canh_bao(self):
        attachment = self.env['ir.attachment'].sudo().create({
            'name': 'chunk-guest.webm', 'raw': b'FAKE', 'mimetype': 'audio/webm',
        })
        self.env['aidt.meeting.chunk'].sudo().create({
            'recording_id': self.recording.id,
            'partner_id': self.guest.partner_id.id,
            'seq': 0, 'offset_ms': 0, 'duration_ms': 30000,
            'attachment_id': attachment.id,
        })
        self.recording.sudo().state = 'done'
        self.recording.invalidate_recordset(
            ['no_audio_partner_ids', 'no_audio_warning'])
        self.assertFalse(self.recording.no_audio_partner_ids)
        self.assertFalse(self.recording.no_audio_warning)
