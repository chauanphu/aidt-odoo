import json
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
    def stream_audio_subtitle(self, channel_id, audio=None, **kwargs):
        """Nhận chunk audio ngắn, xử lý STT nhanh và broadcast qua bus."""
        if not audio:
            return request.make_json_response({'error': 'bad_request'}, status=400)

        partner = request.env.user.partner_id
        channel = request.env['discuss.channel'].search([('id', '=', channel_id)])
        if not channel:
            return request.make_json_response({'error': 'not_found'}, status=404)

        try:
            raw_audio = audio.read()
        except Exception as e:
            _logger.warning('Lỗi đọc luồng audio stream: %s', e)
            return request.make_json_response({'error': 'bad_request'}, status=400)

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

    @http.route('/aidt_meeting/api/save_segment', type='json', auth='none', methods=['POST'], csrf=False)
    def api_save_segment(self, **kwargs):
        """API lưu segment STT từ dịch vụ FastAPI và broadcast qua bus.bus."""
        payload = kwargs
        if hasattr(request, 'jsonrequest') and isinstance(request.jsonrequest, dict):
            if 'params' in request.jsonrequest and isinstance(request.jsonrequest['params'], dict):
                payload = {**payload, **request.jsonrequest['params']}
            else:
                payload = {**payload, **request.jsonrequest}

        channel_id = payload.get('channel_id')
        text = payload.get('text')
        speaker_id = payload.get('speaker_id')
        session_id = payload.get('session_id')
        start_ms = payload.get('start_ms', 0)
        end_ms = payload.get('end_ms', 0)

        if not text or not channel_id:
            return {'error': 'missing_data'}

        try:
            c_id = int(channel_id)
        except (ValueError, TypeError):
            return {'error': 'invalid_channel_id'}

        channel = request.env['discuss.channel'].sudo().search([('id', '=', c_id)], limit=1)
        if not channel:
            return {'error': 'channel_not_found'}

        # Find active recording if present
        recording = request.env['aidt.meeting.recording'].sudo().search([
            ('channel_id', '=', channel.id),
            ('state', '=', 'recording')
        ], limit=1)

        # Resolve partner before bus broadcast to populate speaker_name and partner_id
        partner = None
        if speaker_id:
            try:
                partner = request.env['res.partner'].sudo().browse(int(speaker_id)).exists()
            except (ValueError, TypeError):
                pass
        if not partner and recording and recording.started_by_id:
            partner = recording.started_by_id.partner_id

        # Broadcast subtitle_update event via bus.bus for channel participants
        request.env['bus.bus'].sudo()._sendone(
            channel,
            'aidt_meeting_minutes/subtitle_update',
            {
                'text': text,
                'speaker_id': speaker_id,
                'speaker_name': partner.name if partner else '',
                'partner_id': partner.id if partner else False,
                'session_id': session_id,
                'channel_id': channel.id,
            }
        )

        # Save to aidt.meeting.segment if active recording exists and partner is resolved
        if recording and partner:
            try:
                s_ms = int(start_ms) if start_ms is not None else 0
            except (ValueError, TypeError):
                s_ms = 0

            try:
                e_ms = int(end_ms) if end_ms is not None else 0
            except (ValueError, TypeError):
                e_ms = 0

            if e_ms < s_ms:
                e_ms = s_ms

            request.env['aidt.meeting.segment'].sudo().create({
                'recording_id': recording.id,
                'partner_id': partner.id,
                'start_ms': s_ms,
                'end_ms': e_ms,
                'text': text,
            })

        return {'ok': True}

    @http.route('/aidt_meeting/api/webhook/summary/<int:recording_id>', type='json', auth='public', methods=['POST'], csrf=False)
    def receive_ai_summary(self, recording_id, **kw):
        recording = request.env['aidt.meeting.recording'].sudo().browse(recording_id)
        if not recording.exists():
            return {'status': 'error', 'message': 'Recording not found'}

        data = request.jsonrequest if hasattr(request, 'jsonrequest') and request.jsonrequest else {}

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

        return {'status': 'success'}


