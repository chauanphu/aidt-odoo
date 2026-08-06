from unittest.mock import patch

from odoo.tests.common import TransactionCase

from odoo.tools import mute_logger

BROADCAST = ('odoo.addons.aidt_meeting_minutes.models.meeting_recording.'
             'AidtMeetingRecording._broadcast_state')
LOGGER = 'odoo.addons.aidt_meeting_minutes.models.meeting_recording'


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

    def test_finalize_khong_dang_message_vao_chatter(self):
        """Hoàn tất bản ghi KHÔNG đăng message vào chatter sự kiện hay kênh."""
        rec = self._recording(with_event=True)
        self._segment(rec)
        rec._finalize()
        event_bodies = rec.event_id.message_ids.mapped('body')
        self.assertFalse(any('Xin chào' in (b or '') for b in event_bodies))

        rec_channel = self._recording(with_event=False)
        self._segment(rec_channel)
        rec_channel._finalize()
        channel_bodies = self.channel.message_ids.mapped('body')
        self.assertFalse(any('Xin chào' in (b or '') for b in channel_bodies))

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


class TestSweepRobustness(FinalizeCase):
    def test_mot_ban_ghi_hong_khong_chan_ca_luot_quet(self):
        """Vòng "đóng bản ghi bỏ dở" phải được bọc từng bản ghi, y như vòng
        hoàn tất bên dưới nó. `_broadcast_state` chạm vào bus và vào kênh:
        bus không sẵn sàng hay kênh vừa bị xoá là ném lỗi ra khỏi cả
        `_cron_sweep` — không bản ghi nào được quét trong phút đó, và bản ghi
        hỏng ấy chặn tiếp mọi phút sau, mãi mãi."""
        broken = self.Recording.sudo().create({
            'channel_id': self.channel.id, 'secrecy_at_start': 'thuong',
            'state': 'recording',
        })
        other_channel = self.env['discuss.channel'].create({
            'name': 'Kênh khác', 'channel_type': 'channel',
        })
        healthy = self.Recording.sudo().create({
            'channel_id': other_channel.id, 'secrecy_at_start': 'thuong',
            'state': 'recording',
        })

        def fail_for_broken(rec_self, action):
            if rec_self.id == broken.id:
                raise ValueError('bus không sẵn sàng')
            return True

        with patch(BROADCAST, autospec=True, side_effect=fail_for_broken), \
                mute_logger(LOGGER):
            self.Recording._cron_sweep()

        self.assertEqual(broken.state, 'recording')
        self.assertEqual(healthy.state, 'processing')


class TestLateChunkRebuild(FinalizeCase):
    """Cuộc đua ĐÃ BIẾT, CHƯA sửa (và cố ý không sửa bằng khoá): một mẩu tới
    đúng lúc `_finalize` đang commit `done` vẫn được nhận và vẫn được bóc
    băng, nhưng `_cron_sweep` chỉ duyệt `processing` nên bản bóc băng không
    bao giờ được dựng lại. Ở đây không thiết kế lại khoá — chỉ bảo đảm hậu
    quả KHÔNG CÒN VÔ HÌNH."""

    def test_doan_ve_muon_thi_dung_lai_transcript(self):
        rec = self._recording()
        self._segment(rec, text='Phần đầu')
        rec._finalize()
        self.assertEqual(rec.state, 'done')
        self.assertNotIn('Phần cuối', rec.transcript_text)

        # Mẩu về muộn được bóc băng xong sau khi bản ghi đã 'done'.
        self._segment(rec, text='Phần cuối')
        with mute_logger(LOGGER):
            self.Recording._cron_sweep()
        self.assertIn('Phần cuối', rec.transcript_text)
        self.assertIn('Phần đầu', rec.transcript_text)

    def test_khong_dung_lai_khi_khong_co_gi_moi(self):
        """Không được đăng lại chatter mỗi phút cho mọi bản ghi vừa xong."""
        rec = self._recording()
        self._segment(rec)
        rec._finalize()
        before = len(self.channel.message_ids)
        self.Recording._cron_sweep()
        self.assertEqual(len(self.channel.message_ids), before)

    def test_khong_dung_lai_ban_ghi_da_hoan_tat_tu_lau(self):
        """Ngoài cửa sổ xét lại thì thôi: một bản ghi đã đăng chatter từ lâu
        không được tự ý đăng lại khi có ai đó sửa tay dữ liệu về sau."""
        from odoo import fields
        from odoo.addons.aidt_meeting_minutes.models.meeting_recording import (
            REFINALIZE_WINDOW_MINUTES,
        )
        rec = self._recording()
        self._segment(rec)
        rec._finalize()
        rec.sudo().write({'finalized_at': fields.Datetime.subtract(
            fields.Datetime.now(), minutes=REFINALIZE_WINDOW_MINUTES + 5)})
        self._segment(rec, text='Thêm về sau')
        self.Recording._cron_sweep()
        self.assertNotIn('Thêm về sau', rec.transcript_text)


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
