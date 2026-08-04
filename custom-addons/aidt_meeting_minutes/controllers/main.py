import logging

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)

# Chặn trần kích thước để một client hỏng không đẩy được tệp khổng lồ:
# 15 giây mono 32 kbps ~ 60 KB, nên 2 MB đã rộng gấp nhiều lần.
MAX_CHUNK_BYTES = 2 * 1024 * 1024


class AidtMeetingController(http.Controller):

    @http.route('/aidt_meeting/chunk', type='http', auth='user',
                methods=['POST'], csrf=False)
    def upload_chunk(self, recording_id, seq, offset_ms, duration_ms,
                     audio, **kwargs):
        """Nhận một mẩu audio và trả 200 ngay. KHÔNG gọi ASR ở đây.

        Bóc băng chạy trong cron: nếu gọi ASR đồng bộ trong request thì một
        GPU chậm sẽ giữ worker HTTP và làm nghẽn chính cuộc gọi đang diễn ra.
        """
        recording = request.env['aidt.meeting.recording'].browse(
            int(recording_id)).exists()
        if not recording:
            return request.make_json_response({'error': 'not_found'}, status=404)

        raw = audio.read()
        if len(raw) > MAX_CHUNK_BYTES:
            return request.make_json_response(
                {'error': 'too_large'}, status=413)

        # partner LẤY TỪ PHIÊN ĐĂNG NHẬP, không bao giờ từ payload.
        partner = request.env.user.partner_id
        try:
            request.env['aidt.meeting.chunk']._store(
                recording, partner, int(seq), int(offset_ms),
                int(duration_ms), raw)
        except Exception as exc:                     # noqa: BLE001
            _logger.warning('Từ chối mẩu audio cho bản ghi %s: %s',
                            recording.id, exc)
            return request.make_json_response({'error': 'rejected'}, status=403)
        return request.make_json_response({'ok': True})
