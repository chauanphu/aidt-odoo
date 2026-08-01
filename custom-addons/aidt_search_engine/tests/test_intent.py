import datetime as dt
import unittest

from aidt_search_engine.intent import parse_query

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


if __name__ == "__main__":
    unittest.main()
