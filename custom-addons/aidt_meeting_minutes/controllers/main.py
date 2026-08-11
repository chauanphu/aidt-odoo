import json
import logging

from odoo import http
from odoo.exceptions import AccessError, UserError
from odoo.http import request

_logger = logging.getLogger(__name__)

# Chặn trần kích thước để một client hỏng không đẩy được tệp khổng lồ:
# 15 giây mono 32 kbps ~ 60 KB, nên 2 MB đã rộng gấp nhiều lần.
MAX_CHUNK_BYTES = 50 * 1024 * 1024


class AidtMeetingController(http.Controller):

    @http.route('/aidt_meeting/chunk', type='http', auth='public',
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

    @http.route('/aidt_meeting/audio/<int:recording_id>', type='http', auth='public', cors='*')
    def get_meeting_audio(self, recording_id, **kwargs):
        recording = request.env['aidt.meeting.recording'].browse(recording_id)
        if not recording.exists():
            return request.not_found()
        
        import os
        audio_path = f"/var/lib/odoo/meetings/{recording_id}/full_audio.wav"
        if not os.path.exists(audio_path):
            return request.not_found()
            
        try:
            return http.Stream.from_path(audio_path).get_response()
        except AttributeError:
            with open(audio_path, 'rb') as f:
                return request.make_response(f.read(), headers=[
                    ('Content-Type', 'audio/wav'),
                    ('Content-Disposition', f'inline; filename="meeting_{recording_id}.wav"'),
                    ('Accept-Ranges', 'bytes')
                ])

    # ĐÃ GỠ hai route của đường phụ đề thời gian thực:
    #   * `/discuss/channel/<id>/stream_audio` — chưa bao giờ bóc băng thật,
    #     nó phát cố định chuỗi "..." vào bus kèm một TODO.
    #   * `/aidt_meeting/api/save_segment` — `auth='none'`, tức KHÔNG xác
    #     thực, và nó `sudo()._sendone()` vào bất kỳ `discuss.channel` nào
    #     theo id lấy thẳng từ payload: ai gọi được cũng phát được chữ tuỳ ý
    #     vào cuộc họp của người khác. Nó còn `create()` trên
    #     `aidt.meeting.segment` — model đã bị xoá cùng đợt refactor sang xử
    #     lý theo lô, nên gọi vào là KeyError chứ không phải chạy sai.
    # Không còn phía gọi nào sau khi bỏ phụ đề thời gian thực (bản bóc băng
    # giờ dựng một lần ở docker/ai_worker khi cuộc họp kết thúc).

    @http.route('/aidt_meeting/api/webhook/summary/<int:recording_id>', type='http', auth='public', methods=['POST'], csrf=False)
    def receive_ai_summary(self, recording_id, **kw):
        recording = request.env['aidt.meeting.recording'].sudo().browse(recording_id)
        if not recording.exists():
            return request.make_response(json.dumps({'status': 'error', 'message': 'Recording not found'}), headers=[('Content-Type', 'application/json')])

        try:
            data = json.loads(request.httprequest.data)
        except Exception:
            data = {}

        # Worker báo hỏng: chuyển sang `failed` thay vì để bản ghi nằm mãi ở
        # `processing`. Trạng thái này vốn đã có trong Selection nhưng trước
        # đây không có đường nào đặt được nó — worker chỉ ghi log rồi im, nên
        # một job hỏng và một job đang chạy trông giống hệt nhau từ giao diện.
        # Mẩu audio KHÔNG bị xoá, chạy lại được (docs §8).
        if data.get('error'):
            _logger.error('Worker báo lỗi khi xử lý bản ghi %s: %s',
                          recording_id, data['error'])
            recording.write({'state': 'failed'})
            if recording.channel_id:
                recording.channel_id._bus_send(
                    'aidt_meeting_minutes/recording_state', {
                        'action': 'summary_failed',
                        'recording_id': recording.id,
                    })
            return request.make_response(
                json.dumps({'status': 'error_recorded'}),
                headers=[('Content-Type', 'application/json')])

        # Update text fields
        recording.write({
            'title': data.get('title', ''),
            'overview': data.get('overview', ''),
            'meeting_minutes': data.get('meeting_minutes', ''),
            'key_points': json.dumps(data.get('key_points', []), ensure_ascii=False),
            'risks': json.dumps(data.get('risks', []), ensure_ascii=False),
            'transcript_text': data.get('transcript_raw', ''),
            'state': 'done'
        })

        # Clear existing action items and decisions
        recording.action_item_ids.unlink()
        recording.decision_ids.unlink()

        # Build action items (fuzzy match for assignee_name can be improved later)
        action_items = []
        for ai in data.get('action_items', []):
            assignee_name = ai.get('owner')
            action_items.append((0, 0, {
                'task': ai.get('task'),
                'owner': assignee_name,
                'deadline': ai.get('deadline'),
                'priority': ai.get('priority', 'medium'),
                'timestamp': ai.get('timestamp'),
            }))

        decisions = []
        for dec in data.get('decisions', []):
            decisions.append((0, 0, {
                'content': dec.get('content'),
                'timestamp': dec.get('timestamp'),
            }))

        recording.write({
            'action_item_ids': action_items,
            'decision_ids': decisions
        })
        
        if recording.channel_id:
            recording.channel_id._bus_send('aidt_meeting_minutes/recording_state', {
                'action': 'summary_done',
                'recording_id': recording.id,
            })

        return request.make_response(json.dumps({'status': 'success'}), headers=[('Content-Type', 'application/json')])

    # ĐÃ GỠ `/aidt_meeting/api/finalize_recording`.
    #
    # Nó gọi `action_stop()` cho TOÀN BỘ bản ghi mỗi khi một client kết thúc
    # phiên thu của mình — mà `recorder_service.stop()` chạy trên mọi đường
    # rời cuộc gọi. Hệ quả: một người đóng tab ở phút thứ 5 làm cả cuộc họp
    # mất phần còn lại của biên bản.
    #
    # Bản ghi giờ chỉ kết thúc từ hai nguồn: chủ phòng bấm [Kết thúc], hoặc
    # cuộc gọi trống (móc `unlink` của discuss.channel.rtc.session).
