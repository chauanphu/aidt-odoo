import datetime as dt
import unicodedata
import unittest

from aidt_search_engine.intent import parse_query
from aidt_search_engine.text import strip_accents

DOC_TYPES = [("cong_van", "Công văn"), ("ke_hoach", "Kế hoạch"),
             ("quyet_dinh", "Quyết định"), ("bao_cao", "Báo cáo")]
DEPARTMENTS = [(7, "Sở Tài chính"), (9, "Sở Thông tin và Truyền thông"),
               (3, "Văn phòng")]
URGENCIES = [("hoa_toc", "Hỏa tốc"), ("thuong_khan", "Thượng khẩn"),
             ("khan", "Khẩn")]


def parse(raw):
    return parse_query(raw, DOC_TYPES, DEPARTMENTS, URGENCIES)


class TestReference(unittest.TestCase):
    def test_bat_so_hieu_day_du(self):
        self.assertEqual(parse("145/KH-UBND").reference, "145/KH-UBND")

    def test_bat_so_hieu_trong_cau(self):
        self.assertEqual(parse("cho tôi xem Số 185/CV-STTTT").reference, "185/CV-STTTT")

    def test_bat_so_hieu_nhieu_doan(self):
        self.assertEqual(parse("nghị quyết 12/NQ-TW-BCT").reference, "12/NQ-TW-BCT")

    def test_khong_co_so_hieu(self):
        self.assertIsNone(parse("các văn bản về hỗ trợ hộ nghèo").reference)

    def test_khong_bat_nham_ngay_thang(self):
        self.assertIsNone(parse("văn bản ngày 25/7/2026").reference)


class TestDateFilter(unittest.TestCase):
    def _date_filter(self, raw):
        return next((f for f in parse(raw).filters if f.field == "date"), None)

    def test_nam(self):
        f = self._date_filter("văn bản về hộ nghèo năm 2025")
        self.assertEqual(f.value, (dt.date(2025, 1, 1), dt.date(2025, 12, 31)))
        self.assertEqual(f.label, "Năm 2025")

    def test_quy(self):
        f = self._date_filter("báo cáo quý II năm 2026")
        self.assertEqual(f.value, (dt.date(2026, 4, 1), dt.date(2026, 6, 30)))

    def test_quy_cach_xa_nam_giu_nguyen_van_ban_o_giua(self):
        # 'quý II' và 'năm 2026' không liền nhau — nội dung ngữ nghĩa nằm
        # giữa hai mốc này không được bị bóc theo (không bắc cầu span).
        q = parse("kế hoạch quý II về hỗ trợ hộ nghèo năm 2026")
        f = next(f for f in q.filters if f.field == "date")
        self.assertEqual(f.value, (dt.date(2026, 4, 1), dt.date(2026, 6, 30)))
        self.assertIn("hỗ trợ hộ nghèo", q.semantic)
        self.assertNotIn("2026", q.semantic)

    def test_thang_co_nam(self):
        f = self._date_filter("công văn tháng 3/2026")
        self.assertEqual(f.value, (dt.date(2026, 3, 1), dt.date(2026, 3, 31)))

    def test_thang_12_tinh_dung_ngay_cuoi(self):
        f = self._date_filter("báo cáo tháng 12/2025")
        self.assertEqual(f.value, (dt.date(2025, 12, 1), dt.date(2025, 12, 31)))

    def test_khong_co_moc_thoi_gian(self):
        self.assertIsNone(self._date_filter("hỗ trợ hộ nghèo"))


class TestOtherFilters(unittest.TestCase):
    def _field(self, raw, field):
        return next((f for f in parse(raw).filters if f.field == field), None)

    def test_loai_van_ban(self):
        self.assertEqual(self._field("kế hoạch về an toàn thông tin", "doc_type").value,
                         "ke_hoach")

    def test_don_vi_khop_ten_dai_nhat(self):
        # 'Sở Thông tin và Truyền thông' phải thắng, không được khớp 'Sở Tài chính'
        # hay dừng ở một tiền tố ngắn hơn.
        f = self._field("công văn của Sở Thông tin và Truyền thông", "department_id")
        self.assertEqual(f.value, 9)

    def test_don_vi_khop_khong_dau(self):
        self.assertEqual(self._field("van ban cua So Tai chinh", "department_id").value, 7)

    def test_do_khan_uu_tien_cum_dai(self):
        self.assertEqual(self._field("văn bản thượng khẩn", "do_khan").value, "thuong_khan")

    def test_do_khan_don(self):
        self.assertEqual(self._field("công văn khẩn", "do_khan").value, "khan")

    def test_don_vi_giua_quy_va_nam_khong_cat_giua_tu(self):
        # Span 'quý II' và span 'năm 2026' rời nhau, nhưng span đơn vị nằm
        # LỒNG GIỮA hai mốc đó — vòng lặp xoá text phải gộp span chồng lấn
        # trước khi xoá, nếu không sẽ lệch offset và cắt nham nhở giữa từ.
        q = parse("báo cáo quý II của Sở Tài chính năm 2026")
        self.assertEqual(self._field("báo cáo quý II của Sở Tài chính năm 2026",
                                      "department_id").value, 7)
        self.assertEqual(q.semantic, "của")

    def test_khan_cap_khong_bi_hieu_nham_la_nhan_do_khan(self):
        # 'khẩn cấp' là tính từ thường ('urgent/emergency'), không phải nhãn
        # độ khẩn 'Khẩn' — dù khớp đúng ranh giới từ, đây vẫn là khớp sai nghĩa.
        q = parse("công văn khẩn cấp về phòng chống bão")
        self.assertIsNone(self._field("công văn khẩn cấp về phòng chống bão", "do_khan"))
        self.assertIn("khẩn cấp", q.semantic)
        self.assertIn("phòng chống bão", q.semantic)


class TestSemanticRemainder(unittest.TestCase):
    def test_boc_filter_ra_khoi_chuoi_ngu_nghia(self):
        q = parse("các văn bản về hỗ trợ hộ nghèo năm 2025")
        self.assertNotIn("2025", q.semantic)
        self.assertIn("hỗ trợ hộ nghèo", q.semantic)

    def test_khong_boc_thi_giu_nguyen(self):
        q = parse("hỗ trợ hộ nghèo")
        self.assertEqual(q.semantic, "hỗ trợ hộ nghèo")
        self.assertEqual(q.filters, [])

    def test_raw_luon_duoc_giu(self):
        raw = "báo cáo quý II năm 2026 của Sở Tài chính"
        self.assertEqual(parse(raw).raw, raw)

    def test_truy_van_chi_co_so_hieu_thi_semantic_rong(self):
        self.assertEqual(parse("145/KH-UBND").semantic, "")

    def test_chuoi_rong(self):
        q = parse("")
        self.assertEqual((q.semantic, q.reference, q.filters), ("", None, []))


class TestNfdKhongLamLechSpan(unittest.TestCase):
    """I-6: offset tính trên chuỗi ĐÃ BỎ DẤU nhưng lại cắt trên `raw`.

    Chỉ đúng khi `strip_accents` giữ nguyên độ dài — đúng với NFC, SAI với NFD
    (dấu là code point rời hạng Mn, bỏ đi làm chuỗi ngắn lại). Trước khi sửa,
    dạng NFD của cùng một câu cho `semantic` bị cắt giữa từ và MẤT hẳn filter
    ngày tháng, mà không có lỗi nào hiện ra.
    """

    RAW = "Xin gửi báo cáo tổng kết công tác quý I năm 2025"

    def test_nfd_va_nfc_cho_ket_qua_giong_het(self):
        nfc = parse(unicodedata.normalize("NFC", self.RAW))
        nfd = parse(unicodedata.normalize("NFD", self.RAW))
        self.assertEqual(nfd.semantic, nfc.semantic)
        self.assertEqual(nfd.raw, nfc.raw)
        self.assertEqual(nfd.reference, nfc.reference)
        self.assertEqual([(f.field, f.value, f.span, f.hard) for f in nfd.filters],
                         [(f.field, f.value, f.span, f.hard) for f in nfc.filters])

    def test_nfd_khong_lam_mat_filter_ngay_thang(self):
        nfd = parse(unicodedata.normalize("NFD", self.RAW))
        self.assertIn("date", {f.field for f in nfd.filters})

    def test_nfd_khong_cat_giua_tu(self):
        # Trước khi sửa: 'Xin gử cáo tổng kết công tác quý I năm 2025'.
        self.assertNotIn("gử ", parse(unicodedata.normalize("NFD", self.RAW)).semantic)

    def test_strip_accents_giu_nguyen_do_dai_voi_nfc(self):
        """Bất biến mà `_find_ci` phụ thuộc vào — chốt lại tường minh, vì nếu
        nó vỡ thì mọi span đều lệch mà không có triệu chứng nào khác."""
        for s in ("Xin gửi báo cáo tổng kết", "Sở Thông tin và Truyền thông",
                  "Đường lối đổi mới", "quý III năm 2026", "ĐẢNG ỦY"):
            nfc = unicodedata.normalize("NFC", s)
            self.assertEqual(len(strip_accents(nfc)), len(nfc), repr(s))


class TestDocTypeCungHayMem(unittest.TestCase):
    """F-5: nhãn loại văn bản là danh từ tiếng Việt tần suất cao. Nâng một
    khớp chuỗi con lên thành filter AND cứng sẽ làm rỗng kết quả cho nội dung
    chắc chắn có trong kho, và người dùng không thấy vì sao."""

    def _doc_type(self, raw):
        return next((f for f in parse(raw).filters if f.field == "doc_type"), None)

    def test_nhan_giua_cau_chi_la_goi_y_mem(self):
        f = self._doc_type("Xin gửi báo cáo tổng kết công tác")
        self.assertIsNotNone(f, "vẫn phải hiện chip 'Đã hiểu' cho người dùng thấy")
        self.assertFalse(f.hard, "không được AND vào domain")

    def test_nhan_mem_van_o_lai_trong_phan_ngu_nghia(self):
        q = parse("Xin gửi báo cáo tổng kết công tác")
        self.assertIn("báo cáo", q.semantic)
        self.assertIn("tổng kết", q.semantic)

    def test_cau_chi_gom_nhan_thi_la_filter_cung(self):
        f = self._doc_type("kế hoạch")
        self.assertTrue(f.hard)
        self.assertEqual(parse("kế hoạch").semantic, "")

    def test_nhan_kem_moc_thoi_gian_van_la_filter_cung(self):
        # 'Báo cáo quý II của Sở Tài chính năm 2026': bóc hết mốc thì chỉ còn
        # hư từ -> vẫn rõ ràng là ý định duyệt theo loại.
        self.assertTrue(self._doc_type("báo cáo quý II của Sở Tài chính năm 2026").hard)

    def test_hu_tu_dan_dau_khong_pha_filter_cung(self):
        self.assertTrue(self._doc_type("cho tôi xem các quyết định").hard)

    def test_nhan_co_noi_dung_theo_sau_thi_mem(self):
        f = self._doc_type("kế hoạch phòng chống thiên tai trên địa bàn")
        self.assertFalse(f.hard)
        self.assertIn("phòng chống thiên tai", parse(
            "kế hoạch phòng chống thiên tai trên địa bàn").semantic)

    def test_bao_cao_vien_khong_phai_nhan_loai_van_ban(self):
        self.assertIsNone(self._doc_type("danh sách báo cáo viên hội nghị"))


if __name__ == "__main__":
    unittest.main()
