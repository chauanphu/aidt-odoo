from odoo.tests.common import TransactionCase


class TestChunkSchema(TransactionCase):
    def _columns(self):
        self.env.cr.execute(
            "SELECT column_name, udt_name FROM information_schema.columns "
            "WHERE table_name = 'aidt_doc_chunk'"
        )
        return dict(self.env.cr.fetchall())

    def test_extension_da_cai(self):
        self.env.cr.execute("SELECT extname FROM pg_extension")
        names = {r[0] for r in self.env.cr.fetchall()}
        self.assertIn("vector", names)
        self.assertIn("unaccent", names)

    def test_cot_embedding_dung_kieu(self):
        self.assertEqual(self._columns().get("embedding"), "vector")

    def test_hai_cot_tsvector_ton_tai(self):
        cols = self._columns()
        self.assertEqual(cols.get("ts"), "tsvector")
        self.assertEqual(cols.get("ts_noaccent"), "tsvector")
        self.assertEqual(cols.get("ts_seg"), "tsvector")

    def test_ts_la_generated_column(self):
        # Generated column là điểm mấu chốt: không có đường nào cho code
        # quên cập nhật chỉ mục lexical.
        self.env.cr.execute(
            "SELECT is_generated FROM information_schema.columns "
            "WHERE table_name='aidt_doc_chunk' AND column_name='ts'"
        )
        self.assertEqual(self.env.cr.fetchone()[0], "ALWAYS")

    def test_f_unaccent_bo_dau_va_xu_ly_chu_d(self):
        # Phải khớp strip_accents() phía Python, nếu không kênh không dấu trượt.
        self.env.cr.execute("SELECT f_unaccent('Đảng hộ nghèo')")
        self.assertEqual(self.env.cr.fetchone()[0], "Dang ho ngheo")

    def test_chi_muc_hnsw_va_gin_ton_tai(self):
        self.env.cr.execute(
            "SELECT indexdef FROM pg_indexes WHERE tablename = 'aidt_doc_chunk'"
        )
        defs = " ".join(r[0] for r in self.env.cr.fetchall())
        self.assertIn("hnsw", defs)
        self.assertIn("gin", defs)

    def test_ts_tu_dong_cap_nhat_khi_ghi_text(self):
        doc = self.env["aidt.document"].create({
            "name": "Văn bản thử", "direction": "den", "secrecy": "thuong",
        })
        chunk = self.env["aidt.doc.chunk"].create({
            "document_id": doc.id, "seq": 0,
            "text": "hỗ trợ hộ nghèo", "embed_text": "hỗ trợ hộ nghèo",
        })
        self.env.cr.execute(
            "SELECT ts @@ to_tsquery('simple', 'nghèo'), "
            "       ts_noaccent @@ to_tsquery('simple', 'ngheo') "
            "FROM aidt_doc_chunk WHERE id = %s", (chunk.id,)
        )
        has_accent, no_accent = self.env.cr.fetchone()
        self.assertTrue(has_accent)
        self.assertTrue(no_accent)
