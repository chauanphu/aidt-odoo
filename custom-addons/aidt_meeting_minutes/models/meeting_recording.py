import logging

from markupsafe import Markup

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError
from odoo.tools import config

_logger = logging.getLogger(__name__)

# Thứ tự tăng dần. Dùng để so sánh với ngưỡng cấu hình.
SECRECY_ORDER = ['thuong', 'mat', 'toi_mat', 'tuyet_mat']

# Cửa sổ xét lại bản ghi vừa hoàn tất, tính bằng phút. Xem `_cron_sweep`.
REFINALIZE_WINDOW_MINUTES = 10


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

    # Những người ĐÃ THỰC SỰ có mặt trong CUỘC GỌI trong lúc bản ghi này chạy
    # (có phiên `discuss.channel.rtc.session` trên kênh). Khác hẳn "thành viên
    # kênh": một kênh phòng ban 200 người thì 197 người trong đó chưa bao giờ
    # vào cuộc gọi 3 người này. Xem `_is_participant`.
    participant_partner_ids = fields.Many2many(
        'res.partner', 'aidt_meeting_recording_participant_rel',
        'recording_id', 'partner_id', string='Người có mặt trong cuộc gọi')

    transcript_text = fields.Text(string='Bản bóc băng', readonly=True)
    summary_text = fields.Text(string='Tóm tắt', readonly=True)
    summary_error = fields.Text(string='Lỗi tóm tắt', readonly=True)

    title = fields.Char(string='Tiêu đề')
    overview = fields.Text(string='Tổng quan')
    meeting_minutes = fields.Text(string='Biên bản')
    key_points = fields.Text(string='Ý chính (JSON)')
    risks = fields.Text(string='Rủi ro (JSON)')
    action_item_ids = fields.One2many('aidt.meeting.action.item', 'recording_id', string='Công việc')
    decision_ids = fields.One2many('aidt.meeting.decision', 'recording_id', string='Quyết định')

    # Dấu vết của lần hoàn tất gần nhất, dùng để phát hiện mẩu về muộn (đua
    # giữa `_store` và `_finalize` — xem `_cron_sweep`).
    finalized_at = fields.Datetime(string='Hoàn tất lúc', readonly=True)
    finalized_segment_count = fields.Integer(
        string='Số đoạn lúc hoàn tất', readonly=True)

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

    def _has_partner_session(self, partner):
        """Người này ĐANG có phiên RTC trên kênh của bản ghi hay không."""
        self.ensure_one()
        return bool(self.env['discuss.channel.rtc.session'].sudo().search_count([
            ('channel_id', '=', self.channel_id.id),
            ('partner_id', '=', partner.id),
        ]))

    def _register_participants(self):
        """Ghi lại những người ĐANG trong cuộc gọi vào `participant_partner_ids`.

        Gọi lúc bắt đầu ghi (`_broadcast_state('started')`) và mỗi khi một máy
        hỏi trạng thái lúc vào họp (`action_active_recording`) — hai thời điểm
        duy nhất mà client báo "tôi đang ở trong cuộc gọi này".
        """
        self.ensure_one()
        sessions = self.env['discuss.channel.rtc.session'].sudo().search(
            [('channel_id', '=', self.channel_id.id)])
        partners = sessions.mapped('partner_id')
        new = partners - self.participant_partner_ids
        if new:
            self.sudo().write(
                {'participant_partner_ids': [(4, p.id) for p in new]})
        return new

    def _is_participant(self, partner):
        """Người này có quyền tác động tới bản ghi (gửi audio, dừng, từ chối)?

        Thành viên kênh là điều kiện CẦN, KHÔNG ĐỦ. Bus phát trạng thái ghi âm
        tới mọi thành viên kênh, và một kênh phòng ban có thể có hàng trăm
        người chưa bao giờ vào cuộc gọi này — nếu chỉ xét thành viên kênh thì
        bất kỳ ai trong số đó cũng dừng được bản ghi của một cuộc gọi 3 người,
        đọc được audio thô của họ, và (kết hợp với lỗi phía client) tải lên
        được chính tiếng micro của mình trong một cuộc gọi KHÁC.

        KHÔNG đòi phải có phiên RTC SỐNG tại thời điểm gọi: mẩu cuối của mỗi
        máy tới nơi sau khi người đó đã gập máy (xem ghi chú ở
        `meeting_chunk._store`). Vì vậy xét theo tập người ĐÃ TỪNG có mặt
        trong cuộc gọi trong lúc bản ghi chạy, và bổ sung tại chỗ cho người
        vào họp muộn (họ đang có phiên RTC ngay lúc này).
        """
        self.ensure_one()
        if not self._is_channel_member(self.channel_id, partner):
            return False
        if partner in self.sudo().participant_partner_ids:
            return True
        if self._has_partner_session(partner):
            self.sudo().write({'participant_partner_ids': [(4, partner.id)]})
            return True
        return False

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
        try:
            level = SECRECY_ORDER.index(secrecy)
        except ValueError:
            # Độ mật của CHÍNH cuộc họp nằm ngoài thang đo (aidt_calendar thêm
            # một mức mới, dữ liệu nhập tay...). Không biết nó nằm ở đâu trên
            # thang thì phải coi là CAO NHẤT — từ chối sạch sẽ, không phải một
            # ValueError lọt ra thành lỗi 500.
            _logger.warning(
                'Độ mật %r không nằm trong SECRECY_ORDER; từ chối ghi âm.',
                secrecy)
            level = len(SECRECY_ORDER)
        if level > allowed:
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

    @api.model
    def action_start_for_channel(self, channel_id):
        """Wrapper PUBLIC của `_start_for_channel`, gọi được từ client qua
        `orm.call`: `odoo/service/model.py` từ chối thẳng mọi tên phương thức
        bắt đầu bằng `_` trước khi nó chạy, nên `_start_for_channel` không
        bao giờ gọi được từ JS. KHÔNG nới lỏng phân quyền ở đây — mọi kiểm
        tra (thành viên kênh, chỉ chủ trì được bật, ngưỡng độ mật) vẫn nằm
        nguyên trong `_start_for_channel` và vẫn ném lỗi bình thường; wrapper
        này chỉ đổi tên cho gọi được, không nuốt ngoại lệ.
        """
        channel = self.env['discuss.channel'].browse(int(channel_id)).exists()
        if not channel:
            raise UserError(_('Kênh không tồn tại.'))
        recording = self._start_for_channel(channel)
        return recording.id

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

    def action_decline(self):
        """Wrapper PUBLIC của `_decline`, gọi được từ banner (client) qua
        `orm.call` — `_decline` bắt đầu bằng `_` nên bị RPC chặn thẳng.

        KHÔNG nhận partner làm đối số: khác với `_start_for_channel`, ở đây
        không có lý do hợp lệ nào để tin JS tự khai "tôi là partner nào" —
        partner luôn được lấy từ phiên đăng nhập hiện tại
        (`self.env.user.partner_id`), giống hệt cách controller
        `/aidt_meeting/chunk` lấy partner (xem `controllers/main.py`).
        """
        self.ensure_one()
        return self._decline(self.env.user.partner_id)

    @api.model
    def action_active_recording(self, channel_id):
        """Bản ghi đang chạy trên kênh này, cho một máy vừa vào họp / vừa F5.

        PUBLIC vì client phải gọi được qua `orm.call`. Broadcast `started`
        chỉ phát MỘT LẦN: ai nạp lại tab, hoặc vào họp sau thời điểm đó, sẽ
        không bao giờ nhận được nó. Không có phương thức đọc này thì băng
        đồng thuận — CƠ CHẾ THỰC THI của việc xin phép ghi âm — đơn giản là
        không hiện với họ, và tiếng của họ cũng không được thu.

        KHÔNG nới lỏng phân quyền: người ngoài kênh nhận `{}` chứ không nhận
        id bản ghi. Chỉ trả về đúng ba thông tin mà client cần để vào đúng
        chỗ trên trục thời gian chung.
        """
        channel = self.env['discuss.channel'].browse(int(channel_id)).exists()
        if not channel:
            return {}
        partner = self.env.user.partner_id
        if not self._is_channel_member(channel, partner):
            raise AccessError(_('Bạn không thuộc cuộc gọi này.'))
        recording = self.sudo().search([
            ('channel_id', '=', channel.id),
            ('state', '=', 'recording'),
        ], limit=1)
        if not recording:
            return {}
        # Máy này vừa khai "tôi đang trong cuộc gọi": đúng lúc để ghi nhận
        # người vào họp muộn vào tập người tham gia (xem `_is_participant`).
        recording._register_participants()
        return {
            'recording_id': recording.id,
            'channel_id': channel.id,
            'elapsed_ms': recording._elapsed_ms(),
        }

    def _elapsed_ms(self):
        self.ensure_one()
        if not self.started_at:
            return 0
        delta = fields.Datetime.now() - self.started_at
        return int(delta.total_seconds() * 1000)

    def _broadcast_state(self, action):
        """Báo cho mọi client trong kênh để chúng bật/tắt thu âm.

        Gửi kèm `elapsed_ms` để máy vào giữa chừng tính được vị trí tuyệt
        đối của chunk mà không cần đồng hồ tường của nó khớp với server.

        Gửi kèm `channel_id` vì bus phát tới MỌI thành viên kênh, kể cả người
        đang ở trong một cuộc gọi ở kênh KHÁC — client bắt buộc phải đối chiếu
        id kênh trước khi bật micro (xem `recorder_service.js`).
        """
        self.ensure_one()
        elapsed = self._elapsed_ms()
        if action == 'started':
            self._register_participants()
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

    def _segment_count(self):
        self.ensure_one()
        return self.env['aidt.meeting.segment'].sudo().search_count(
            [('recording_id', '=', self.id)])

    def _finalize(self):
        self.ensure_one()
        transcript = self.env['aidt.meeting.transcript']._build(self)
        # `finalized_segment_count` chụp lại số đoạn mà transcript này ĐÃ dựa
        # trên. `_cron_sweep` so lại con số đó để phát hiện đoạn về muộn do
        # đua giữa `_store` và `_finalize`.
        self.sudo().write({
            'transcript_text': transcript, 'state': 'done',
            'finalized_at': fields.Datetime.now(),
            'finalized_segment_count': self._segment_count(),
        })
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

    def action_retranscribe(self):
        """Bóc băng LẠI từ audio còn lưu, bằng cấu hình ASR hiện hành.

        LÝ DO TỒN TẠI: không có nút này thì mọi thay đổi về model, tham số
        giải mã hay ngưỡng lọc đều KHÔNG ĐO ĐƯỢC. Cách duy nhất để so sánh
        "trước/sau" là họp thật thêm một lần nữa và hy vọng người ta nói
        giống hệt lần trước — tức là không so sánh được. Một bản bóc băng tệ
        cũng vì thế mà vĩnh viễn tệ.

        RÀNG BUỘC PHẢI BIẾT: `aidt_meeting.audio_retention_days` mặc định
        XUẤT XƯỞNG là `0`, nghĩa là audio bị xoá ngay khi hoàn tất
        (`_finalize` -> `_purge_own_audio`). Đó là một lựa chọn RIÊNG TƯ có
        chủ ý cho biên bản họp hành chính, không phải sơ suất — nên nút này
        KHÔNG tự nâng ngưỡng đó. Muốn tinh chỉnh thì admin phải chủ động đặt
        `audio_retention_days > 0` TRƯỚC khi họp; sau đó mỗi lần chạy lại vẫn
        tiêu tốn đúng một vòng `_finalize`, và `_finalize` lại xoá audio theo
        chính sách, nên với ngưỡng `0` thì mỗi bản ghi chỉ chạy lại được một
        lần và chỉ khi bấm trước lượt cron xoá.

        Mẩu đã mất audio được GIỮ NGUYÊN, không đụng tới: đoạn cũ của nó vẫn
        vào bản bóc băng mới. Xoá đi để "sạch" sẽ đổi một bản bóc băng thiếu
        chính xác lấy một bản bóc băng THIẾU HẲN — mất mát không hoàn lại
        được, vì nguồn audio đã không còn.
        """
        self.ensure_one()
        chunks = self.env['aidt.meeting.chunk'].sudo().search(
            [('recording_id', '=', self.id)])
        replayable = chunks.filtered(
            lambda c: c.attachment_id and c.attachment_id.exists())
        if not replayable:
            # Nhãn dưới đây PHẢI khớp nguyên văn nhãn thật trên trang Cấu
            # hình (`res_config_settings.py`: string='Giữ audio (ngày)',
            # trong khối `<setting string="Lưu trữ audio">`). Bản đầu ghi
            # "Số ngày giữ audio" — một cái tên không tồn tại ở đâu trong
            # giao diện, nên người đọc thông báo này sẽ đi tìm một ô không
            # có thật. Một thông báo lỗi chỉ sai mỗi cái tên còn tệ hơn
            # không có thông báo: nó làm người ta tin là mình tìm sai chỗ.
            raise UserError(_(
                'Không mẩu audio nào còn lưu nên không bóc băng lại được. '
                'Audio đã bị xoá theo ô "Giữ audio (ngày)" (mục "Lưu trữ '
                'audio" trong Cấu hình), hiện đang là %s. Muốn bóc băng lại '
                'được thì phải đặt số đó lớn hơn 0 TRƯỚC khi họp.',
                self._config('audio_retention_days', '0')))

        replayable.write({
            'state': 'pending', 'attempt': 0, 'error': False,
            'skip_note': False, 'next_retry_at': False,
        })
        # Về 'processing' để `_cron_sweep` nhặt lên và dựng lại bản bóc băng
        # khi hàng đợi lắng xuống. `finalized_segment_count` phải về 0 cùng
        # lúc: `_cron_sweep` so số đoạn hiện tại với con số đã chụp để phát
        # hiện đoạn về muộn, mà số cũ được chụp trên tập đoạn CŨ — để nguyên
        # thì lần hoàn tất sau lại tưởng có đoạn về muộn và dựng lại thêm
        # một lần nữa.
        self.sudo().write({'state': 'processing', 'finalized_segment_count': 0})
        _logger.info(
            'Bóc băng lại bản ghi %s: %s/%s mẩu còn audio.',
            self.id, len(replayable), len(chunks))
        return True

    @api.model
    def _audio_purge_domain(self, days, extra_domain=None):
        """Mẩu đã "yên vị" (`done` HOẶC `failed`) thì audio thô hết lý do tồn tại.

        `failed` PHẢI nằm trong đây. Chỉ lọc `done` nghĩa là đúng những mẩu
        đã hết lượt thử — thứ không ai còn xử lý nữa — giữ `ir.attachment`
        VĨNH VIỄN, kể cả khi chính sách là `audio_retention_days = 0` ("xoá
        ngay"). Với một hệ thống lấy chính sách lưu trữ làm cam kết tuân thủ,
        audio cuộc họp sống sót mãi mãi đúng ở các mẩu hỏng là mặc định sai.
        Mẩu `pending`/`transcribing` thì vẫn giữ — chúng còn cần audio để thử
        lại.
        """
        domain = [('state', 'in', ('done', 'failed')),
                  ('attachment_id', '!=', False)]
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
        hạn theo một bản ghi nào, khác với `_purge_own_audio`.

        SAVEPOINT + try/except vì lý do Y HỆT `_purge_own_audio` đã ghi rõ, và
        ở đây hậu quả còn nặng hơn: (a) `audio_retention_days` là dữ liệu admin
        gõ tay, `int(...)` ném ValueError với bất kỳ chuỗi không phải số nào;
        (b) `unlink()` có thể lỗi vì filestore/khoá ngoại. Không bọc thì MỘT
        giá trị cấu hình rác giết lượt cron này mỗi ngày, mãi mãi, và âm thầm —
        đúng thứ mà chính sách lưu trữ không được phép phụ thuộc vào. Thêm nữa
        `chunks.write({'attachment_id': False})` chạy TRƯỚC `attachments.unlink()`,
        nên lỗi ở bước sau mà không có savepoint sẽ để lại attachment mồ côi đã
        bị tháo khỏi chunk; rollback về savepoint trả cả hai bước về nguyên vẹn.
        """
        try:
            with self.env.cr.savepoint():
                days = int(self._config('audio_retention_days', '0') or 0)
                domain = self._audio_purge_domain(days)
                chunks = self.env['aidt.meeting.chunk'].sudo().search(domain)
                attachments = chunks.mapped('attachment_id')
                chunks.write({'attachment_id': False})
                attachments.unlink()
        except Exception as exc:                     # noqa: BLE001
            self.env.invalidate_all()
            _logger.warning('Lượt xoá audio định kỳ thất bại: %s', exc)
            return False
        return True

    @api.model
    def _cron_sweep(self):
        """Hai việc: đóng bản ghi bị bỏ dở, và hoàn tất bản ghi đã đủ dữ liệu.

        Chụp danh sách 'processing' TRƯỚC khi chuyển các bản ghi 'recording'
        vừa bị bỏ dở sang 'processing': một bản ghi chỉ vừa được phát hiện
        kết thúc phải chờ ít nhất một lượt quét sau mới được xét hoàn tất,
        cho các chunk cuối cùng kịp được tạo — không hoàn tất ngay trong
        cùng một lượt quét.

        Việc thứ ba: xét LẠI những bản ghi vừa hoàn tất trong
        `REFINALIZE_WINDOW_MINUTES` phút gần đây. Có một cuộc đua đã biết và
        CHƯA sửa: một request `/aidt_meeting/chunk` đọc thấy `state='processing'`
        ngay trước khi `_finalize` commit `done` vẫn tạo được mẩu, mẩu đó vẫn
        được bóc băng, nhưng vòng lặp trên chỉ duyệt `processing` nên transcript
        không bao giờ được dựng lại — và không ai biết. Ở đây không thiết kế lại
        khoá; chỉ so số đoạn hiện tại với `finalized_segment_count` đã chụp lúc
        hoàn tất, và dựng lại transcript nếu lệch. Ngoài cửa sổ đó thì thôi:
        một bản ghi đã đăng chatter từ lâu không được tự ý đăng lại.
        """
        already_processing = self.sudo().search([('state', '=', 'processing')])
        for recording in self.sudo().search([('state', '=', 'recording')]):
            # Bọc từng bản ghi, cùng khuôn mẫu với vòng hoàn tất bên dưới:
            # `_broadcast_state` chạm vào bus và vào kênh, nên một kênh vừa bị
            # xoá hay một bus không sẵn sàng sẽ ném lỗi ra khỏi cả `_cron_sweep`
            # — không bản ghi nào được quét trong phút đó, và bản ghi hỏng ấy
            # chặn tiếp mọi phút sau.
            try:
                with self.env.cr.savepoint():
                    if not recording._has_live_session():
                        recording.write({
                            'state': 'processing',
                            'ended_at': fields.Datetime.now(),
                        })
                        recording._broadcast_state('stopped')
            except Exception:                        # noqa: BLE001
                self.env.invalidate_all()
                _logger.exception(
                    'Đóng bản ghi bỏ dở %s thất bại', recording.id)
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
        self._sweep_late_chunks()
        return True

    @api.model
    def _sweep_late_chunks(self):
        """Dựng lại transcript của bản ghi vừa hoàn tất mà có đoạn về muộn.

        Xem phần cuộc đua đã mô tả trong docstring của `_cron_sweep`.
        """
        cutoff = fields.Datetime.subtract(
            fields.Datetime.now(), minutes=REFINALIZE_WINDOW_MINUTES)
        candidates = self.sudo().search([
            ('state', '=', 'done'),
            ('finalized_at', '>=', cutoff),
        ])
        for recording in candidates:
            if not recording._chunks_settled():
                continue
            if recording._segment_count() == recording.finalized_segment_count:
                continue
            _logger.warning(
                'Bản ghi %s có đoạn về muộn sau khi đã hoàn tất (%s đoạn lúc '
                'hoàn tất, %s đoạn hiện tại) — dựng lại bản bóc băng.',
                recording.id, recording.finalized_segment_count,
                recording._segment_count())
            try:
                with self.env.cr.savepoint():
                    recording._finalize()
            except Exception:                        # noqa: BLE001
                self.env.invalidate_all()
                _logger.exception(
                    'Dựng lại bản ghi %s thất bại', recording.id)
            if not config['test_enable']:
                self.env.cr.commit()
        return True
