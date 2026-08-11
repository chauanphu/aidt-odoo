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

    def _is_host(self, partner):
        """Người này có phải chủ phòng của bản ghi này không."""
        self.ensure_one()
        return bool(partner) and partner == self.sudo().host_partner_id

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

        host = channel.sudo().aidt_call_host_partner_id
        if not host:
            raise AccessError(_(
                'Chưa có cuộc gọi nào đang diễn ra trên kênh này.'))
        if host != partner:
            raise AccessError(_(
                'Chỉ chủ phòng mới bật được ghi âm.'))

        event = self._event_for_channel(channel)
        if event:
            # Cuộc họp có lịch thì người chủ trì trong lịch vẫn là tiếng nói
            # cuối cùng — chủ phòng của cuộc gọi không vượt được quyền đó.
            if event.user_id != self.env.user:
                raise AccessError(_(
                    'Chỉ người chủ trì cuộc họp mới bật được ghi âm.'))
            secrecy = event.secrecy or 'thuong'
        else:
            secrecy = 'thuong'
        self._check_secrecy_allowed(secrecy)

        existing = self.sudo().search([
            ('channel_id', '=', channel.id),
            ('state', 'in', ('recording', 'paused', 'processing')),
        ], limit=1)
        if existing:
            raise UserError(_('Cuộc gọi này đang được ghi âm rồi.'))

        recording = self.sudo().create({
            'channel_id': channel.id,
            'event_id': event.id if event else False,
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
        self.ensure_one()
        if not self._is_host(self.env.user.partner_id):
            raise AccessError(_('Chỉ chủ phòng mới tạm dừng được ghi âm.'))
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
        self.ensure_one()
        if not self._is_host(self.env.user.partner_id):
            raise AccessError(_('Chỉ chủ phòng mới ghi tiếp được.'))
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
        if self.state not in ('recording', 'paused'):
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
        self.ensure_one()
        if not self._is_host(self.env.user.partner_id):
            raise AccessError(_('Chỉ chủ phòng mới kết thúc được ghi âm.'))
        return self._end_recording()

    def _trigger_ai_service(self):
        """Xuất mẩu audio ra đĩa rồi đẩy job sang worker.

        Mẩu được xuất GOM THEO NGƯỜI NÓI, giữ nguyên thứ tự `seq` của chính
        người đó. Bản trước đánh số lại toàn bộ theo một dãy `chunk_{idx}`
        phẳng, nhưng `seq` là duy nhất theo TỪNG người chứ không phải theo bản
        ghi — nên dãy phẳng đó trộn lẫn hai người vào nhau và không còn là thứ
        tự thời gian. Worker cần biết mẩu nào thuộc luồng nào để nối lại đúng
        một luồng liên tục cho mỗi máy (xem docker/ai_worker/main.py).
        """
        self.ensure_one()

        import base64
        import json
        import os
        from pathlib import Path

        chunk_dir = Path(f"/var/lib/odoo/meetings/{self.id}")
        chunk_dir.mkdir(parents=True, exist_ok=True)

        chunks = self.env['aidt.meeting.chunk'].sudo().search(
            [('recording_id', '=', self.id)], order='partner_id, seq asc')

        speakers = {}
        total_chunks = 0
        for chunk in chunks:
            if not (chunk.attachment_id and chunk.attachment_id.datas):
                continue
            partner = chunk.partner_id
            chunk_file = f"spk{partner.id}_{chunk.seq:05d}.webm"
            (chunk_dir / chunk_file).write_bytes(
                base64.b64decode(chunk.attachment_id.datas))
            total_chunks += 1

            entry = speakers.setdefault(partner.id, {
                'partner_id': partner.id,
                'speaker_name': partner.name or 'Unknown',
                # Mốc bắt đầu của LUỒNG là offset của mẩu ĐẦU TIÊN người đó
                # gửi; các mẩu sau nối liền vào đó nên không cần offset riêng.
                'offset_ms': chunk.offset_ms,
                'files': [],
            })
            entry['files'].append(chunk_file)
            entry['offset_ms'] = min(entry['offset_ms'], chunk.offset_ms)

        (chunk_dir / "metadata.json").write_text(json.dumps(
            {'speakers': list(speakers.values())}, ensure_ascii=False))

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
        """
        channel = self.env['discuss.channel'].browse(int(channel_id)).exists()
        if not channel:
            return {}
        partner = self.env.user.partner_id
        if not self._is_channel_member(channel, partner):
            raise AccessError(_('Bạn không thuộc cuộc gọi này.'))
        recording = self.sudo().search([
            ('channel_id', '=', channel.id),
            ('state', 'in', ('recording', 'paused')),
        ], limit=1)
        if not recording:
            return {}
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
