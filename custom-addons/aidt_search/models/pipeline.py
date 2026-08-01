import base64
import logging
import os
import tempfile
import time

from odoo import api, models

from odoo.addons.aidt_search_engine.chunker import chunk_blocks
from odoo.addons.aidt_search_engine.extract import ocr as ocr_mod
from odoo.addons.aidt_search_engine.extract import pdf as pdf_mod
from odoo.addons.aidt_search_engine.extract.docx import UnreadableDocx, extract_docx
from odoo.addons.aidt_search_engine.extract.zone_adapter import assign_zones
from odoo.addons.aidt_search_engine.types import Block, DocMeta

_logger = logging.getLogger(__name__)

# Magic bytes — không tin đuôi tệp.
_ZIP_MAGIC = b'PK\x03\x04'
_PDF_MAGIC = b'%PDF'
_IMAGE_MAGICS = (b'\x89PNG', b'\xff\xd8\xff', b'II*\x00', b'MM\x00*')

# Ảnh 150dpi khổ A4 rộng ~1240px. zone_adapter dùng tỷ lệ nên con số này
# chỉ cần đúng bậc độ lớn.
_PAGE_WIDTH_PX = 1240.0


class PermanentExtractError(Exception):
    """Tệp không bao giờ xử lý được — retry chỉ đốt GPU."""


class AidtIndexPipeline(models.AbstractModel):
    _name = 'aidt.index.pipeline'
    _description = 'Đường ống chỉ mục tài liệu'

    @api.model
    def _config(self, key, default=None):
        return self.env['ir.config_parameter'].sudo().get_param(
            f'aidt_search.{key}', default)

    @api.model
    def _doc_meta(self, document):
        """DocMeta cho contextual header."""
        labels = dict(document._fields['doc_type'].selection)
        return DocMeta(
            doc_type_label=labels.get(document.doc_type),
            reference=document.reference or None,
            title=document.name or None,
        )

    # ------------------------------------------------------------------ #
    # Định tuyến trích xuất
    # ------------------------------------------------------------------ #
    @api.model
    def _extract(self, job, blob, filename):
        if blob.startswith(_ZIP_MAGIC):
            try:
                return extract_docx(blob)
            except UnreadableDocx as exc:
                raise PermanentExtractError(f'DOCX không đọc được: {exc}') from exc
        if blob.startswith(_PDF_MAGIC):
            return self._extract_pdf(blob)
        if any(blob.startswith(m) for m in _IMAGE_MAGICS):
            return self._ocr_png(blob, ocr_mod.WINDOW_IMAGE)
        raise PermanentExtractError(f'định dạng chưa hỗ trợ: {filename}')

    @api.model
    def _extract_pdf(self, blob):
        """Quyết định theo TỪNG TRANG: văn bản thật rất hay lai — vài trang
        soạn máy, vài trang scan chèn vào.

        Toàn bộ lời gọi poppler (pdfinfo/pdftotext/pdftoppm) được bọc
        CHUNG một try/except PdfToolError: một trang hỏng khiến bất kỳ
        công cụ nào trong ba công cụ đó lỗi đều là dấu hiệu tệp PDF hỏng,
        không phải sự cố hạ tầng tạm thời — retry không giúp ích gì, chỉ
        đốt thời gian worker cho tới khi hết attempt. Nếu chỉ bọc riêng
        pdfinfo (như ban đầu), lỗi từ pdftotext/pdftoppm trên một trang cụ
        thể sẽ rơi xuống `except Exception` chung ở `_process_one` và bị
        phân loại NHẦM thành tạm thời — hot-loop 3 lần vô ích trước khi
        cùng thất bại.
        """
        threshold = int(self._config('scan_char_threshold', 50))
        blocks = []
        fd, path = tempfile.mkstemp(suffix='.pdf')
        try:
            with os.fdopen(fd, 'wb') as fh:
                fh.write(blob)
            try:
                total = pdf_mod.page_count(path)
                for page in range(1, total + 1):
                    text = pdf_mod.page_text(path, page)
                    if len(text.strip()) >= threshold:
                        blocks.extend(self._blocks_from_text(text, page))
                    else:
                        png = pdf_mod.render_page_png(path, page)
                        blocks.extend(self._ocr_png(png, ocr_mod.WINDOW_PDF, page=page))
            except pdf_mod.PdfToolError as exc:
                raise PermanentExtractError(f'PDF không đọc được: {exc}') from exc
        finally:
            if os.path.exists(path):
                os.unlink(path)
        return blocks

    @api.model
    def _blocks_from_text(self, text, page):
        raw = [Block(text=line.strip(), page=page)
               for line in text.splitlines() if line.strip()]
        return assign_zones(raw, _PAGE_WIDTH_PX)

    @api.model
    def _ocr_png(self, png, window_size, page=None):
        base_url = self._config('ocr_url', '')
        blocks = ocr_mod.ocr_image(png, base_url, window_size=window_size)
        for block in blocks:
            block.page = page
        return assign_zones(blocks, _PAGE_WIDTH_PX)

    # ------------------------------------------------------------------ #
    # Chạy một job
    # ------------------------------------------------------------------ #
    @api.model
    def run(self, job):
        """Chạy hết một job trong ĐÚNG MỘT giao dịch — không commit xen giữa
        các bước `job.write({'state': ...})`. `_claim()` (Task 13) giữ khoá
        `FOR UPDATE SKIP LOCKED` trên row của job này cho tới khi giao dịch
        hiện tại kết thúc; nếu hàm này commit giữa chừng, khoá đó bị nhả
        sớm và mở lại đúng cửa sổ đua mà Task 13 đã đóng giữa `_enqueue_file`
        và `_claim`/`_process_one`. Các trạng thái 'extracting'/'chunking'/
        'embedding' vì vậy CHỈ là nhãn tiến độ hiển thị được sau khi job đã
        `done`/`failed` (đọc lại từ job khác) — không ai quan sát được job
        đang ở trạng thái đó trong lúc nó thật sự đang xử lý.
        """
        job.write({'state': 'extracting'})
        stage_ms, dms_file = {}, job.file_id.sudo()
        blob = base64.b64decode(dms_file.with_context(bin_size=False).content or b'')

        t0 = time.monotonic()
        try:
            blocks = self._extract(job, blob, dms_file.name or '')
        except PermanentExtractError as exc:
            job._mark_permanent(str(exc))
            return
        except ocr_mod.OcrEmptyOutput as exc:
            # Trang trắng và lỗi cấu hình trông giống nhau — nhưng ghi chunk
            # rỗng thì tài liệu "đã chỉ mục" mà tìm mãi không ra.
            job._mark_permanent(str(exc))
            return
        stage_ms['extract'] = int((time.monotonic() - t0) * 1000)

        if not blocks:
            job._mark_permanent('không trích xuất được nội dung nào')
            return

        job.write({'state': 'chunking'})
        t0 = time.monotonic()
        chunks = chunk_blocks(blocks, self._doc_meta(job.document_id))
        stage_ms['chunk'] = int((time.monotonic() - t0) * 1000)
        if not chunks:
            job._mark_permanent('nội dung trích được rỗng sau khi chia đoạn')
            return

        job.write({'state': 'embedding'})
        t0 = time.monotonic()
        vectors = self.env['aidt.embed.client'].embed([c.embed_text for c in chunks])
        stage_ms['embed'] = int((time.monotonic() - t0) * 1000)

        self._store(job, chunks, vectors)
        job._mark_done(stage_ms)

    @api.model
    def _store(self, job, chunks, vectors):
        """Xoá chunk cũ rồi chèn mới, trong cùng một transaction."""
        Chunk = self.env['aidt.doc.chunk'].sudo()
        Chunk.search([('file_id', '=', job.file_id.id)]).unlink()
        records = Chunk.create([{
            'document_id': job.document_id.id,
            'file_id': job.file_id.id,
            'seq': c.seq,
            'zone': c.zone,
            'zone_confidence': c.zone_confidence,
            'heading_path': c.heading_path,
            'text': c.text,
            'embed_text': c.embed_text,
            'page': c.page,
            'bbox': str(list(c.bbox)) if c.bbox else False,
            'token_count': c.token_count,
        } for c in chunks])
        for record, vector in zip(records, vectors):
            self.env.cr.execute(
                "UPDATE aidt_doc_chunk SET embedding = %s::vector WHERE id = %s",
                (str(vector), record.id))
