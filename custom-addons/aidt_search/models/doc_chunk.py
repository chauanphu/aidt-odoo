from odoo import api, fields, models

# Số chiều của AITeamVN/Vietnamese_Embedding. Đổi model sang số chiều khác
# là một migration có chủ đích (ALTER COLUMN + nạp lại toàn bộ), không phải
# đổi một tham số cấu hình.
EMBED_DIM = 1024


class AidtDocChunk(models.Model):
    _name = 'aidt.doc.chunk'
    _description = 'Đoạn nội dung đã chỉ mục'
    _order = 'document_id, file_id, seq'

    document_id = fields.Many2one(
        'aidt.document', string='Văn bản', required=True,
        ondelete='cascade', index=True)
    file_id = fields.Many2one(
        'dms.file', string='Tệp', ondelete='cascade', index=True)

    seq = fields.Integer(string='Thứ tự', default=0)
    zone = fields.Char(string='Vùng thể thức', index=True)
    zone_confidence = fields.Selection(
        [('style', 'Theo style'), ('heuristic', 'Suy đoán')],
        string='Độ tin cậy vùng')
    heading_path = fields.Char(string='Đường dẫn mục')
    text = fields.Text(string='Nội dung', required=True)
    embed_text = fields.Text(
        string='Chuỗi đã embed',
        help='Chuỗi thực sự đem đi embed, gồm contextual header. Giữ lại để '
             'khi kết quả sai còn trả lời được câu hỏi "nó đã embed cái gì".')
    page = fields.Integer(string='Trang')
    bbox = fields.Char(string='Toạ độ')
    ocr_confidence = fields.Float(string='Độ tin cậy OCR')
    token_count = fields.Integer(string='Số token')

    def init(self):
        """Tạo extension, hàm f_unaccent, cột vector/tsvector và chỉ mục.

        Ba cột dưới đây không khai bằng fields.* được vì ORM của Odoo không
        có kiểu vector lẫn tsvector. Odoo không xoá cột nó không biết nên
        cách này an toàn qua các lần nâng cấp module.
        """
        cr = self.env.cr
        cr.execute("CREATE EXTENSION IF NOT EXISTS vector")
        cr.execute("CREATE EXTENSION IF NOT EXISTS unaccent")

        # unaccent() không IMMUTABLE nên không dùng thẳng trong generated
        # column được. Bọc lại là thủ thuật chuẩn của Postgres.
        cr.execute("""
            CREATE OR REPLACE FUNCTION f_unaccent(text) RETURNS text
              LANGUAGE sql IMMUTABLE PARALLEL SAFE STRICT AS
              $$ SELECT public.unaccent('public.unaccent', $1) $$
        """)

        cr.execute(f"""
            ALTER TABLE aidt_doc_chunk
              ADD COLUMN IF NOT EXISTS embedding vector({EMBED_DIM}),
              ADD COLUMN IF NOT EXISTS ts tsvector
                GENERATED ALWAYS AS (to_tsvector('simple', coalesce(text, ''))) STORED,
              ADD COLUMN IF NOT EXISTS ts_noaccent tsvector
                GENERATED ALWAYS AS (to_tsvector('simple', f_unaccent(coalesce(text, '')))) STORED,
              ADD COLUMN IF NOT EXISTS ts_seg tsvector
        """)

        cr.execute("""
            CREATE INDEX IF NOT EXISTS aidt_doc_chunk_embedding_idx
              ON aidt_doc_chunk USING hnsw (embedding vector_cosine_ops);
            CREATE INDEX IF NOT EXISTS aidt_doc_chunk_ts_idx
              ON aidt_doc_chunk USING gin (ts);
            CREATE INDEX IF NOT EXISTS aidt_doc_chunk_ts_noaccent_idx
              ON aidt_doc_chunk USING gin (ts_noaccent);
            CREATE INDEX IF NOT EXISTS aidt_doc_chunk_ts_seg_idx
              ON aidt_doc_chunk USING gin (ts_seg);
        """)
