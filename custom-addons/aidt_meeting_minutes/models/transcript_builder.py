from odoo import api, models

# Số từ tối đa thử khớp ở mối nối. Chồng lấn là 1.5 giây, người nói nhanh
# nhất cũng khó vượt ~12 từ trong ngần ấy thời gian.
MAX_OVERLAP_WORDS = 12

# Số VỊ TRÍ được thử khi dò lùi tìm đoạn lặp trong `previous` — tính cả vị
# trí sát đuôi, nên thực tế là chấp nhận tối đa 5 từ thừa ở đuôi `previous`.
# Đoạn khớp không bắt buộc phải nằm sát đuôi nữa.
# Lý do cần dò lùi: mẩu trước và mẩu sau bóc băng ĐỘC LẬP cùng
# 1.5 giây audio, nên mẩu trước hay đẻ thêm vài từ ở đuôi mà mẩu sau không
# có (từ đệm, một từ bị nghe thành hai, hoặc ảo giác cuối mẩu). Chỉ cần MỘT
# từ thừa như vậy là phép khớp sát-đuôi trượt hoàn toàn và biên bản lặp chữ.
#
# TẠI SAO GIỮ 6 MÀ KHÔNG NỚI RỘNG HƠN: mỗi vị trí dò thêm là một cơ hội
# khớp NHẦM vào một cụm từ lặp lại tự nhiên trong câu ("cuộc họp hôm nay …
# cuộc họp hôm nay"), và hậu quả của khớp nhầm là xoá nội dung ÂM THẦM khỏi
# một biên bản chính thức (xem lập luận trong `_strip_overlap`). 6 là con số
# của dự án tham chiếu, tương ứng khoảng nửa giây lời nói — đủ để nuốt vài
# từ thừa ở đuôi mẩu, nhưng vẫn giữ vùng dò nằm gọn trong phần audio thật
# sự chồng lấn. Nới rộng hơn là nới vùng có thể xoá nhầm ra ngoài vùng chồng
# lấn, tức là đổi một lỗi NHÌN THẤY ĐƯỢC lấy một lỗi KHÔNG NHÌN THẤY.
#
# Cả hai hằng số này CHƯA được hiệu chỉnh trên đầu ra ASR thật.
MAX_OVERLAP_BACKSEARCH = 6


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

        Đoạn lặp KHÔNG bắt buộc nằm sát đuôi `previous`: ta thử
        `MAX_OVERLAP_BACKSEARCH` vị trí lùi dần từ đuôi vào (xem lập luận ở
        khai báo hằng số). Đây là phần dò lùi lấy từ dự án tham chiếu
        `STT_T-m-T-t-AI` (`_strip_overlap_prefix`) — nó chữa đúng cái ca hay
        gặp nhất: mẩu trước kết thúc bằng vài từ mà mẩu sau không nghe ra,
        khiến phép khớp sát-đuôi trượt sạch dù phần chồng lấn rành rành.

        CỐ Ý KHÔNG PORT tầng khớp theo KÝ TỰ của dự án tham chiếu (hậu tố
        120 ký tự khớp tiền tố 120 ký tự, tối thiểu 5 ký tự). Với tiếng Việt
        đơn âm, 5 ký tự chỉ là một từ rưỡi ("cuộc", "họp l") — ngưỡng đó
        lỏng tới mức xoá cả nội dung thật. Chỉ khớp theo TỪ.

        CHUẨN HOÁ để so sánh giữ nguyên `lower()` + `strip('.,;:!?')`, KHÔNG
        đổi sang `re.sub(r"[^\\w\\s]", "", w.lower())` của dự án tham chiếu.
        Regex đó xoá mọi ký tự không phải chữ ở MỌI vị trí trong từ, nên
        "TP.HCM" == "TPHCM", "cô-vy" == "côvy" — tức là nó khớp DỄ hơn hẳn.
        Ta đang nới lỏng phép khớp bằng dò lùi 6 vị trí; nới thêm knob thứ
        hai cùng lúc, mà không có dữ liệu hiệu chỉnh nào, là cộng dồn rủi ro
        xoá nhầm theo hướng không đo được. Cái giá phải trả của lựa chọn này
        là ngoặc kép/gạch ngang ở mối nối không được bỏ qua, nên vài seam
        vẫn lọt — đúng hướng sai an toàn (xem dưới).

        GIỚI HẠN: khớp theo từ nguyên văn không bắt được trường hợp hai lượt
        bóc băng của CÙNG một đoạn audio chồng lấn ra hai chuỗi từ khác nhau
        quá mức viết hoa/dấu câu — ví dụ ASR chọn từ khác, số viết bằng chữ
        số ở lượt này và bằng chữ ở lượt kia, hoặc câu bị diễn đạt lại do
        cửa sổ ngữ cảnh khác nhau. Khi đó phần chồng lấn không bị xoá và
        transcript sẽ lặp chữ ở mối nối — đây là đánh đổi CÓ CHỦ Ý (khớp mờ/
        fuzzy sẽ là làm quá tay cho bài toán này), không phải lỗi cần sửa
        khi gặp trong dữ liệu thật.

        `MAX_OVERLAP_WORDS = 12` và `MAX_OVERLAP_BACKSEARCH = 6` đều là con
        số ước lượng theo giả định (chồng lấn 1.5 giây), CHƯA được hiệu
        chỉnh trên đầu ra ASR thật — theo quy ước của dự án, ngưỡng chưa
        hiệu chỉnh phải được nêu rõ như thế này.
        """
        prev_words = previous.split()
        cur_words = current.split()
        if not prev_words or not cur_words:
            return current
        norm_prev = [w.lower().strip('.,;:!?') for w in prev_words]
        norm_cur = [w.lower().strip('.,;:!?') for w in cur_words]
        limit = min(MAX_OVERLAP_WORDS, len(norm_prev), len(norm_cur))
        # Yêu cầu khớp TỐI THIỂU 2 từ mới xoá (vòng lặp dừng ở size = 2).
        # Hai hướng sai không cân nhau: xoá thiếu để lại một từ lặp mà người
        # đọc NHÌN THẤY và tự sửa được; xoá thừa làm mất nội dung ÂM THẦM,
        # không dấu vết, trong một biên bản chính thức — với văn bản tiếng
        # Việt, các từ đệm/xác nhận ngắn như "vâng", "rồi", "được", "vậy",
        # "dạ" thường xuyên vừa kết thúc câu này vừa mở đầu câu sau, nên
        # khớp 1 từ là trùng hợp phổ biến chứ không phải bằng chứng chắc
        # chắn về seam. Vì vậy thiên về giữ lại từ lặp (an toàn hơn) thay vì
        # xoá nhầm. Sàn 2 từ này càng QUAN TRỌNG hơn sau khi thêm dò lùi:
        # cửa sổ tìm kiếm rộng ra 6 lần thì xác suất khớp trùng hợp cũng
        # tăng theo, và sàn 2 từ là thứ duy nhất chặn nó lại.
        for size in range(limit, 1, -1):
            target = norm_cur[:size]
            # Dài trước, rồi trong cùng độ dài thì ưu tiên vị trí PHẢI NHẤT
            # (sát đuôi `previous` nhất) — vị trí sát đuôi là seam thật, các
            # vị trí lùi chỉ là phương án dự phòng khi đuôi có từ thừa.
            first = len(norm_prev) - size
            for offset in range(first, max(-1, first - MAX_OVERLAP_BACKSEARCH), -1):
                if offset >= 0 and norm_prev[offset:offset + size] == target:
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
