"""Test lớp lọc hậu kiểm, dựng từ ĐÚNG dữ liệu đã quan sát được.

Chạy dưới pytest của ảnh dev Odoo (worker không có pytest):

    docker exec aidt-odoo-dev-odoo-1 bash -lc \\
      'cd /opt/odoo && PYTHONPATH=docker/ai_worker /opt/venv/bin/python3 \\
         -m pytest docker/ai_worker/test_filters.py -q'

`main.py` import được ngoài GPU vì `faster_whisper` nằm trong try/except.
"""

import main

# Nguyên văn `aidt_meeting.asr_prompt` đang cấu hình trên aidt_demo.
PROMPT = (
    "Đây là biên bản một cuộc họp hành chính. Chúng tôi trao đổi về việc "
    "ghi âm và bóc băng biên bản, phân quyền người dùng, độ mật của văn "
    "bản, cấu hình server và cơ sở dữ liệu, cùng con model AI chạy local "
    "trên hệ thống Odoo."
)

# Đoạn model nhả ra ở bản ghi 2858, luồng của Nguyễn Văn An: một segment
# DUY NHẤT trải 44 giây (0.4 -> 44.4), avg_logprob -0.06 — tức model rất
# "tự tin". Nó nuốt trọn 44 giây phát biểu thật và thay bằng chính prompt.
ECHO_2858 = (
    "Chúng tôi trao đổi về việc ghi âm và bóc băng biên bản, phân quyền "
    "người dùng, độ mật của văn bản, cấu hình server và cơ sở dữ liệu, "
    "cùng con model AI chạy local trên hệ thống Odoo."
)

# Bản ghi 2856: nói đúng một từ "alo" trong 9,5 giây; toàn bộ transcript là
# một biến thể rút gọn của prompt.
ECHO_2856 = (
    "Chúng tôi chạy local trên hệ thống Odoo, cùng con model AI chạy local "
    "trên hệ thống Odoo."
)


def seg(text, start, end, logprob=-0.3, no_speech=0.0):
    return {"text": text, "start": start, "end": end,
            "abs_start": int(start * 1000), "abs_end": int(end * 1000),
            "avg_logprob": logprob, "no_speech_prob": no_speech}


def texts(segments):
    return [s["text"] for s in segments]


class TestGiuLaiLoiNoiThat:
    """Từ đáp ngắn là lời nói THẬT và mang nghĩa trong biên bản.

    Luật `len(text) <= 3` cũ vứt sạch chúng: ở bản ghi 2858 nó loại 36
    segment và TẤT CẢ đều là "Ok" — trong đó có cả tiếng "Ok" thật dài 7
    giây mà người B dùng để đồng ý. Ở 2797 nó vứt "Hả?" và "Dạ dạ".
    Trong một biên bản hành chính, "Ok"/"Vâng"/"Dạ" chính là chỗ ghi nhận
    sự đồng thuận — mất chúng là mất quyết định.
    """

    def test_giu_tu_dap_ngan_co_do_dai_that(self):
        segments = [
            seg("Ok", 74.1, 81.1),          # 2858: 7 giây, tiếng đồng ý thật
            seg("Dạ", 6.6, 7.4),            # 2797
            seg("Hả?", 20.7, 21.3),         # 2797
        ]
        assert texts(main.filter_segments(segments)) == ["Ok", "Dạ", "Hả?"]


class TestVongLapGiaiMa:
    """Vòng lặp giải mã nhận ra bằng THỜI LƯỢNG, không phải độ dài chữ.

    Ở 2858, 36 segment "Ok" cuối luồng đều nằm trong khoảng 85.2 -> 86.0
    giây, mỗi segment dài ~0,0 giây. Đó là dấu hiệu model kẹt vòng lặp ở
    cuối tệp, hoàn toàn khác với một tiếng "Ok" thật dài 7 giây.
    """

    def test_bo_segment_do_dai_bang_khong(self):
        segments = [seg("Ok", 74.1, 81.1)]
        t = 85.2
        for _ in range(36):
            segments.append(seg("Ok", t, t + 0.02))
            t += 0.02

        kept = main.filter_segments(segments)
        assert texts(kept) == ["Ok"], (
            f"phải giữ đúng tiếng Ok thật, nhận được {texts(kept)}")

    def test_bo_cac_segment_lap_lai_lien_tiep(self):
        """Cùng một câu lặp lại liên tiếp = vòng lặp, kể cả khi mỗi segment
        có thời lượng hợp lệ."""
        segments = [
            seg("Cảm ơn mọi người", 10.0, 12.0),
            seg("Cảm ơn mọi người", 12.0, 14.0),
            seg("Cảm ơn mọi người", 14.0, 16.0),
            seg("Chúng ta bắt đầu nhé", 16.0, 18.0),
        ]
        assert texts(main.filter_segments(segments)) == [
            "Cảm ơn mọi người", "Chúng ta bắt đầu nhé"]


class TestNhaNguocPrompt:
    """Lưới chắn cuối cho `initial_prompt`.

    Mặc định nay là KHÔNG prompt (xem TestPromptMacDinh), nhưng quản trị
    viên vẫn bật lại được từ trang Cấu hình. Khi đó phải chặn được đúng thứ
    đã đo ở 2856 và 2858: model đọc tiếp prompt thay vì bóc băng.
    """

    def test_bo_doan_trung_voi_prompt(self):
        segments = [seg(ECHO_2858, 0.4, 44.4, logprob=-0.06)]
        assert main.filter_segments(segments, prompt=PROMPT) == []

    def test_bo_ca_ban_rut_gon_cua_prompt(self):
        segments = [seg(ECHO_2856, 0.0, 5.4, logprob=-0.10)]
        assert main.filter_segments(segments, prompt=PROMPT) == []

    def test_khong_dung_cham_loi_noi_that(self):
        """Prompt nhắc tới "cuộc họp", "hệ thống", "cấu hình" — những từ
        người ta nói thật trong cuộc họp. Lưới chắn phải bắt theo mức
        TRÙNG KHỚP CỤM, không phải theo từ đơn lẻ, nếu không nó ăn luôn
        nội dung thật."""
        that = [
            seg("Mình nghĩ cần tối ưu lại một số câu truy vấn database "
                "và có thể bổ sung cơ chế caching", 31.1, 35.5),
            seg("Cấu hình server hiện tại đã ổn định chưa anh", 40.0, 44.0),
            seg("Hiện còn chức năng thông báo và dashboard", 46.1, 52.8),
        ]
        assert len(main.filter_segments(that, prompt=PROMPT)) == 3

    def test_khong_co_prompt_thi_khong_loc_gi_them(self):
        segments = [seg(ECHO_2858, 0.4, 44.4, logprob=-0.06)]
        assert len(main.filter_segments(segments, prompt="")) == 1


class TestPromptMacDinh:
    """Đo được, không phải phỏng đoán (10/08/2026).

    Chạy CÙNG một luồng audio, chỉ đổi `initial_prompt`:
      * 2858 luồng Nguyễn Văn An — CÓ prompt: một segment 0.4->44.4 chứa
        nguyên văn prompt, mất trắng 44 giây phát biểu. KHÔNG prompt: đúng
        44 giây đó ra 8 câu thật ("hoàn thành khoảng 70%", "API đôi khi
        phản hồi khá chậm", "bổ sung cơ chế caching"...).
      * 2797 luồng Administrator — CÓ prompt 51 segment, KHÔNG prompt 53
        segment; "PDF", "OCR", "tàu trình" GIỐNG HỆT nhau ở cả hai. Tức
        phần "mồi vốn từ" không đem lại lợi ích đo được nào.
    Lợi ích 0, thiệt hại mất nửa phần phát biểu của một người.
    """

    def test_worker_khong_tu_dat_prompt_mac_dinh(self):
        assert main.DEFAULT_ASR_PROMPT == ""


class TestNguongLoc:
    def test_gom_doan_lap_tu_trong_mot_cau_ve_mot_lan(self):
        """Lặp TRONG LÒNG một segment thì GOM LẠI, không vứt cả segment.

        `clean_text` đã gom "dạ dạ dạ…" về "dạ" từ trước. Vứt cả segment —
        như luật `len <= 3` cũ vẫn làm — nghĩa là mất luôn tiếng đáp thật
        mà người ta có nói, chỉ vì model lặp lại nó. Giữ một lần là khôi
        phục đúng thứ đã xảy ra.
        """
        segments = [seg("dạ dạ dạ dạ dạ dạ dạ dạ dạ dạ", 5.0, 9.0)]
        assert texts(main.filter_segments(segments)) == ["dạ"]


    def test_van_bo_doan_do_tu_tin_thap(self):
        segments = [seg("nghe không rõ gì cả", 5.0, 9.0, logprob=-1.5)]
        assert main.filter_segments(segments) == []

    def test_van_bo_blacklist_youtube(self):
        segments = [seg("Cảm ơn các bạn đã theo dõi", 5.0, 9.0)]
        assert main.filter_segments(segments) == []
