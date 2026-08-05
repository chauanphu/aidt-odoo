import logging

from markupsafe import Markup

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError
from odoo.tools import config

_logger = logging.getLogger(__name__)

# Thứ tự tăng dần. Dùng để so sánh với ngưỡng cấu hình.
SECRECY_ORDER = ['thuong', 'mat', 'toi_mat', 'tuyet_mat']


class AidtMeetingRecording(models.Model):
    _name = 'aidt.meeting.recording'
    _description = 'Bản ghi cuộc họp'
    _order = 'started_at desc, id desc'

    # channel_id mới là khoá thật: cuộc gọi tự phát không có calendar.event.
    # Mọi truy vấn phân quyền phải đi qua trường này.
    channel_id = fields.Many2one(
        'discuss.channel', string='Kênh', required=True,
        ondelete='cascade', index=True)
    event_id = fields.Many2one(
        'calendar.event', string='Cuộc họp', ondelete='set null', index=True)

    state = fields.Selection(
        [('recording', 'Đang ghi'), ('processing', 'Đang xử lý'),
         ('done', 'Xong'), ('failed', 'Lỗi'), ('cancelled', 'Đã huỷ')],
        string='Trạng thái', default='recording', required=True, index=True)

    started_by_id = fields.Many2one('res.users', string='Người bật', readonly=True)
    started_at = fields.Datetime(string='Bắt đầu', readonly=True)
    ended_at = fields.Datetime(string='Kết thúc', readonly=True)

    # Bản chụp, KHÔNG phải related. Xem test_chup_lai_do_mat_luc_bat_dau.
    secrecy_at_start = fields.Selection(
        [('thuong', 'Thường'), ('mat', 'Mật'),
         ('toi_mat', 'Tối mật'), ('tuyet_mat', 'Tuyệt mật')],
        string='Độ mật lúc bắt đầu', required=True, default='thuong',
        readonly=True)

    declined_partner_ids = fields.Many2many(
        'res.partner', string='Người từ chối ghi âm')

    transcript_text = fields.Text(string='Bản bóc băng', readonly=True)
    summary_text = fields.Text(string='Tóm tắt', readonly=True)
    summary_error = fields.Text(string='Lỗi tóm tắt', readonly=True)

    def init(self):
        """Chỉ mục UNIQUE riêng phần: mỗi kênh chỉ có một bản ghi đang hoạt
        động (recording/processing) tại một thời điểm.

        Brief gốc yêu cầu `models.Constraint` với mệnh đề Postgres
        `EXCLUDE (channel_id WITH =) WHERE (...)`. Mệnh đề đó CHỈ chạy được
        khi extension `btree_gist` đã cài (opclass gist cho phép so sánh `=`
        trên kiểu integer) — đã thử trực tiếp trên CSDL `aidt_demo` và xác
        nhận: `CREATE EXTENSION btree_gist` cần quyền superuser, và ngay cả
        khi cài được ở đây thì không có gì đảm bảo môi trường triển khai
        khác (staging/production, hosting không cho superuser) cũng cài
        được. Vì vậy chọn cách UNIQUE INDEX riêng phần — không phụ thuộc
        extension nào — theo đúng khuôn mẫu đã dùng ở
        `aidt_search/models/index_job.py::init()`. Đây KHÔNG phải suy giảm
        về hành vi: vẫn là ràng buộc ở tầng CSDL, chặn được đua create/write
        đồng thời mà kiểm tra đọc-rồi-ghi trong Python (`_start_for_channel`)
        không chặn nổi.
        """
        self.env.cr.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS
                aidt_meeting_recording_channel_active_uniq
              ON aidt_meeting_recording (channel_id)
              WHERE state IN ('recording', 'processing')
        """)

    # ------------------------------------------------------------------ #
    # Phân quyền
    # ------------------------------------------------------------------ #
    @api.model
    def _config(self, key, default=None):
        return self.env['ir.config_parameter'].sudo().get_param(
            f'aidt_meeting.{key}', default)

    @api.model
    def _event_for_channel(self, channel):
        """Cuộc họp có lịch gắn với kênh này, hoặc bản ghi rỗng.

        sudo() vì người dùng có thể dự họp mà không có quyền đọc
        calendar.event qua record rule của aidt_calendar; ở đây ta chỉ cần
        biết cuộc họp TỒN TẠI và độ mật của nó để quyết định cho phép.
        """
        return self.env['calendar.event'].sudo().search(
            [('videocall_channel_id', '=', channel.id)], limit=1)

    @api.model
    def _is_channel_member(self, channel, partner):
        return bool(self.env['discuss.channel.member'].sudo().search_count([
            ('channel_id', '=', channel.id), ('partner_id', '=', partner.id),
        ]))

    def _is_participant(self, partner):
        self.ensure_one()
        return self._is_channel_member(self.channel_id, partner)

    @api.model
    def _check_secrecy_allowed(self, secrecy):
        ceiling = self._config('max_secrecy', 'thuong')
        try:
            allowed = SECRECY_ORDER.index(ceiling)
        except ValueError:
            # Cấu hình rác thì KHÔNG mở rộng quyền — lùi về mức chặt nhất.
            _logger.warning(
                'aidt_meeting.max_secrecy không hợp lệ (%r), coi như "thuong".',
                ceiling)
            allowed = 0
        if SECRECY_ORDER.index(secrecy) > allowed:
            labels = dict(self._fields['secrecy_at_start'].selection)
            raise UserError(_(
                'Cuộc họp ở mức "%(muc)s" vượt ngưỡng cho phép ghi âm. '
                'Liên hệ quản trị viên nếu cần thay đổi.',
                muc=labels.get(secrecy, secrecy),
            ))

    @api.model
    def _start_for_channel(self, channel):
        """Bật ghi âm cho một kênh đang có cuộc gọi. Trả về bản ghi."""
        partner = self.env.user.partner_id
        if not self._is_channel_member(channel, partner):
            raise AccessError(_('Bạn không thuộc cuộc gọi này.'))

        event = self._event_for_channel(channel)
        if event:
            # Cuộc họp có lịch: chỉ người chủ trì được bật.
            if event.user_id != self.env.user:
                raise AccessError(_(
                    'Chỉ người chủ trì cuộc họp mới bật được ghi âm.'))
            secrecy = event.secrecy or 'thuong'
        else:
            # Cuộc gọi tự phát: không có gì để phân loại nên coi là thường,
            # và thành viên bất kỳ đều bật được. Ngưỡng độ mật KHÔNG kiểm
            # soát được ca này — banner đồng thuận và nút dừng ở §5 của spec
            # mới là cơ chế thực thi.
            secrecy = 'thuong'
        self._check_secrecy_allowed(secrecy)

        existing = self.sudo().search([
            ('channel_id', '=', channel.id),
            ('state', 'in', ('recording', 'processing')),
        ], limit=1)
        if existing:
            raise UserError(_('Cuộc gọi này đang được ghi âm rồi.'))

        recording = self.sudo().create({
            'channel_id': channel.id,
            'event_id': event.id if event else False,
            'secrecy_at_start': secrecy,
            'started_by_id': self.env.user.id,
            'started_at': fields.Datetime.now(),
        })
        recording._broadcast_state('started')
        return recording

    def action_stop(self):
        """Dừng ghi âm. BẤT KỲ người tham gia nào cũng gọi được."""
        self.ensure_one()
        if not self._is_participant(self.env.user.partner_id):
            raise AccessError(_('Bạn không thuộc cuộc gọi này.'))
        if self.state != 'recording':
            return False
        self.sudo().write({
            'state': 'processing', 'ended_at': fields.Datetime.now(),
        })
        self._broadcast_state('stopped')
        return True

    def _decline(self, partner):
        self.ensure_one()
        if not self._is_participant(self.env.user.partner_id):
            raise AccessError(_('Bạn không thuộc cuộc gọi này.'))
        self.sudo().write({'declined_partner_ids': [(4, partner.id)]})
        return True

    def _broadcast_state(self, action):
        """Báo cho mọi client trong kênh để chúng bật/tắt thu âm.

        Gửi kèm `elapsed_ms` để máy vào giữa chừng tính được vị trí tuyệt
        đối của chunk mà không cần đồng hồ tường của nó khớp với server.
        """
        self.ensure_one()
        elapsed = 0
        if self.started_at:
            delta = fields.Datetime.now() - self.started_at
            elapsed = int(delta.total_seconds() * 1000)
        self.channel_id._bus_send('aidt_meeting_minutes/recording_state', {
            'action': action,
            'recording_id': self.id,
            'channel_id': self.channel_id.id,
            'elapsed_ms': elapsed,
        })

    # ------------------------------------------------------------------ #
    # Kết thúc và hoàn tất
    # ------------------------------------------------------------------ #
    def _has_live_session(self):
        self.ensure_one()
        return bool(self.env['discuss.channel.rtc.session'].sudo().search_count(
            [('channel_id', '=', self.channel_id.id)]))

    def _chunks_settled(self):
        """True khi mọi mẩu audio đã 'done' hoặc 'failed'."""
        self.ensure_one()
        return not self.env['aidt.meeting.chunk'].sudo().search_count([
            ('recording_id', '=', self.id),
            ('state', 'in', ('pending', 'transcribing')),
        ])

    def _post_target(self):
        """Cuộc họp có lịch thì đăng vào chatter sự kiện; cuộc gọi tự phát
        thì đăng thẳng vào kênh, đúng nơi cuộc gọi đã diễn ra."""
        self.ensure_one()
        return self.event_id.sudo() if self.event_id else self.channel_id.sudo()

    def _finalize(self):
        self.ensure_one()
        transcript = self.env['aidt.meeting.transcript']._build(self)
        self.sudo().write({'transcript_text': transcript, 'state': 'done'})
        body = Markup('<p><b>%s</b></p><pre>%s</pre>') % (
            _('Bản bóc băng cuộc họp'), transcript or _('(không có nội dung)'))
        self._post_target().message_post(body=body)
        self._run_summary()
        self._purge_own_audio()
        return True

    def _run_summary(self):
        """Tóm tắt. Lỗi được ghi lại nhưng KHÔNG lan ra ngoài — transcript đã
        đăng rồi và không được mất vì bộ tóm tắt chết.

        `_summarize()` được bọc trong SAVEPOINT riêng của chính nó, cùng
        khuôn mẫu với `index_job.py::_process_one()`. Không có savepoint,
        một lỗi TẦNG CSDL từ bên trong `_summarize` (deadlock, vi phạm ràng
        buộc, ...) sẽ để cursor rơi vào InFailedSqlTransaction; câu
        `self.sudo().write({'summary_error': ...})` ở khối `except` bên dưới
        khi đó tự nó ném NGOẠI LỆ THỨ HAI, thoát khỏi `_run_summary` lẫn
        `_finalize`, và bị savepoint của `_cron_sweep` bắt lấy — rollback
        luôn cả `transcript_text`/`state='done'` vừa ghi. Đó đúng là mất mát
        mà docstring này cam kết không xảy ra. Rollback về savepoint trả
        cursor về trạng thái dùng được, để `sudo().write({'summary_error':
        ...})` phía dưới ghi lại được.
        """
        self.ensure_one()
        try:
            with self.env.cr.savepoint():
                summary = self.env['aidt.meeting.summary.client']._summarize(
                    self.transcript_text)
        except Exception as exc:                     # noqa: BLE001
            _logger.warning('Tóm tắt thất bại cho bản ghi %s: %s', self.id, exc)
            # Cache ORM có thể còn giữ giá trị của những ghi đã bị rollback
            # cùng savepoint — bỏ hết trước khi ghi trạng thái lỗi, cùng lý
            # do với `index_job.py::_process_one()`.
            self.env.invalidate_all()
            self.sudo().write({'summary_error': str(exc)})
            return False
        self.sudo().write({'summary_text': summary, 'summary_error': False})
        if summary:
            self._post_target().message_post(
                body=Markup('<p><b>%s</b></p><pre>%s</pre>') % (
                    _('Tóm tắt cuộc họp'), summary))
        return True

    def action_retry_summary(self):
        self.ensure_one()
        return self._run_summary()

    @api.model
    def _audio_purge_domain(self, days, extra_domain=None):
        domain = [('state', '=', 'done'), ('attachment_id', '!=', False)]
        if days > 0:
            cutoff = fields.Datetime.subtract(fields.Datetime.now(), days=days)
            domain.append(('create_date', '<=', cutoff))
        return domain + list(extra_domain or [])

    def _purge_own_audio(self):
        """Xoá audio của riêng bản ghi NÀY, ngay sau khi hoàn tất — best-effort.

        Gọi từ `_finalize`, nên PHẢI tự bọc savepoint + except của chính
        mình: nếu để lỗi lan ra, nó chạy trong savepoint của `_cron_sweep`
        và rollback luôn transcript vừa ghi — hai lỗi cụ thể đã thấy:
        (a) `aidt_meeting.audio_retention_days` là dữ liệu admin gõ tay qua
        `res.config.settings`, `int(...)` ném ValueError với bất kỳ giá trị
        không phải số nào; (b) `unlink()` có thể lỗi vì filestore/khoá ngoại.
        Domain PHẢI giới hạn theo `self`: việc dọn dẹp KHÔNG giới hạn (theo
        toàn hệ thống) là việc của `_cron_purge_audio` chạy theo lịch hàng
        ngày, không phải việc làm kèm mỗi lần hoàn tất MỘT bản ghi — nếu
        không, hoàn tất bản ghi A sẽ xoá audio của mọi bản ghi B, C, ... đã
        'done' từ trước, không liên quan gì tới A.
        """
        self.ensure_one()
        try:
            with self.env.cr.savepoint():
                days = int(self._config('audio_retention_days', '0') or 0)
                domain = self._audio_purge_domain(
                    days, [('recording_id', '=', self.id)])
                chunks = self.env['aidt.meeting.chunk'].sudo().search(domain)
                attachments = chunks.mapped('attachment_id')
                chunks.write({'attachment_id': False})
                attachments.unlink()
        except Exception as exc:                     # noqa: BLE001
            self.env.invalidate_all()
            _logger.warning(
                'Xoá audio thất bại cho bản ghi %s: %s', self.id, exc)
            return False
        return True

    @api.model
    def _cron_purge_audio(self):
        """Xoá audio của mọi mẩu đã bóc băng xong, TOÀN HỆ THỐNG, theo chính
        sách lưu trữ. Chạy theo `cron_purge_audio` hàng ngày — không giới
        hạn theo một bản ghi nào, khác với `_purge_own_audio`."""
        days = int(self._config('audio_retention_days', '0') or 0)
        domain = self._audio_purge_domain(days)
        chunks = self.env['aidt.meeting.chunk'].sudo().search(domain)
        attachments = chunks.mapped('attachment_id')
        chunks.write({'attachment_id': False})
        attachments.unlink()
        return True

    @api.model
    def _cron_sweep(self):
        """Hai việc: đóng bản ghi bị bỏ dở, và hoàn tất bản ghi đã đủ dữ liệu.

        Chụp danh sách 'processing' TRƯỚC khi chuyển các bản ghi 'recording'
        vừa bị bỏ dở sang 'processing': một bản ghi chỉ vừa được phát hiện
        kết thúc phải chờ ít nhất một lượt quét sau mới được xét hoàn tất,
        cho các chunk cuối cùng kịp được tạo — không hoàn tất ngay trong
        cùng một lượt quét.
        """
        already_processing = self.sudo().search([('state', '=', 'processing')])
        for recording in self.sudo().search([('state', '=', 'recording')]):
            if not recording._has_live_session():
                recording.write({
                    'state': 'processing', 'ended_at': fields.Datetime.now(),
                })
                recording._broadcast_state('stopped')
        for recording in already_processing:
            if recording._chunks_settled():
                try:
                    with self.env.cr.savepoint():
                        recording._finalize()
                except Exception:                    # noqa: BLE001
                    # Cố ý không đặt trần thử lại: bản ghi lỗi vẫn ở
                    # 'processing' và được thử lại ở lượt quét kế tiếp, vô
                    # thời hạn — không có cờ 'failed' nào chặn nó lại.
                    _logger.exception(
                        'Hoàn tất bản ghi %s thất bại', recording.id)
            if not config['test_enable']:
                self.env.cr.commit()
        return True
