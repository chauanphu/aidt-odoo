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
