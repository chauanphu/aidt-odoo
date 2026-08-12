import json
import logging
from pathlib import Path

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError
from odoo.tools import config

_logger = logging.getLogger(__name__)

# NGUỒN DUY NHẤT của thư mục audio cuộc họp. Trước đây chuỗi
# "/var/lib/odoo/meetings" được gõ tay ở HAI nơi — chỗ GHI
# (`_export_chunks`) và chỗ ĐỌC (`controllers/main.py::get_meeting_audio`) —
# và chúng chỉ khớp nhau nhờ TRÙNG HỢP với `data_dir` trong docker/odoo.conf,
# không nhờ một tham chiếu nào. Đổi `data_dir` (host khác, volume khác) mà chỉ
# sửa một trong hai chỗ thì audio ghi ra một nơi còn endpoint tìm ở nơi khác:
# lỗi 404 im lặng, không ai lần ra được nguyên nhân.
#
# Dẫn từ `config['data_dir']` là đúng quy ước Odoo đã dùng cho filestore
# (odoo/tools/config.py: `filestore()` cũng ghép từ chính khoá này), và khớp
# tên `MEETINGS_ROOT` mà docker/ai_worker/main.py đã đặt cho cùng thư mục.
MEETINGS_ROOT = Path(config['data_dir']) / 'meetings'

# Thứ tự tăng dần. Dùng để so sánh với ngưỡng cấu hình.
SECRECY_ORDER = ['thuong', 'mat', 'toi_mat', 'tuyet_mat']

# Hai tập trạng thái dưới đây MANG Ý NGHĨA KHÁC NHAU, đừng gộp:
#
#   ACTIVE_STATES — bản ghi còn CHIẾM chỗ duy nhất của kênh. `processing` vẫn
#     nằm trong đây vì job bóc băng còn chạy và mẩu đến muộn vẫn phải nhận
#     được; bật một bản ghi thứ hai lúc này là hỏng dữ liệu.
#   OPEN_STATES — bản ghi CHƯA chuyển sang xử lý, tức còn dừng/kết thúc được
#     và còn hiện băng thông báo.
#
# Đặt tên thay vì viết tay tuple ở từng chỗ, vì việc viết tay ĐÃ hỏng một
# lần: chỉ mục UNIQUE riêng phần trong `init()` dùng
# `CREATE UNIQUE INDEX IF NOT EXISTS` nên khi mệnh đề WHERE thêm `'paused'`
# thì lệnh đó không làm gì cả và chỉ mục cũ ở lại — phải có
# `migrations/19.0.1.3.0/pre-migration.py` DROP tường minh. Người thêm trạng
# thái thứ ba về sau chỉ cần sửa đúng ở đây, và vẫn phải viết migration cho
# chỉ mục.
ACTIVE_STATES = ('recording', 'paused', 'processing')
OPEN_STATES = ('recording', 'paused')


class AidtMeetingRecording(models.Model):
    _name = 'aidt.meeting.recording'
    _description = 'Bản ghi cuộc họp'
    _order = 'started_at desc, id desc'

    # channel_id mới là khoá thật, dù từ 19.0.1.4.0 mọi bản ghi MỚI đều có
    # `event_id` (ghi âm chỉ tồn tại trong phòng họp): kênh cuộc gọi thường
    # đông hơn danh sách mời trong lịch, nên chỉ trường này mới cho người có
    # mặt trong cuộc gọi mà không được mời riêng đọc được bản ghi của chính
    # họ. Ngoài ra `event_id` là `ondelete='set null'` — xoá cuộc họp khỏi
    # Lịch làm nó rỗng lại trên những bản ghi cũ. Mọi truy vấn phân quyền
    # phải đi qua `channel_id` (xem `security/aidt_meeting_rules.xml`).
    channel_id = fields.Many2one(
        'discuss.channel', string='Kênh', required=True,
        ondelete='cascade', index=True)
    event_id = fields.Many2one(
        'calendar.event', string='Cuộc họp', ondelete='set null', index=True)

    state = fields.Selection(
        [('recording', 'Đang ghi'), ('paused', 'Tạm dừng'),
         ('processing', 'Đang xử lý'), ('done', 'Xong'),
         ('failed', 'Lỗi'), ('cancelled', 'Đã huỷ')],
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

    # Bản chụp, KHÔNG phải related tới `channel_id.aidt_call_host_partner_id`:
    # chủ phòng của KÊNH đổi khi có cuộc gọi mới, còn "ai đã bật bản ghi này"
    # là dữ kiện lịch sử của biên bản và phải đứng yên.
    host_partner_id = fields.Many2one(
        'res.partner', string='Chủ phòng', readonly=True, index=True)

    # Lần ghi hiện tại. Tăng 1 mỗi lần ghi tiếp. Client đánh `seq` lại từ 0
    # cho mỗi take, nên `take` là thứ phân biệt hai mẩu cùng `seq`.
    current_take = fields.Integer(
        string='Lần ghi hiện tại', default=0, readonly=True)
    pause_ids = fields.One2many(
        'aidt.meeting.pause', 'recording_id', string='Các đoạn tạm dừng')
    pause_summary = fields.Char(
        string='Đoạn không được ghi', compute='_compute_pause_summary')

    # Những người ĐÃ THỰC SỰ có mặt trong CUỘC GỌI trong lúc bản ghi này chạy
    # (có phiên `discuss.channel.rtc.session` trên kênh). Khác hẳn "thành viên
    # kênh": một kênh phòng ban 200 người thì 197 người trong đó chưa bao giờ
    # vào cuộc gọi 3 người này. Xem `_is_participant`.
    participant_partner_ids = fields.Many2many(
        'res.partner', 'aidt_meeting_recording_participant_rel',
        'recording_id', 'partner_id', string='Người có mặt trong cuộc gọi')

    # Có mặt trong cuộc gọi nhưng KHÔNG có mẩu âm thanh nào.
    #
    # VÌ SAO CẦN: mỗi máy tự thu micro của chính người đó, và nếu một máy không
    # thu được thì hỏng HOÀN TOÀN IM LẶNG — không cảnh báo cho chủ phòng, không
    # cho người dự, không dòng log nào. Chủ trì họp xong, tin rằng đã thu đủ, và
    # chỉ phát hiện khi đọc biên bản thấy mọi câu đều mang một cái tên. Đã xảy ra
    # thật ở bản ghi 5641 (12/08/2026): người dự có phiên RTC đúng lúc bấm bật
    # ghi, nhưng gửi lên 0 mẩu, và toàn bộ phần phát biểu của họ biến mất khỏi
    # biên bản mà không có dấu hiệu nào.
    #
    # KHÔNG kết luận thay người đọc: `recorder_service.js` chỉ gửi mẩu NÀO CÓ
    # TIẾNG NÓI (`shouldUpload = hasVoiceActivity || !analyser`), nên "0 mẩu" có
    # ĐÚNG HAI nghĩa — micro không được thu, HOẶC người đó dự mà không phát biểu
    # câu nào. Cả hai đều đáng biết, và chỉ người trong cuộc mới phân biệt được.
    # Vì vậy câu chữ nêu cả hai khả năng thay vì buộc tội một bên.
    no_audio_partner_ids = fields.Many2many(
        'res.partner', compute='_compute_no_audio',
        string='Có mặt nhưng không có âm thanh')
    no_audio_warning = fields.Char(compute='_compute_no_audio')

    @api.depends('participant_partner_ids', 'state')
    def _compute_no_audio(self):
        # Gom một lượt cho cả recordset thay vì hỏi từng bản ghi.
        by_recording = {}
        done = self.filtered(
            lambda r: r.id and r.state in ('processing', 'done', 'failed'))
        if done:
            rows = self.env['aidt.meeting.chunk'].sudo()._read_group(
                [('recording_id', 'in', done.ids)],
                ['recording_id', 'partner_id'], [])
            for recording, partner in rows:
                by_recording.setdefault(recording.id, set()).add(partner.id)
        for rec in self:
            # Trong lúc còn đang ghi thì im lặng là bình thường: người ta chưa
            # tới lượt nói. Cảnh báo lúc đó chỉ là báo động giả.
            if rec not in done:
                rec.no_audio_partner_ids = False
                rec.no_audio_warning = False
                continue
            uploaded = by_recording.get(rec.id, set())
            missing = rec.participant_partner_ids.filtered(
                lambda p: p.id not in uploaded)
            rec.no_audio_partner_ids = missing
            rec.no_audio_warning = _(
                'Không thu được âm thanh của: %(ten)s. Hoặc micro của họ không '
                'được thu, hoặc họ dự mà không phát biểu — biên bản dưới đây '
                'thiếu phần của những người này.',
                ten=', '.join(missing.mapped('name')),
            ) if missing else False

    transcript_text = fields.Text(string='Bản bóc băng', readonly=True)
    summary_text = fields.Text(string='Tóm tắt', readonly=True)

    title = fields.Char(string='Tiêu đề')
    overview = fields.Text(string='Tổng quan')
    meeting_minutes = fields.Text(string='Biên bản')
    key_points = fields.Text(string='Ý chính (JSON)')
    risks = fields.Text(string='Rủi ro (JSON)')
    key_points_html = fields.Html(string='Ý chính', compute='_compute_json_html')
    risks_html = fields.Html(string='Rủi ro', compute='_compute_json_html')
    audio_html = fields.Html(string='Nghe lại', compute='_compute_audio_html')

    @api.depends('state')
    def _compute_audio_html(self):
        for rec in self:
            if rec.state in ('processing', 'done'):
                rec.audio_html = f'<audio controls style="width: 100%; border-radius: 8px; margin-top: 10px;"><source src="/aidt_meeting/audio/{rec.id}" type="audio/wav"></audio>'
            else:
                rec.audio_html = ''

    @api.depends('key_points', 'risks')
    def _compute_json_html(self):
        for rec in self:
            def to_html(val):
                if not val:
                    return ''
                try:
                    data = json.loads(val)
                    if isinstance(data, list):
                        items = ''.join(f"<li>{item.get('content', '')}</li>" for item in data)
                        return f"<ul>{items}</ul>"
                except Exception:
                    pass
                return val
            
            rec.key_points_html = to_html(rec.key_points)
            rec.risks_html = to_html(rec.risks)

    @api.depends('pause_ids.paused_at_ms', 'pause_ids.resumed_at_ms')
    def _compute_pause_summary(self):
        """Tóm tắt các đoạn KHÔNG được ghi, cho người đọc biên bản.

        `resumed_at_ms` rỗng KHÔNG phải "khoảng dừng 0 giây" — theo hợp đồng
        đã chốt ở Task 9 (xem docstring `_end_recording`), nó nghĩa là khoảng
        dừng CÒN MỞ: dừng từ đó tới HẾT cuộc họp, tức là loại DÀI NHẤT có thể
        có, không phải loại ngắn nhất. Cộng nó vào tổng như một khoảng 0 giây
        (kiểu `sum(... for p in pauses if p.resumed_at_ms)` không lọc riêng)
        sẽ nói NGƯỢC sự thật với đúng người đang cần biết biên bản thiếu chỗ
        nào — một bản ghi kết thúc trong lúc đang tạm dừng sẽ hiện "tổng 0
        phút 0 giây" trong khi phần đuôi cuộc họp thực ra không hề được ghi.
        Vì vậy khoảng dừng CÒN MỞ được tách riêng và nói thẳng bằng lời, không
        gộp vào con số tổng phút/giây (vốn chỉ tính được cho khoảng đã đóng).
        """
        for rec in self:
            pauses = rec.pause_ids
            if not pauses:
                rec.pause_summary = ''
                continue
            closed = pauses.filtered('resumed_at_ms')
            open_pauses = pauses - closed
            parts = []
            if closed:
                total = sum(
                    (p.resumed_at_ms - p.paused_at_ms)
                    for p in closed)
                minutes, seconds = divmod(max(0, total) // 1000, 60)
                parts.append(
                    f"{len(closed)} đoạn không được ghi · "
                    f"tổng {minutes} phút {seconds} giây")
            if open_pauses:
                parts.append(
                    f"{len(open_pauses)} đoạn không được ghi tới hết "
                    f"cuộc họp (đang tạm dừng lúc kết thúc)")
            rec.pause_summary = ' · '.join(parts)

    action_item_ids = fields.One2many('aidt.meeting.action.item', 'recording_id', string='Công việc')
    decision_ids = fields.One2many('aidt.meeting.decision', 'recording_id', string='Quyết định')

    def init(self):
        """Chỉ mục UNIQUE riêng phần: mỗi kênh chỉ có một bản ghi đang hoạt
        động (recording/paused/processing) tại một thời điểm.

        `CREATE UNIQUE INDEX IF NOT EXISTS` KHÔNG cập nhật mệnh đề WHERE của
        một chỉ mục đã tồn tại — trên một CSDL đã cài từ trước khi có
        `'paused'`, lệnh này không làm gì cả và chỉ mục cũ ở lại. Bản dọn
        thật nằm ở `migrations/19.0.1.3.0/pre-migration.py` (DROP tường minh
        rồi để `init()` này tạo lại).
        """
        states = ', '.join("'%s'" % state for state in ACTIVE_STATES)
        self.env.cr.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS
                aidt_meeting_recording_channel_active_uniq
              ON aidt_meeting_recording (channel_id)
              WHERE state IN (%s)
        """ % states)

    # ------------------------------------------------------------------ #
    # Phân quyền
    # ------------------------------------------------------------------ #
    @api.model
    def _config(self, key, default=None):
        return self.env['ir.config_parameter'].sudo().get_param(
            f'aidt_meeting.{key}', default)

    @api.model
    def _event_for_channel(self, channel, at=None):
        """Cuộc họp đứng sau kênh này TẠI MỐC `at`, hoặc bản ghi rỗng.

        Một kênh có thể đứng sau NHIỀU cuộc họp: `addons/calendar` cố ý cho
        cả chuỗi họp định kỳ dùng chung một kênh
        (`calendar_event.py:1057`). Bản cũ dùng `limit=1` không kèm `order`
        nên rơi vào `_order = "start desc"` của `calendar.event` và LUÔN trả
        về buổi xa nhất trong tương lai — giao ban sáng nay trả về buổi
        tháng 12. Bốn chỗ hỏng vì nó: kiểm người chủ trì, `secrecy_at_start`,
        `recording.event_id`, và `_resolve_host_partner`.

        Thứ tự ưu tiên: buổi ĐANG diễn ra -> buổi SẮP tới gần nhất -> buổi
        VỪA qua gần nhất. Nấc thứ ba cần thiết vì bản ghi được tạo lúc bấm
        "Bật ghi âm", có thể muộn hơn `stop` vài phút khi cuộc họp kéo dài.

        sudo() vì người dùng có thể dự họp mà không có quyền đọc
        calendar.event qua record rule của aidt_calendar; ở đây ta chỉ cần
        biết cuộc họp TỒN TẠI và độ mật của nó để quyết định cho phép.
        """
        at = at or fields.Datetime.now()
        events = self.env['calendar.event'].sudo().search(
            [('videocall_channel_id', '=', channel.id)])
        # Đường tắt: cuộc họp thường — tuyệt đại đa số — không phải trả giá
        # cho ba lượt lọc dưới đây.
        if len(events) <= 1:
            return events
        ongoing = events.filtered(
            lambda e: e.start and e.stop and e.start <= at <= e.stop)
        if ongoing:
            return ongoing.sorted('start')[0]
        upcoming = events.filtered(lambda e: e.start and e.start > at)
        if upcoming:
            return upcoming.sorted('start')[0]
        return events.sorted('start')[-1]

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

    def _is_host(self, partner):
        """Người này có phải chủ phòng của bản ghi này không."""
        self.ensure_one()
        return bool(partner) and partner == self.sudo().host_partner_id

    def _require_host(self, message):
        """Chặn mọi người trừ chủ phòng. Ẩn nút trên giao diện KHÔNG phải
        phân quyền — đây mới là chỗ chặn thật, và cả ba hành động điều khiển
        ghi âm phải đi qua đúng một cửa này để không đường nào bị bỏ sót."""
        self.ensure_one()
        if not self._is_host(self.env.user.partner_id):
            raise AccessError(message)

    @api.model
    def _check_secrecy_allowed(self, secrecy):
        ceiling = self._config('max_secrecy', 'thuong')
        try:
            allowed = SECRECY_ORDER.index(ceiling)
        except ValueError:
            _logger.warning(
                'aidt_meeting.max_secrecy không hợp lệ (%r), coi như "thuong".',
                ceiling)
            allowed = 0
        try:
            level = SECRECY_ORDER.index(secrecy)
        except ValueError:
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

        # Từ 19.0.1.4.0: ghi âm CHỈ tồn tại trong phòng họp — kênh có
        # `calendar.event` đứng sau. Nhánh "cuộc gọi tự phát" cũ đã bị gỡ:
        # nó cho phép bất kỳ chủ phòng cuộc gọi nào bật ghi âm ở bất kỳ kênh
        # nào, kể cả tin nhắn trực tiếp hai người, với độ mật mặc định
        # 'thuong' mà không ai chọn.
        #
        # THỨ TỰ ở đây là bắt buộc: khối này phải đứng TRƯỚC khối chủ phòng.
        # `discuss_channel_rtc_session.create` chỉ chốt
        # `aidt_call_host_partner_id` cho phòng họp, nên kênh thường KHÔNG
        # BAO GIỜ có chủ phòng — đặt khối chủ phòng lên trước thì mọi kênh
        # thường thoát ra ở "Chưa có cuộc gọi nào đang diễn ra trên kênh
        # này." (sai hẳn nguyên nhân: cuộc gọi đang diễn ra thật) và câu
        # dưới đây thành mã chết, không chạy lần nào.
        event = self._event_for_channel(channel)
        if not event:
            raise AccessError(_('Chỉ ghi âm được trong phòng họp.'))

        host = channel.sudo().aidt_call_host_partner_id
        if not host:
            raise AccessError(_(
                'Chưa có cuộc gọi nào đang diễn ra trên kênh này.'))
        if host != partner:
            raise AccessError(_(
                'Chỉ chủ phòng mới bật được ghi âm.'))

        # Người chủ trì trong lịch là tiếng nói cuối cùng — chủ phòng của
        # cuộc gọi không vượt được quyền đó. Phòng vệ chiều sâu: với phòng
        # họp có `event.user_id`, `_resolve_host_partner` đã chốt chủ phòng
        # đúng vào người đó nên guard trên đã bắt trước và câu dưới không
        # phát ra. Nó chỉ chạy khi `event.user_id` RỖNG — lúc đó chủ phòng
        # lùi về người vào cuộc gọi đầu tiên, và người đó không được thừa
        # hưởng quyền của một người chủ trì không tồn tại.
        if event.user_id != self.env.user:
            raise AccessError(_('Chỉ người chủ trì cuộc họp mới bật được ghi âm.'))
        secrecy = event.secrecy or 'thuong'
        self._check_secrecy_allowed(secrecy)

        existing = self.sudo().search([
            ('channel_id', '=', channel.id),
            ('state', 'in', ACTIVE_STATES),
        ], limit=1)
        if existing:
            raise UserError(_('Cuộc gọi này đang được ghi âm rồi.'))

        recording = self.sudo().create({
            'channel_id': channel.id,
            'event_id': event.id,
            'secrecy_at_start': secrecy,
            'started_by_id': self.env.user.id,
            'host_partner_id': host.id,
            'started_at': fields.Datetime.now(),
        })
        recording._broadcast_state('started')
        return recording

    @api.model
    def action_start_for_channel(self, channel_id):
        """Wrapper PUBLIC của `_start_for_channel`"""
        channel = self.env['discuss.channel'].browse(int(channel_id)).exists()
        if not channel:
            raise UserError(_('Kênh không tồn tại.'))
        recording = self._start_for_channel(channel)
        return recording.id

    def action_pause(self):
        """Tạm dừng THU BIÊN BẢN. Cuộc gọi không bị đụng tới.

        Người tham gia vẫn nghe và nói với nhau bình thường — chỉ luồng
        `getUserMedia` riêng của bộ ghi âm bị đóng lại, không phải track
        WebRTC của cuộc gọi.
        """
        self._require_host(_('Chỉ chủ phòng mới tạm dừng được ghi âm.'))
        if self.state != 'recording':
            # Bấm hai lần vì mạng chậm là chuyện thường; lần sau phải là
            # no-op chứ không mở thêm một khoảng dừng chồng lên khoảng đang mở.
            return False

        self.env['aidt.meeting.pause'].sudo().create({
            'recording_id': self.id,
            'paused_at_ms': self._elapsed_ms(),
            'paused_by_id': self.env.user.id,
        })
        self.sudo().write({'state': 'paused'})
        self._broadcast_state('paused')
        return True

    def action_resume(self):
        """Ghi tiếp sau khi tạm dừng. Tăng `take`."""
        self._require_host(_('Chỉ chủ phòng mới ghi tiếp được.'))
        if self.state != 'paused':
            return False

        open_pause = self.sudo().pause_ids.filtered(
            lambda p: not p.resumed_at_ms)[-1:]
        if open_pause:
            open_pause.write({'resumed_at_ms': self._elapsed_ms()})
        self.sudo().write({
            'state': 'recording',
            'current_take': self.current_take + 1,
        })
        self._broadcast_state('resumed')
        return True

    def _end_recording(self):
        """Kết thúc bản ghi. KHÔNG kiểm tra quyền — hai đường gọi tới đây đã
        tự kiểm: `action_stop` (chủ phòng bấm) và móc `unlink` của phiên RTC
        (cuộc gọi trống). Tách ra để hai đường không lệch hành vi.

        Bản ghi đang `paused` cũng kết thúc được: không bắt chủ phòng phải
        ghi tiếp rồi mới dừng được. Khoảng dừng đang mở giữ nguyên
        `resumed_at_ms` rỗng — ta biết lúc dừng, không biết cuộc họp còn kéo
        dài bao lâu sau đó.
        """
        self.ensure_one()
        if self.state not in OPEN_STATES:
            return False

        self.sudo().write({
            'state': 'processing', 'ended_at': fields.Datetime.now(),
        })
        self._broadcast_state('stopped')

        # Đợi mẩu cuối của mọi máy tới nơi rồi mới đẩy job. 10 giây là con số
        # ước lượng, không phải kết quả đo — máy có mạng chậm hơn thế vẫn mất
        # đoạn kết.
        import threading
        registry = self.env.registry

        def trigger_later(reg, recording_id):
            import time
            import logging
            from odoo import api, SUPERUSER_ID
            time.sleep(10)
            try:
                with reg.cursor() as cr:
                    env = api.Environment(cr, SUPERUSER_ID, {})
                    rec = env['aidt.meeting.recording'].browse(recording_id)
                    if rec.exists() and rec.state == 'processing':
                        rec._trigger_ai_service()
            except Exception as e:
                logging.getLogger(__name__).error(
                    f"Error in delayed AI trigger for {recording_id}: {e}")

        threading.Thread(target=trigger_later, args=(registry, self.id)).start()
        return True

    def action_stop(self):
        """Kết thúc ghi âm. CHỈ chủ phòng.

        Trước đây bất kỳ người tham gia nào cũng gọi được, và điều đó kết
        hợp với `finalize_recording` làm một người rời cuộc gọi kết thúc cả
        bản ghi của mọi người.
        """
        self._require_host(_('Chỉ chủ phòng mới kết thúc được ghi âm.'))
        return self._end_recording()

    def _trigger_ai_service(self):
        """Xuất mẩu audio ra đĩa rồi đẩy job sang worker.

        Mẩu được xuất GOM THEO (NGƯỜI NÓI, LẦN GHI), giữ nguyên thứ tự `seq`
        của chính lần ghi đó. `seq` đếm lại từ 0 ở MỖI take (tạm dừng rồi ghi
        tiếp), nên tên tệp phải mang cả `t{take}` — thiếu nó thì lần ghi tiếp
        sẽ ghi đè tệp cùng `seq` của lần trước. Vì lý do tương tự, không thể
        nối byte các take với nhau: mỗi lần bấm ghi tiếp là một phiên
        MediaRecorder mới nên có header EBML riêng; worker phải ghép nối ở
        mức âm thanh đã giải mã (xem docker/ai_worker/main.py), không phải ở
        mức tệp thô. `pauses` cho worker biết chính xác quãng thời gian nào
        bị cắt để khớp lại mốc thời gian thật của cuộc họp.
        """
        self.ensure_one()

        import json
        import os

        chunk_dir = MEETINGS_ROOT / str(self.id)
        chunk_dir.mkdir(parents=True, exist_ok=True)

        chunks = self.env['aidt.meeting.chunk'].sudo().search(
            [('recording_id', '=', self.id)], order='partner_id, take, seq')

        speakers = {}
        total_chunks = 0
        # Duyệt theo LÔ và dọn cache mỗi lô. Hai lý do, cả hai đã đo:
        #
        #   * `attachment.raw` chứ không phải `.datas`: `datas` là base64 của
        #     `raw`, nên đọc nó giữ CẢ HAI dạng trong cache (+33%) rồi ta lại
        #     decode ngược về đúng cái `raw` ban đầu.
        #   * `datas`/`raw` là trường compute KHÔNG lưu, nên `Field.__get__`
        #     chạy compute cho cả LÔ PREFETCH (tới 1000 bản ghi) ngay khi ta
        #     chạm vào bản ghi đầu tiên — và không có gì dọn cache giữa chừng,
        #     nên nó cộng dồn tới hết cuộc họp.
        #
        # Đo trên 200 mẩu (23,7 MB audio): cách cũ +55,9 MB RSS / 2 truy vấn;
        # cách này +0,0 MB / 22 truy vấn. Đổi 20 truy vấn lấy toàn bộ phần
        # RAM là đáng, vì hàm này chạy trong một `threading.Thread` sinh ra
        # từ `_end_recording` — tức nó ăn vào worker đang phục vụ HTTP. Họp
        # 2 giờ × 10 người ≈ 2400 mẩu ≈ 290 MB audio ⇒ ~700 MB RSS theo cách
        # cũ; gặp `limit_memory_hard` thì worker bị giết GIỮA LÚC export và
        # cuộc họp mất biên bản mà không ai biết vì sao.
        BATCH = 50
        for start in range(0, len(chunks), BATCH):
            for chunk in chunks[start:start + BATCH]:
                raw = chunk.attachment_id.raw if chunk.attachment_id else None
                if not raw:
                    continue
                partner = chunk.partner_id
                chunk_file = f"spk{partner.id}_t{chunk.take}_{chunk.seq:05d}.webm"
                (chunk_dir / chunk_file).write_bytes(raw)
                total_chunks += 1

                speaker = speakers.setdefault(partner.id, {
                    'partner_id': partner.id,
                    'speaker_name': partner.name or 'Unknown',
                    'takes': {},
                })
                # Mốc bắt đầu của mỗi LẦN GHI là offset của mẩu sớm nhất trong
                # chính lần đó — không phải của cả người. Nối byte chỉ hợp lệ
                # trong phạm vi một take (header EBML mới ở mỗi lần ghi tiếp).
                take = speaker['takes'].setdefault(chunk.take, {
                    'take': chunk.take,
                    'offset_ms': chunk.offset_ms,
                    'files': [],
                })
                take['files'].append(chunk_file)
                take['offset_ms'] = min(take['offset_ms'], chunk.offset_ms)
            # Nhả byte audio của lô vừa ghi xong. Phải đứng NGOÀI vòng trong,
            # nếu không mỗi mẩu lại kích hoạt một lượt prefetch mới và ta trả
            # một truy vấn cho từng mẩu thay vì cho từng lô.
            self.env.invalidate_all()

        metadata = {
            'speakers': [
                {**spk, 'takes': [spk['takes'][k] for k in sorted(spk['takes'])]}
                for spk in speakers.values()
            ],
            'pauses': [
                # `Integer` của Odoo không phân biệt được "chưa ghi tiếp" với
                # "ghi tiếp tại mốc 0 ms": trường rỗng đọc ra là số 0, không
                # phải `False`/`None`. Ép `0`/rỗng thành `null` để worker biết
                # đây là khoảng dừng CÒN MỞ (kéo dài tới hết cuộc họp), không
                # phải một khoảng dừng dài đúng 0 ms ở đầu bản ghi.
                {'paused_at_ms': p.paused_at_ms,
                 'resumed_at_ms': p.resumed_at_ms or None}
                for p in self.sudo().pause_ids.sorted('paused_at_ms')
            ],
        }
        (chunk_dir / "metadata.json").write_text(
            json.dumps(metadata, ensure_ascii=False))

        ai_url = self._config('ai_service_url', 'http://ai-worker:8000')
        webhook_base = os.environ.get('WEBHOOK_BASE_URL', 'http://odoo:8069')
        webhook_url = f"{webhook_base}/aidt_meeting/api/webhook/summary/{self.id}"

        try:
            import requests
            requests.post(
                f"{ai_url}/jobs/process_meeting",
                json={
                    'meeting_id': self.id,
                    'total_chunks': total_chunks,
                    'webhook_url': webhook_url,
                    # Đẩy cấu hình sang worker: các ô trong Cài đặt trước đây
                    # không điều khiển gì cả vì worker ghim cứng model/URL.
                    #
                    # `asr_ct2_model` chứ KHÔNG PHẢI `asr_model`: hai tham số
                    # này nói hai ngôn ngữ khác nhau. `asr_model` là tên model
                    # của đường vLLM cũ (`openai/whisper-large-v3` — một repo
                    # HF thường), còn worker chạy faster-whisper, vốn chỉ nhận
                    # tên kích cỡ (`large-v3`) hoặc một repo đã chuyển sang
                    # CTranslate2. Đẩy nhầm giá trị kia sang là lỗi
                    # "Invalid model size" ngay lúc nạp model — đã xảy ra thật
                    # với `PhoWhisper-large-ct2` trong log của worker. Không
                    # đặt thì worker dùng mặc định `large-v3` của chính nó.
                    'asr_model': self._config('asr_ct2_model') or None,
                    # `or None` cho prompt/model = "không đặt, worker dùng
                    # mặc định của nó". KHÔNG dùng cho `asr_language`: rỗng
                    # ở đó là một LỰA CHỌN THẬT ("để model tự nhận dạng",
                    # dùng cho họp song ngữ), nên phải gửi đúng chuỗi rỗng
                    # thay vì để worker lùi về 'vi'.
                    'asr_prompt': self._config('asr_prompt') or None,
                    'asr_language': self._config('asr_language') or '',
                    'llm_model': self._config('llm_model') or None,
                },
                timeout=5
            )
        except Exception as e:
            _logger.error(f"Failed to trigger AI service for meeting {self.id}: {e}")
            self.sudo().write({'state': 'failed'})

    @api.model
    def action_active_recording(self, channel_id):
        """Bản ghi đang chạy trên kênh này, cho một máy vừa vào họp / vừa F5.

        Tìm cả `paused`: broadcast `started` chỉ phát một lần lúc bật, nên
        người vào sau chỉ biết được qua đường này. Chốt ở `recording` nghĩa
        là người vào giữa lúc tạm dừng không thấy thông báo nào và tưởng cuộc
        họp không được ghi.

        TRONG PHÒNG HỌP, luôn trả `host_partner_id` — kể cả khi không có bản
        ghi nào đang chạy — lấy từ `channel.aidt_call_host_partner_id` (chủ phòng của
        CUỘC GỌI, chốt lúc phiên RTC đầu tiên được tạo, xem
        `discuss_channel_rtc_session.py`), KHÔNG phải `recording.host_partner_id`
        (chủ của một bản ghi cụ thể, chỉ tồn tại khi đang ghi). Đây là điều
        kiện DUY NHẤT để client biết ai được phép thấy nút "Bật ghi âm biên
        bản" TRƯỚC khi có bản ghi nào — thiếu nó thì mọi thành viên cuộc gọi
        đều thấy nút, dù server vẫn chặn đúng ở `_start_for_channel`, người
        không phải chủ phòng bấm vào chỉ để ăn một AccessError.

        Kênh KHÔNG phải phòng họp và KHÔNG có bản ghi nào đang mở thì trả
        `{}` tuyệt đối. Hai điều kiện đó phải xét theo đúng thứ tự này: một
        bản ghi đang mở luôn thắng, kể cả khi kênh vừa thôi là phòng họp —
        xem chú thích trong thân hàm.
        """
        channel = self.env['discuss.channel'].browse(int(channel_id)).exists()
        if not channel:
            return {}
        partner = self.env.user.partner_id
        if not self._is_channel_member(channel, partner):
            raise AccessError(_('Bạn không thuộc cuộc gọi này.'))
        # Bản ghi đang mở phải được tra TRƯỚC lối tắt "kênh thường" bên dưới.
        # Kênh có thể THÔI là phòng họp trong lúc bản ghi vẫn đang chạy —
        # cuộc họp bị xoá khỏi Lịch, hoặc `videocall_channel_id` bị gỡ, giữa
        # lúc cuộc gọi tiếp diễn. Lối tắt đứng trước thì mọi máy F5 hoặc vào
        # muộn nhận `{}`, `recorder_service` đặt `hostPartnerId = null` và
        # băng 🔴 "Cuộc họp đang được ghi âm…" BIẾN MẤT trong khi
        # `/aidt_meeting/chunk` vẫn nhận audio (`_store`/`_is_participant`
        # không hỏi tới event). Ghi âm tiếp mà không còn thông báo là hỏng
        # nghĩa vụ thông báo, không phải lỗi hiển thị.
        recording = self.sudo().search([
            ('channel_id', '=', channel.id),
            ('state', 'in', OPEN_STATES),
        ], limit=1)
        if not recording:
            # Kênh thường không có gì để trả: `host_partner_id` là điều kiện
            # DUY NHẤT làm nút "Bật ghi âm biên bản" hiện ra
            # (RecordingBanner.canStart đòi isHost, isHost đòi hostPartnerId).
            # Trả nó cho kênh thường nghĩa là mọi thành viên đều thấy nút mời
            # họ bấm rồi ăn AccessError.
            if not self._event_for_channel(channel):
                return {}
            # Rỗng khi chưa ai vào cuộc gọi hoặc chủ phòng đã rời — fail
            # closed, đúng hướng: không suy ra bừa một chủ phòng khác.
            return {'host_partner_id': channel.sudo().aidt_call_host_partner_id.id}
        recording._register_participants()
        return {
            'recording_id': recording.id,
            'channel_id': channel.id,
            'elapsed_ms': recording._elapsed_ms(),
            'state': recording.state,
            'take': recording.current_take,
            'host_partner_id': recording.host_partner_id.id,
        }

    def _elapsed_ms(self):
        self.ensure_one()
        if not self.started_at:
            return 0
        delta = fields.Datetime.now() - self.started_at
        return int(delta.total_seconds() * 1000)

    def _broadcast_state(self, action):
        """Báo cho mọi client trong kênh để chúng bật/tắt thu âm.

        Bus phát MỘT payload chung cho mọi người — không cá nhân hoá được —
        nên payload mang `host_partner_id` để mỗi client tự so với partner
        của chính mình mà chọn dạng băng thông báo.
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
            'state': self.state,
            'take': self.current_take,
            'host_partner_id': self.sudo().host_partner_id.id,
        })
