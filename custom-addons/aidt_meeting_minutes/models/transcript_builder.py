from odoo import api, models

# Số từ tối đa thử khớp ở mối nối. Chồng lấn là 1.5 giây, người nói nhanh
# nhất cũng khó vượt ~12 từ trong ngần ấy thời gian.
MAX_OVERLAP_WORDS = 12


class AidtMeetingTranscript(models.AbstractModel):
    _name = 'aidt.meeting.transcript'
    _description = 'Dựng bản bóc băng từ các đoạn'

    @api.model
    def _format_ts(self, ms):
        total = max(0, ms) // 1000
        return f'{total // 60:02d}:{total % 60:02d}'

    @api.model
    def _strip_overlap(self, previous, current):
        """Bỏ phần đầu của `current` nếu nó lặp lại phần đuôi của `previous`.

        Khớp theo TỪ chứ không theo ký tự: bóc băng hai lần cùng một đoạn
        audio hiếm khi ra chuỗi ký tự trùng khít, nhưng chuỗi từ thì thường
        trùng. Thử từ dài đến ngắn để lấy phần chồng lớn nhất.
        """
        prev_words = previous.split()
        cur_words = current.split()
        if not prev_words or not cur_words:
            return current
        limit = min(MAX_OVERLAP_WORDS, len(prev_words), len(cur_words))
        for size in range(limit, 0, -1):
            tail = [w.lower().strip('.,;:!?') for w in prev_words[-size:]]
            head = [w.lower().strip('.,;:!?') for w in cur_words[:size]]
            if tail == head:
                return ' '.join(cur_words[size:])
        return current

    @api.model
    def _gap_markers(self, recording):
        """Một dòng cho mỗi mẩu audio hỏng, kèm mốc thời gian."""
        failed = self.env['aidt.meeting.chunk'].sudo().search([
            ('recording_id', '=', recording.id), ('state', '=', 'failed'),
        ], order='offset_ms')
        markers = []
        for chunk in failed:
            start = self._format_ts(chunk.offset_ms)
            end = self._format_ts(chunk.offset_ms + chunk.duration_ms)
            markers.append({
                'start_ms': chunk.offset_ms,
                'line': (f'[thiếu âm thanh {start}–{end}: '
                         f'{chunk.partner_id.name}]'),
            })
        return markers

    @api.model
    def _build(self, recording):
        segments = self.env['aidt.meeting.segment'].sudo().search(
            [('recording_id', '=', recording.id)], order='start_ms, id')

        blocks = []
        for seg in segments:
            text = (seg.text or '').strip()
            if not text:
                continue
            if blocks and blocks[-1]['partner'] == seg.partner_id:
                text = self._strip_overlap(blocks[-1]['text'], text)
                if not text:
                    continue
                blocks[-1]['text'] = f"{blocks[-1]['text']} {text}"
                continue
            blocks.append({
                'partner': seg.partner_id,
                'start_ms': seg.start_ms,
                'text': text,
            })

        lines = []
        for block in blocks:
            lines.append({
                'start_ms': block['start_ms'],
                'line': (f"[{self._format_ts(block['start_ms'])}] "
                         f"{block['partner'].name}: {block['text']}"),
            })
        lines += self._gap_markers(recording)
        lines.sort(key=lambda item: item['start_ms'])

        header = []
        declined = recording.sudo().declined_partner_ids
        if declined:
            names = ', '.join(declined.mapped('name'))
            # Nêu tên ngay đầu bản: người đọc phải biết thiếu giọng của ai,
            # thay vì tưởng những người đó im lặng suốt cuộc họp.
            header.append(
                f'Không ghi âm giọng của: {names} (đã từ chối ghi âm).')

        body = '\n'.join(item['line'] for item in lines)
        if header:
            return '\n\n'.join(['\n'.join(header), body])
        return body
