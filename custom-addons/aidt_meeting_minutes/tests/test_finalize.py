from odoo.tests.common import TransactionCase

from odoo.tools import mute_logger


class FinalizeCase(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Recording = cls.env['aidt.meeting.recording']
        cls.user = cls.env['res.users'].create({
            'name': 'Chủ trì', 'login': 'f_chutri@test.local',
        })
        cls.channel = cls.env['discuss.channel'].create({
            'name': 'Cuộc gọi', 'channel_type': 'channel',
        })
        cls.channel.add_members(partner_ids=[cls.user.partner_id.id])

    def _recording(self, with_event=False):
        event = False
        if with_event:
            event = self.env['calendar.event'].create({
                'name': 'Họp giao ban',
                'start': '2026-08-04 01:00:00',
                'stop': '2026-08-04 02:00:00',
                'user_id': self.user.id,
                'videocall_channel_id': self.channel.id,
                'partner_ids': [(6, 0, [self.user.partner_id.id])],
            })
        return self.Recording.sudo().create({
            'channel_id': self.channel.id,
            'event_id': event.id if event else False,
            'secrecy_at_start': 'thuong',
            'state': 'processing',
        })

    def _segment(self, recording, text='Xin chào'):
        return self.env['aidt.meeting.segment'].sudo().create({
            'recording_id': recording.id,
            'partner_id': self.user.partner_id.id,
            'start_ms': 0, 'end_ms': 1000, 'text': text,
        })

    def _done_chunk(self, recording):
        """Mẩu 'done' có audio, để `_purge_own_audio`/`_cron_purge_audio` có
        gì đó để dọn."""
        attachment = self.env['ir.attachment'].sudo().create({
            'name': 'a.mp3', 'datas': b'QUJD', 'mimetype': 'audio/mpeg',
        })
        return self.env['aidt.meeting.chunk'].sudo().create({
            'recording_id': recording.id, 'partner_id': self.user.partner_id.id,
            'seq': 0, 'offset_ms': 0, 'duration_ms': 15000,
            'state': 'done', 'attachment_id': attachment.id,
        })


class TestFinalize(FinalizeCase):
    def test_xong_het_chunk_thi_dung_transcript(self):
        rec = self._recording()
        self._segment(rec)
        rec._finalize()
        self.assertEqual(rec.state, 'done')
        self.assertIn('Xin chào', rec.transcript_text)

    def test_con_chunk_pending_thi_chua_hoan_tat(self):
        rec = self._recording()
        self.env['aidt.meeting.chunk'].sudo().create({
            'recording_id': rec.id, 'partner_id': self.user.partner_id.id,
            'seq': 0, 'offset_ms': 0, 'duration_ms': 15000, 'state': 'pending',
        })
        self.Recording._cron_sweep()
        self.assertEqual(rec.state, 'processing')

    def test_co_cuoc_hop_thi_dang_vao_chatter_su_kien(self):
        rec = self._recording(with_event=True)
        self._segment(rec)
        rec._finalize()
        bodies = rec.event_id.message_ids.mapped('body')
        self.assertTrue(any('Xin chào' in (b or '') for b in bodies))

    def test_khong_co_cuoc_hop_thi_dang_vao_kenh(self):
        """Cuộc gọi tự phát: transcript quay lại đúng nơi cuộc gọi diễn ra."""
        rec = self._recording(with_event=False)
        self._segment(rec)
        rec._finalize()
        bodies = self.channel.message_ids.mapped('body')
        self.assertTrue(any('Xin chào' in (b or '') for b in bodies))

    def test_cuoc_goi_bo_do_duoc_quet_sang_processing(self):
        """Kiểu kết thúc phổ biến không phải bấm nút mà là tất cả cùng gập
        máy — không có lớp quét này thì bản ghi treo ở 'recording' mãi."""
        rec = self.Recording.sudo().create({
            'channel_id': self.channel.id, 'secrecy_at_start': 'thuong',
            'state': 'recording',
        })
        self.Recording._cron_sweep()
        self.assertEqual(rec.state, 'processing')

    def test_lan_quet_thu_hai_moi_hoan_tat(self):
        """Bản ghi vừa được phát hiện kết thúc phải chờ sang lượt quét sau
        mới đủ điều kiện hoàn tất — chứng minh phần "processing" của
        _cron_sweep thực sự nhận lại nó ở lần gọi tiếp theo, chứ không phải
        mãi mãi bỏ qua."""
        rec = self.Recording.sudo().create({
            'channel_id': self.channel.id, 'secrecy_at_start': 'thuong',
            'state': 'recording',
        })
        self._segment(rec)
        self.Recording._cron_sweep()
        self.assertEqual(rec.state, 'processing')
        self.Recording._cron_sweep()
        self.assertEqual(rec.state, 'done')
        self.assertIn('Xin chào', rec.transcript_text)

    def test_cuoc_goi_dang_dien_ra_thi_khong_dong(self):
        """Còn phiên RTC sống trên kênh nghĩa là vẫn còn người đang nói —
        lớp quét TUYỆT ĐỐI không được đóng bản ghi trong trường hợp này,
        vì đó sẽ là lỗi nặng nhất của tính năng: cắt ngang cuộc họp đang
        diễn ra."""
        rec = self.Recording.sudo().create({
            'channel_id': self.channel.id, 'secrecy_at_start': 'thuong',
            'state': 'recording',
        })
        member = self.channel.channel_member_ids[0]
        self.env['discuss.channel.rtc.session'].sudo().create({
            'channel_member_id': member.id,
        })
        self.Recording._cron_sweep()
        self.assertEqual(rec.state, 'recording')


class TestFinalizePurge(FinalizeCase):
    """`_purge_own_audio` chạy TRONG `_finalize`, sau khi transcript đã ghi.
    Nó phải: (1) không bao giờ kéo mất transcript nếu bản thân nó lỗi, và
    (2) chỉ đụng tới audio của ĐÚNG bản ghi đang hoàn tất, không phải toàn
    hệ thống — khác với `_cron_purge_audio` chạy theo lịch hàng ngày."""

    def test_loi_xoa_audio_khong_lam_mat_transcript(self):
        """Cấu hình rác (admin gõ tay qua res.config.settings) làm
        `int(...)` ném ValueError bên trong `_purge_own_audio` — lỗi đó
        KHÔNG được phép lan ra ngoài `_finalize` và làm mất transcript vừa
        ghi, dù chạy trong savepoint của `_cron_sweep`."""
        rec = self._recording()
        self._segment(rec)
        self._done_chunk(rec)
        self.env['ir.config_parameter'].sudo().set_param(
            'aidt_meeting.audio_retention_days', 'khong_phai_so')
        with mute_logger('odoo.addons.aidt_meeting_minutes.models.meeting_recording'):
            rec._finalize()
        self.assertEqual(rec.state, 'done')
        self.assertIn('Xin chào', rec.transcript_text)

    def test_hoan_tat_khong_xoa_audio_cua_ban_ghi_khac(self):
        """Hoàn tất bản ghi A không được đụng tới audio của bản ghi B đã
        'done' từ trước — việc dọn KHÔNG giới hạn theo bản ghi là việc
        riêng của `_cron_purge_audio` chạy theo lịch, không phải một hiệu
        ứng phụ bất ngờ của việc hoàn tất một bản ghi khác."""
        self.env['ir.config_parameter'].sudo().set_param(
            'aidt_meeting.audio_retention_days', '0')
        other = self.Recording.sudo().create({
            'channel_id': self.channel.id, 'secrecy_at_start': 'thuong',
            'state': 'done',
        })
        other_chunk = self._done_chunk(other)

        rec = self._recording()
        self._segment(rec)
        rec_chunk = self._done_chunk(rec)
        rec._finalize()

        self.assertFalse(rec_chunk.attachment_id)
        self.assertTrue(other_chunk.attachment_id)
