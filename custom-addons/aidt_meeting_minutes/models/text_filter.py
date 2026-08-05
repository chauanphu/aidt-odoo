import logging
import re

from odoo import api, models

_logger = logging.getLogger(__name__)

# Whisper "ảo giác" (hallucinate) khi audio gần như không có tiếng nói: thay
# vì trả rỗng, nó sinh ra một câu trơn tru mà KHÔNG AI NÓI. Vì model được
# huấn luyện trên phụ đề YouTube, những câu đó lặp đi lặp lại đúng một nhóm
# khuôn mẫu — lời chào kênh, lời cảm ơn cuối video, dòng bản quyền.
#
# Danh sách dưới đây lấy từ `HALLUCINATION_PATTERNS` của dự án tham chiếu
# `~/projects/STT_T-m-T-t-AI` (`src-python/stt.py:26-51`), nơi nó đã chạy
# thật trên tiếng Việt. Giữ gần như nguyên văn có chủ ý: đây là dữ liệu quan
# sát được từ đầu ra thật của model, không phải thứ nên "cải tiến" bằng suy
# đoán. Muốn thêm mẫu thì thêm khi BẮT ĐƯỢC nó trong bản bóc băng thật, kèm
# ngày và ngữ cảnh.
#
# MỘT SỬA ĐỔI DUY NHẤT so với bản gốc, BẮT BUỘC phải có: bốn mẫu dùng `.*`
# không chặn đã được đổi thành `.{0,N}`. Bên kia xoá cả đoạn ngay khi có mẫu
# khớp nên `.*` dài hay ngắn không đổi kết quả; còn ở đây quyết định dựa vào
# TỈ LỆ ký tự bị khớp (xem `HALLUCINATION_COVERAGE`), nên một `.*` tham lam
# tự nó thổi tỉ lệ lên gần 1.0 và biến câu nói thật thành ảo giác. Ca thật
# gặp phải: "Hẹn gặp lại các đồng chí vào tuần sau, chúng ta sẽ xem lại
# video hướng dẫn" — `hẹn gặp lại.*video` nuốt trọn 84% câu và xoá mất một
# câu hoàn toàn bình thường trong biên bản. Ảo giác thật thì luôn ngắn
# ("hẹn gặp lại ở video sau"), nên chặn khoảng cách vừa giữ được mẫu vừa
# chặn được ca trên.
HALLUCINATION_PATTERNS = (
    r'hãy subscribe cho kênh',
    r'ghiền mì gõ',
    # `nh[uưữ]ng` chứ KHÔNG phải `nh[uư]ng` như bản gốc. Lớp ký tự của họ
    # KHÔNG khớp được `những` — `ữ` là một ký tự Unicode riêng, không phải
    # `ư`. Mà `những` đúng là thứ model sinh ra thật: đo ngày 05/08/2026,
    # whisper-large-v3 trên 15 giây IM LẶNG TUYỆT ĐỐI trả về "Hãy subscribe
    # cho kênh La La School Để không bỏ lỡ những video hấp dẫn". Mẫu gốc
    # trượt đúng nửa sau câu đó, kéo tỉ lệ khớp xuống 0.31 và làm cả câu ảo
    # giác lọt lưới.
    r'để không bỏ lỡ nh[uưữ]ng video hấp dẫn',
    r'đừng quên like và subscribe',
    r'nhấn nút đăng ký',
    r'cảm ơn các bạn đã theo dõi',
    r'hãy đăng ký kênh',
    r'xin chào các bạn.{0,20}kênh',
    r'hẹn gặp lại.{0,20}video',
    r'like.{0,20}share.{0,20}subscribe',
    r'thank you for watching',
    r'please subscribe',
    r'like and subscribe',
    r"don'?t forget to subscribe",
    r'hit the bell',
    r'©.{0,40}all rights reserved',
    r'subtitles? by',
    r'www\.\w+\.\w+',
    r'^meeting\.?$',
    r'^meeting discussion\.?$',
    r'^cuộc họp công việc\.?$',
    # `^\.+$` và `^,+$` của bản gốc đã BỎ ĐI, không phải quên: chuỗi chỉ có
    # dấu câu bị `_has_no_word_char` chặn trước khi tới đây, nên giữ lại chỉ
    # là hai mẫu chết mà người đọc sau này phải mất công xác minh.
)

_COMPILED = tuple(re.compile(p, re.IGNORECASE) for p in HALLUCINATION_PATTERNS)

# Tỉ lệ ký tự bị khớp trên tổng độ dài, tính từ HỢP của mọi vùng khớp, mà
# vượt qua thì coi cả đoạn là ảo giác.
#
# ĐÂY LÀ CHỖ TA CỐ Ý LÀM KHÁC dự án tham chiếu, không phải bỏ sót. Bên đó
# dùng `re.search` rồi xoá TOÀN BỘ văn bản nếu bất kỳ mẫu nào khớp ở BẤT KỲ
# đâu (`stt.py:1398`). Với một ứng dụng phụ đề tiêu dùng thì hợp lý; với một
# lát 15 giây của biên bản họp hành chính thì quá tàn phá — một người nói
# thật câu "cảm ơn các bạn đã theo dõi" ở cuối phần trình bày sẽ âm thầm xoá
# 15 giây biên bản, và không để lại dấu vết nào cho người đọc biết.
#
# Ảo giác thật gần như luôn CHIẾM TRỌN đầu ra (model không có gì để bám nên
# nó chỉ sinh ra đúng câu khuôn mẫu đó), còn câu nói thật trùng khuôn mẫu thì
# nằm lọt giữa nội dung khác. Tỉ lệ phân biệt được hai ca đó.
#
# 0.4 ĐÃ được hiệu chỉnh trên đầu ra THẬT của `openai/whisper-large-v3`,
# không phải số ước lượng. Đo ngày 05/08/2026 bằng cách gửi thẳng audio tổng
# hợp vào chính service `aidt-asr` đang chạy:
#
#   ẢO GIÁC THẬT (phải bỏ)
#     0.80  "Hãy subscribe cho kênh La La School Để không bỏ lỡ những
#            video hấp dẫn"            <- từ 15 giây IM LẶNG TUYỆT ĐỐI
#     0.62  "Cảm ơn các bạn đã theo dõi và hẹn gặp lại."
#                                      <- từ nhiễu nền RMS 0.001 và 0.006
#   CÂU NÓI THẬT (phải giữ)
#     0.16  "…tôi xin cảm ơn các bạn đã theo dõi và mong nhận được ý kiến…"
#     0.00  "Hẹn gặp lại các đồng chí vào tuần sau, chúng ta sẽ xem lại
#            video hướng dẫn."
#
# Ngưỡng nằm ở đâu trong khoảng (0.16, 0.62) cũng phân tách đúng bốn ca này;
# chọn 0.4 để chừa biên hai phía thay vì bám sát một mép. Tập mẫu vẫn NHỎ —
# bốn ca — nên đây là hiệu chỉnh sơ bộ, không phải số chốt.
HALLUCINATION_COVERAGE = 0.4

# CỐ Ý KHÔNG PORT luật `len(text) <= 3` của dự án tham chiếu
# (`stt.py:1404`). Bên đó làm phụ đề tiêu dùng nên vứt một đoạn ba ký tự là
# vô hại. Ở biên bản họp tiếng Việt thì KHÔNG: những lượt nói ngắn nhất lại
# thường là lượt mang tính pháp lý nhất — "Dạ" (2), "Ừ" (1), "OK" (2) là
# tiếng đồng ý của người chủ trì, và luật đó xoá sạch chúng mà không để lại
# dấu vết nào. Đúng loại mất mát âm thầm mà cả module này được viết ra để
# tránh.
#
# Thứ luật kia thật sự bắt được — chuỗi chỉ có dấu câu ("...", ",,,") — đã
# có `^\.+$` và `^,+$` lo, và luật dưới đây phủ tổng quát hơn mà không đụng
# tới chữ. Điều kiện: KHÔNG có lấy một ký tự chữ hoặc số nào.
def _has_no_word_char(text):
    return not any(ch.isalnum() for ch in text)


class AidtMeetingTextFilter(models.AbstractModel):
    _name = 'aidt.meeting.text.filter'
    _description = 'Lọc ảo giác khỏi đầu ra bóc băng'

    @api.model
    def _coverage(self, text, matches):
        """Tỉ lệ ký tự bị khớp, tính trên HỢP các vùng khớp.

        Phải hợp nhất chứ không cộng dồn độ dài từng vùng: một ảo giác nhiều
        câu ("Cảm ơn các bạn đã theo dõi. Hẹn gặp lại ở video sau.") khớp
        NHIỀU mẫu cùng lúc, và các vùng đó có thể chồng lên nhau. Cộng dồn sẽ
        cho tỉ lệ vượt 1.0 — vô nghĩa; mà xét từng vùng riêng lẻ thì mỗi vùng
        chỉ chiếm ~0.5 nên không vùng nào một mình vượt ngưỡng, và đúng ca ảo
        giác điển hình nhất lại lọt lưới.
        """
        if not text:
            return 0.0
        covered = set()
        for match in matches:
            covered.update(range(*match.span()))
        return len(covered) / len(text)

    @api.model
    def _filter(self, text):
        """text -> (text_giữ_lại, lý_do_bỏ | None).

        Trả `('', lý do)` khi bỏ cả đoạn. Bên gọi PHẢI ghi lại lý do đó chứ
        không được lặng lẽ vứt đi: trong một biên bản chính thức, nội dung
        biến mất không dấu vết còn tệ hơn nội dung sai nhìn thấy được — người
        đọc sửa được cái thứ hai, không sửa được cái thứ nhất. Cùng nguyên
        tắc đã ghi ở `transcript_builder._strip_overlap`.
        """
        stripped = (text or '').strip()
        if not stripped:
            return '', None
        if _has_no_word_char(stripped):
            return '', f'đoạn không có chữ nào: {stripped!r}'

        matches = [m for m in (rx.search(stripped) for rx in _COMPILED) if m]
        if not matches:
            return stripped, None

        coverage = self._coverage(stripped, matches)
        if coverage < HALLUCINATION_COVERAGE:
            # Khớp mẫu nhưng chỉ chiếm một phần nhỏ ⇒ nhiều khả năng là câu
            # nói thật trùng khuôn mẫu. Giữ lại, nhưng ghi log để còn hiệu
            # chỉnh `HALLUCINATION_COVERAGE` bằng dữ liệu thật về sau.
            _logger.info(
                'Giữ đoạn khớp mẫu ảo giác vì chỉ chiếm %.0f%% (<%.0f%%): %r',
                coverage * 100, HALLUCINATION_COVERAGE * 100, stripped)
            return stripped, None

        return '', (f'ảo giác ({coverage * 100:.0f}% khớp mẫu '
                    f'{matches[0].re.pattern!r}): {stripped!r}')

    @api.model
    def _filter_segments(self, parsed):
        """Lọc danh sách đoạn của `asr_client._transcribe`.

        Trả `(đoạn_giữ_lại, [lý do…])`.
        """
        kept, notes = [], []
        for item in parsed:
            text, note = self._filter(item.get('text', ''))
            if note:
                notes.append(note)
            if text:
                kept.append(dict(item, text=text))
        return kept, notes
