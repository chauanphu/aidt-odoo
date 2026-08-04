import logging

from odoo import http
from odoo.exceptions import AccessError, UserError
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
        # partner LẤY TỪ PHIÊN ĐĂNG NHẬP, không bao giờ từ payload.
        partner = request.env.user.partner_id
        try:
            recording = request.env['aidt.meeting.recording'].browse(
                int(recording_id)).exists()
            if not recording:
                return request.make_json_response(
                    {'error': 'not_found'}, status=404)

            raw = audio.read()
            if len(raw) > MAX_CHUNK_BYTES:
                return request.make_json_response(
                    {'error': 'too_large'}, status=413)

            request.env['aidt.meeting.chunk']._store(
                recording, partner, int(seq), int(offset_ms),
                int(duration_ms), raw)
        except (ValueError, AccessError, UserError) as exc:
            # Payload sai dạng (recording_id/seq/offset_ms/duration_ms không
            # phải số) hoặc bị `_store` từ chối hợp lệ (không thuộc cuộc gọi,
            # bản ghi đã dừng, giả mạo partner...): đây là lỗi CỦA CLIENT,
            # trả 403 có cấu trúc.
            _logger.warning('Từ chối mẩu audio cho recording_id=%s: %s',
                            recording_id, exc)
            return request.make_json_response({'error': 'rejected'}, status=403)
        except Exception:                              # noqa: BLE001
            # Lỗi thật (bug, DB down, ...) — KHÔNG được báo cho client như
            # thể là "bị từ chối hợp lệ", nếu không đội vận hành sẽ không
            # bao giờ thấy nó nổi lên như một 5xx để mà theo dõi.
            _logger.exception(
                'Lỗi khi lưu mẩu audio cho recording_id=%s', recording_id)
            return request.make_json_response(
                {'error': 'internal_error'}, status=500)
        return request.make_json_response({'ok': True})
