import json
import logging

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError

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

    # Những người ĐÃ THỰC SỰ có mặt trong CUỘC GỌI trong lúc bản ghi này chạy
    # (có phiên `discuss.channel.rtc.session` trên kênh). Khác hẳn "thành viên
    # kênh": một kênh phòng ban 200 người thì 197 người trong đó chưa bao giờ
    # vào cuộc gọi 3 người này. Xem `_is_participant`.
    participant_partner_ids = fields.Many2many(
        'res.partner', 'aidt_meeting_recording_participant_rel',
        'recording_id', 'partner_id', string='Người có mặt trong cuộc gọi')

    transcript_text = fields.Text(string='Bản bóc băng', readonly=True)
    summary_text = fields.Text(string='Tóm tắt', readonly=True)

    title = fields.Char(string='Tiêu đề')
    overview = fields.Text(string='Tổng quan')
    meeting_minutes = fields.Text(string='Biên bản')
    key_points = fields.Text(string='Ý chính (JSON)')
    risks = fields.Text(string='Rủi ro (JSON)')
    key_points_html = fields.Html(string='Ý chính', compute='_compute_json_html')
    risks_html = fields.Html(string='Rủi ro', compute='_compute_json_html')

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
    action_item_ids = fields.One2many('aidt.meeting.action.item', 'recording_id', string='Công việc')
    decision_ids = fields.One2many('aidt.meeting.decision', 'recording_id', string='Quyết định')

    def init(self):
        """Chỉ mục UNIQUE riêng phần: mỗi kênh chỉ có một bản ghi đang hoạt
        động (recording/processing) tại một thời điểm.
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

        event = self._event_for_channel(channel)
        if event:
            if event.user_id != self.env.user:
                raise AccessError(_(
                    'Chỉ người chủ trì cuộc họp mới bật được ghi âm.'))
            secrecy = event.secrecy or 'thuong'
        else:
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
        """Wrapper PUBLIC của `_start_for_channel`"""
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
        
        # Trigger external AI service
        self._trigger_ai_service()
        return True

    def _trigger_ai_service(self):
        self.ensure_one()
        ai_url = self._config('ai_service_url', 'http://localhost:8000')
        webhook_url = f"{self.env['ir.config_parameter'].sudo().get_param('web.base.url')}/aidt_meeting/api/webhook/summary/{self.id}"
        total_chunks = self.env['aidt.meeting.chunk'].sudo().search_count([('recording_id', '=', self.id)])
        
        try:
            import requests
            requests.post(
                f"{ai_url}/jobs/process_meeting",
                json={
                    'meeting_id': self.id,
                    'total_chunks': total_chunks,
                    'webhook_url': webhook_url
                },
                timeout=5
            )
        except Exception as e:
            _logger.error(f"Failed to trigger AI service for meeting {self.id}: {e}")

    def _decline(self, partner):
        self.ensure_one()
        if not self._is_participant(self.env.user.partner_id):
            raise AccessError(_('Bạn không thuộc cuộc gọi này.'))
        self.sudo().write({'declined_partner_ids': [(4, partner.id)]})
        return True

    def action_decline(self):
        """Wrapper PUBLIC của `_decline`"""
        self.ensure_one()
        return self._decline(self.env.user.partner_id)

    @api.model
    def action_active_recording(self, channel_id):
        """Bản ghi đang chạy trên kênh này, cho một máy vừa vào họp / vừa F5."""
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
        """Báo cho mọi client trong kênh để chúng bật/tắt thu âm."""
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
