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

        GIỚI HẠN: khớp theo từ nguyên văn không bắt được trường hợp hai lượt
        bóc băng của CÙNG một đoạn audio chồng lấn ra hai chuỗi từ khác nhau
        quá mức viết hoa/dấu câu — ví dụ ASR chọn từ khác, số viết bằng chữ
        số ở lượt này và bằng chữ ở lượt kia, hoặc câu bị diễn đạt lại do
        cửa sổ ngữ cảnh khác nhau. Khi đó phần chồng lấn không bị xoá và
        transcript sẽ lặp chữ ở mối nối — đây là đánh đổi CÓ CHỦ Ý (khớp mờ/
        fuzzy sẽ là làm quá tay cho bài toán này), không phải lỗi cần sửa
        khi gặp trong dữ liệu thật.

        `MAX_OVERLAP_WORDS = 12` là một con số ước lượng theo giả định (chồng
        lấn 1.5 giây), CHƯA được hiệu chỉnh trên đầu ra ASR thật — theo quy
        ước của dự án, ngưỡng chưa hiệu chỉnh phải được nêu rõ như thế này.
        """
        prev_words = previous.split()
        cur_words = current.split()
        if not prev_words or not cur_words:
            return current
        limit = min(MAX_OVERLAP_WORDS, len(prev_words), len(cur_words))
        # Yêu cầu khớp TỐI THIỂU 2 từ mới xoá. Hai hướng sai không cân nhau:
        # xoá thiếu để lại một từ lặp mà người đọc NHÌN THẤY và tự sửa được;
        # xoá thừa làm mất nội dung ÂM THẦM, không dấu vết, trong một biên
        # bản chính thức — với văn bản tiếng Việt, các từ đệm/xác nhận ngắn
        # như "vâng", "rồi", "được", "vậy", "dạ" thường xuyên vừa kết thúc
        # câu này vừa mở đầu câu sau, nên khớp 1 từ là trùng hợp phổ biến chứ
        # không phải bằng chứng chắc chắn về seam. Vì vậy thiên về giữ lại
        # từ lặp (an toàn hơn) thay vì xoá nhầm.
        for size in range(limit, 1, -1):
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
