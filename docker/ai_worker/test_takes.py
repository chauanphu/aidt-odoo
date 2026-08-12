"""Ghép audio theo (người, take). Chạy dưới pytest của ảnh dev Odoo."""

import json

import main


def write_meta(tmp_path, meta):
    (tmp_path / "metadata.json").write_text(json.dumps(meta, ensure_ascii=False))


class TestLoadStreams:
    def test_moi_take_la_mot_luong_rieng(self, tmp_path):
        """Nối byte xuyên qua ranh giới tạm dừng cho ra tệp có EBML header
        nằm giữa: ffmpeg giải mã phần đầu rồi dừng, im lặng mất phần sau."""
        write_meta(tmp_path, {"speakers": [{
            "partner_id": 3, "speaker_name": "A", "takes": [
                {"take": 0, "offset_ms": 0, "files": ["spk3_t0_00000.webm"]},
                {"take": 1, "offset_ms": 90000, "files": ["spk3_t1_00000.webm"]},
            ]}], "pauses": []})

        streams = main._load_streams(tmp_path, 0)

        assert len(streams) == 2
        assert [s["take"] for s in streams] == [0, 1]
        assert streams[0]["files"] == ["spk3_t0_00000.webm"]
        assert streams[1]["offset_ms"] == 90000
        assert streams[0]["name"] == "A"

    def test_cat_tai_moc_tam_dung(self, tmp_path):
        """Mẩu đang bay lúc bấm tạm dừng vẫn được nhận ở server (nếu chặn thì
        mất tới 30 giây lời nói trước mỗi lần dừng), nên ranh giới phải được
        bảo đảm ở đây."""
        write_meta(tmp_path, {"speakers": [{
            "partner_id": 3, "speaker_name": "A", "takes": [
                {"take": 0, "offset_ms": 0, "files": ["a.webm"]},
                {"take": 1, "offset_ms": 90000, "files": ["b.webm"]},
            ]}], "pauses": [{"paused_at_ms": 60000, "resumed_at_ms": 90000}]})

        streams = main._load_streams(tmp_path, 0)

        assert streams[0]["max_duration_ms"] == 60000
        assert streams[1]["max_duration_ms"] is None

    def test_doc_duoc_khuon_dang_cu(self, tmp_path):
        """Job đã nằm sẵn trên đĩa từ bản trước phải chạy lại được."""
        write_meta(tmp_path, {"speakers": [
            {"partner_id": 3, "speaker_name": "A", "offset_ms": 34,
             "files": ["spk3_00000.webm", "spk3_00001.webm"]}]})

        streams = main._load_streams(tmp_path, 0)

        assert len(streams) == 1
        assert streams[0]["take"] == 0
        assert streams[0]["offset_ms"] == 34
        assert streams[0]["max_duration_ms"] is None

    def test_khong_co_metadata_thi_coi_la_mot_luong(self, tmp_path):
        streams = main._load_streams(tmp_path, 2)
        assert len(streams) == 1
        assert streams[0]["files"] == ["chunk_0.webm", "chunk_1.webm"]

    def test_khoang_dung_con_mo_khong_lam_sai_moc_cat(self, tmp_path):
        """resumed_at_ms: null nghĩa là khoảng dừng CÒN MỞ (dừng tới hết cuộc
        họp) — Task 9 vừa vá bẫy đọc null thành 0. `_pause_bound_for` không
        được đọc `resumed_at_ms`, chỉ `paused_at_ms` mới quyết định mốc cắt;
        khoá lại để không ai "cải tiến" bằng cách đọc `resumed_at_ms` rồi tái
        sinh đúng bẫy đó."""
        write_meta(tmp_path, {"speakers": [{
            "partner_id": 3, "speaker_name": "A", "takes": [
                {"take": 0, "offset_ms": 0, "files": ["a.webm"]},
            ]}], "pauses": [{"paused_at_ms": 60000, "resumed_at_ms": None}]})

        streams = main._load_streams(tmp_path, 0)

        assert streams[0]["max_duration_ms"] == 60000


class TestAssembleFallbackBudget:
    def test_luot_du_phong_cong_don_ngan_sach(self, tmp_path, monkeypatch):
        """Lượt dự phòng (giải mã từng mẩu con khi luồng nối byte hỏng) phải
        cộng dồn thời lượng đã dùng qua các mẩu, cắt mẩu đang xét theo phần
        ngân sách CÒN LẠI, và dừng hẳn khi ngân sách cạn. Áp `max_duration_ms`
        cho từng mẩu độc lập (không cộng dồn) để lọt audio sau tạm dừng vào
        biên bản khi một take có nhiều mẩu con ngắn — đúng thứ tính năng này
        phải chặn."""
        calls = []

        def fake_decode(src, dst, audio_filter, max_duration_ms=None):
            if src.name.startswith("stream_"):
                return False  # buộc rơi vào lượt dự phòng
            calls.append(max_duration_ms)
            dst.write_bytes(b"x")
            return True

        monkeypatch.setattr(main, "decode_to_wav", fake_decode)
        monkeypatch.setattr(main, "probe_duration_ms", lambda path: 40000)
        # >=2 mẩu giải mã được thì hàm còn nối các WAV bằng `ffmpeg -f
        # concat` — không liên quan tới điều đang kiểm, và ffmpeg không có
        # trong ảnh pytest, nên chặn ở đây.
        monkeypatch.setattr(main, "_run", lambda cmd: type(
            "FakeResult", (), {"returncode": 1, "stderr": ""})())

        for name in ("a.webm", "b.webm", "c.webm"):
            (tmp_path / name).write_bytes(b"data")

        main.assemble_speaker_stream(
            tmp_path, "spk", ["a.webm", "b.webm", "c.webm"], "anull",
            max_duration_ms=60000)

        # Mẩu 1 nhận đủ ngân sách (60000). Mẩu 1 "dùng" 40000 -> còn 20000,
        # mẩu 2 chỉ được cấp 20000. Sau mẩu 2, ngân sách đã âm -> mẩu 3
        # không được giải mã nữa.
        assert calls == [60000, 20000]


def seg(text, abs_start_ms, speaker="A"):
    return {"text": text, "abs_start": abs_start_ms,
            "abs_end": abs_start_ms + 2000, "speaker": speaker}


class TestPauseMarker:
    def test_chen_moc_dung_vi_tri_thoi_gian(self):
        segments = [seg("Trước khi dừng", 308000), seg("Sau khi ghi tiếp", 521000)]
        pauses = [{"paused_at_ms": 312000, "resumed_at_ms": 520000}]

        lines = main.build_transcript_for_llm(segments, pauses).split("\n")

        assert lines[0].startswith("[05:08]")
        assert lines[1] == ("--- TẠM DỪNG GHI ÂM 05:12 → 08:40 "
                            "(3 phút 28 giây không được ghi) ---")
        assert lines[2].startswith("[08:41]")

    def test_doan_dung_khong_ghi_tiep_dat_o_cuoi(self):
        """Chủ phòng kết thúc trong lúc đang tạm dừng: ta biết lúc dừng,
        KHÔNG biết cuộc họp còn kéo dài bao lâu sau đó.

        `resumed_at_ms` phải là `None` (JSON `null`) — đúng giá trị mà
        đường xuất dữ liệu thật sinh ra cho một khoảng dừng còn mở (Task 9).
        `0` từng được dùng để biểu diễn điều này nhưng gây hiểu nhầm thành
        "ghi tiếp ngay tại mốc 0 ms" nên đã bị loại bỏ."""
        segments = [seg("Câu cuối", 300000)]
        pauses = [{"paused_at_ms": 312000, "resumed_at_ms": None}]

        lines = main.build_transcript_for_llm(segments, pauses).split("\n")

        assert lines[-1] == ("--- TẠM DỪNG GHI ÂM 05:12 — không ghi tiếp "
                             "cho tới hết cuộc họp ---")

    def test_khong_co_doan_dung_thi_khong_chen_gi(self):
        segments = [seg("Một câu", 1000), seg("Câu nữa", 3000)]
        assert "TẠM DỪNG" not in main.build_transcript_for_llm(segments, [])

    def test_prompt_he_thong_day_model_khong_suy_dien_qua_cho_dung(self):
        assert "TẠM DỪNG GHI ÂM" in main.SYSTEM_PROMPT
