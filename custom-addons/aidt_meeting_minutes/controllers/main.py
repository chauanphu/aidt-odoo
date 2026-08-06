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

            # KHÔNG phải hàng rào chống DoS bộ nhớ: Werkzeug đã đọc và đệm
            # xong toàn bộ body trước khi hàm này chạy, nên tới đây dữ liệu
            # nằm sẵn trong RAM/tệp tạm rồi. Trần này chỉ giới hạn thứ được
            # GHI XUỐNG (ir.attachment/filestore). Muốn chặn ở tầng bộ nhớ
            # thì phải đặt trần ở reverse proxy (`client_max_body_size`) hoặc
            # ở `--limit-request-...` của tầng WSGI, không phải ở đây.
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

    @http.route('/discuss/channel/<int:channel_id>/stream_audio', type='http', auth='user', methods=['POST'], csrf=False)
    def stream_audio_subtitle(self, channel_id, audio, **kwargs):
        """Nhận chunk audio ngắn, xử lý STT nhanh và broadcast qua bus."""
        partner = request.env.user.partner_id
        channel = request.env['discuss.channel'].search([('id', '=', channel_id)])
        if not channel:
            return request.make_json_response({'error': 'not_found'}, status=404)

        raw_audio = audio.read()
        if len(raw_audio) < 100:  # Quá ngắn hoặc rỗng
            return request.make_json_response({'ok': True})

        # TODO: Tích hợp VAD và Whisper fast STT ở đây.
        # Tạm thời giả lập kết quả trả về để hoàn thiện luồng UI.
        transcript = "..."  # Sẽ thay bằng kết quả của model ASR sau

        if transcript:
            request.env['bus.bus']._sendone(
                channel,
                'aidt_meeting_minutes/subtitle_update',
                {
                    'text': transcript,
                    'speaker_name': partner.name,
                    'partner_id': partner.id,
                }
            )

        return request.make_json_response({'ok': True})

