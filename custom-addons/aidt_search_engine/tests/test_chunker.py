import unittest

from aidt_search_engine.chunker import (
    STANDALONE_ZONES,
    chunk_blocks,
    detect_heading,
    is_soft_boundary,
    split_long_text,
)
from aidt_search_engine.types import Block, DocMeta

META = DocMeta(doc_type_label="Kế hoạch", reference="145/KH-UBND", title="An toàn thông tin")


class TestDetectHeading(unittest.TestCase):
    def test_phan_la_bac_1(self):
        self.assertEqual(detect_heading("PHẦN II. MỤC TIÊU"), (1, "PHẦN II"))

    def test_chuong_la_bac_2(self):
        self.assertEqual(detect_heading("Chương IV"), (2, "Chương IV"))

    def test_muc_la_bac_3(self):
        self.assertEqual(detect_heading("Mục 3. Tổ chức thực hiện"), (3, "Mục 3"))

    def test_dieu_la_bac_4(self):
        self.assertEqual(detect_heading("Điều 7. Trách nhiệm"), (4, "Điều 7"))

    def test_doan_thuong_khong_phai_tieu_de(self):
        self.assertIsNone(detect_heading("Các sở, ban, ngành có trách nhiệm"))

    def test_khong_bat_nham_giua_cau(self):
        # 'Điều' xuất hiện giữa câu không phải tiêu đề.
        self.assertIsNone(detect_heading("Căn cứ Điều 7 của Luật nêu trên"))


class TestIsSoftBoundary(unittest.TestCase):
    def test_so_thu_tu(self):
        self.assertTrue(is_soft_boundary("1. Mục tiêu chung"))

    def test_chu_cai_ngoac(self):
        self.assertTrue(is_soft_boundary("a) Bố trí kinh phí"))

    def test_doan_thuong(self):
        self.assertFalse(is_soft_boundary("Các sở, ban, ngành"))


class TestSplitLongText(unittest.TestCase):
    def test_ngan_hon_nguong_thi_khong_cat(self):
        self.assertEqual(split_long_text("Một câu ngắn.", 400), ["Một câu ngắn."])

    def test_dai_hon_nguong_thi_cat_theo_cau(self):
        text = " ".join(f"Câu số {i} dài vừa đủ để cộng dồn." for i in range(60))
        pieces = split_long_text(text, 50)
        self.assertGreater(len(pieces), 1)
        # Không mảnh nào được vượt xa ngưỡng.
        for p in pieces:
            self.assertLess(len(p) // 3, 50 * 2)

    def test_mot_cau_dai_hon_nguong_van_thanh_mot_manh(self):
        # Không được rơi vào vòng lặp vô hạn hay cắt giữa từ.
        long_sentence = "x" * 5000
        self.assertEqual(split_long_text(long_sentence, 50), [long_sentence])

    def test_chuoi_rong(self):
        self.assertEqual(split_long_text("", 400), [])


class TestChunkBlocks(unittest.TestCase):
    def test_tai_lieu_rong(self):
        self.assertEqual(chunk_blocks([], META), [])

    def test_bo_qua_doan_toan_khoang_trang(self):
        self.assertEqual(chunk_blocks([Block(text="   "), Block(text="\n")], META), [])

    def test_doi_zone_thi_cat(self):
        blocks = [
            Block(text="Về việc phối hợp công tác", zone="trich_yeu"),
            Block(text="Kính gửi các đơn vị.", zone="noi_dung"),
        ]
        chunks = chunk_blocks(blocks, META)
        self.assertEqual(len(chunks), 2)
        self.assertEqual(chunks[0].zone, "trich_yeu")
        self.assertEqual(chunks[1].zone, "noi_dung")

    def test_bon_vung_dac_biet_luon_dung_rieng(self):
        for zone in STANDALONE_ZONES:
            blocks = [
                Block(text="Đoạn nội dung một.", zone="noi_dung"),
                Block(text="Giá trị vùng đặc biệt.", zone=zone),
                Block(text="Đoạn nội dung hai.", zone="noi_dung"),
            ]
            chunks = chunk_blocks(blocks, META)
            self.assertEqual(len(chunks), 3, f"vùng {zone} bị gộp")
            self.assertEqual(chunks[1].zone, zone)

    def test_heading_path_long_nhau_dung_thu_tu(self):
        blocks = [
            Block(text="PHẦN II. MỤC TIÊU", zone="noi_dung"),
            Block(text="Mục 3. Tổ chức thực hiện", zone="noi_dung"),
            Block(text="Các sở, ban, ngành có trách nhiệm.", zone="noi_dung"),
        ]
        chunks = chunk_blocks(blocks, META)
        self.assertEqual(chunks[-1].heading_path, "PHẦN II › Mục 3")

    def test_heading_bac_nong_hon_cat_nhanh_sau(self):
        blocks = [
            Block(text="PHẦN II", zone="noi_dung"),
            Block(text="Mục 3", zone="noi_dung"),
            Block(text="PHẦN III", zone="noi_dung"),
            Block(text="Nội dung phần ba.", zone="noi_dung"),
        ]
        chunks = chunk_blocks(blocks, META)
        # 'Mục 3' của PHẦN II không được dính sang PHẦN III.
        self.assertEqual(chunks[-1].heading_path, "PHẦN III")

    def test_dieu_dai_bi_cat_thanh_nhieu_chunk(self):
        long_text = " ".join(f"Nội dung câu thứ {i} của điều này." for i in range(200))
        blocks = [
            Block(text="Điều 7. Trách nhiệm", zone="noi_dung"),
            Block(text=long_text, zone="noi_dung"),
        ]
        chunks = chunk_blocks(blocks, META, target_tokens=100)
        self.assertGreater(len(chunks), 1)
        # Mọi mảnh đều giữ nguyên heading_path của Điều 7.
        for c in chunks:
            self.assertEqual(c.heading_path, "Điều 7")

    def test_dieu_ngan_duoc_gop(self):
        blocks = [
            Block(text="Điều 1. Phạm vi", zone="noi_dung"),
            Block(text="Quy định này áp dụng cho toàn tỉnh.", zone="noi_dung"),
        ]
        self.assertEqual(len(chunk_blocks(blocks, META)), 1)

    def test_danh_sach_gach_dau_dong_khong_bi_bam_vun(self):
        # Ranh giới mềm: 6 gạch đầu dòng ngắn phải nằm chung một chunk.
        blocks = [Block(text=f"{i}. Nhiệm vụ ngắn thứ {i}.", zone="noi_dung")
                  for i in range(1, 7)]
        self.assertEqual(len(chunk_blocks(blocks, META)), 1)

    def test_seq_lien_tuc_tu_khong(self):
        blocks = [Block(text=f"Đoạn {i} nội dung.", zone="noi_dung") for i in range(5)]
        chunks = chunk_blocks(blocks, META, target_tokens=5)
        self.assertEqual([c.seq for c in chunks], list(range(len(chunks))))

    def test_embed_text_co_header_con_text_thi_khong(self):
        blocks = [Block(text="Điều 7. Trách nhiệm", zone="noi_dung")]
        c = chunk_blocks(blocks, META)[0]
        self.assertIn("145/KH-UBND", c.embed_text)
        self.assertNotIn("145/KH-UBND", c.text)

    def test_giu_page_va_bbox_cua_khoi_dau(self):
        blocks = [Block(text="Đoạn có toạ độ.", zone="noi_dung", page=3, bbox=(1, 2, 3, 4))]
        c = chunk_blocks(blocks, META)[0]
        self.assertEqual((c.page, c.bbox), (3, (1, 2, 3, 4)))


if __name__ == "__main__":
    unittest.main()
