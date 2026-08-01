import base64
import json
from unittest.mock import patch

from odoo.tests.common import TransactionCase

from odoo.addons.aidt_search_engine.types import Block

DIM = 1024


def fake_vectors(texts):
    return [[0.01] * DIM for _ in texts]


class PipelineCase(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, test_dms_field=True))
        cls.doc = cls.env['aidt.document'].create({
            'name': 'Kế hoạch an toàn thông tin', 'direction': 'den',
            'secrecy': 'thuong', 'reference': '145/KH-UBND', 'doc_type': 'ke_hoach',
        })

    def _file(self, name, content=b'noi dung'):
        return self.env['dms.file'].sudo().create({
            'name': name, 'directory_id': self.doc.directory_id.id,
            'content': base64.b64encode(content),
            'res_model': 'aidt.document', 'res_id': self.doc.id,
        })

    def _job(self, dms_file):
        return self.env['aidt.index.job'].search([('file_id', '=', dms_file.id)], limit=1)


class TestDocMeta(PipelineCase):
    def test_lay_dung_ba_thanh_phan_header(self):
        meta = self.env['aidt.index.pipeline']._doc_meta(self.doc)
        self.assertEqual(meta.reference, '145/KH-UBND')
        self.assertEqual(meta.doc_type_label, 'Kế hoạch')
        self.assertEqual(meta.title, 'Kế hoạch an toàn thông tin')


class TestEmbedClient(PipelineCase):
    def test_kiem_so_chieu_va_nem_khi_lech(self):
        # Đổi model mà quên embed_dim phải nổ NGAY lúc chèn, tuyệt đối
        # không được ghi bừa vector sai chiều vào cột vector(1024).
        from odoo.addons.aidt_search.models.embed_client import EmbedDimensionError
        Client = self.env['aidt.embed.client']
        with patch.object(type(Client), '_post', return_value=[[0.0] * 768]):
            with self.assertRaises(EmbedDimensionError):
                Client.embed(['xin chào'])

    def test_danh_sach_rong_khong_goi_service(self):
        Client = self.env['aidt.embed.client']
        with patch.object(type(Client), '_post') as post:
            self.assertEqual(Client.embed([]), [])
            post.assert_not_called()

    def test_phan_hoi_it_hon_so_van_ban_gui_di_nem_loi(self):
        # Lô 2 văn bản nhưng service chỉ trả 1 vector — nếu không chặn,
        # zip(records, vectors) ở pipeline._store sẽ ghép lệch vị trí, chunk
        # cuối cùng bị bỏ lại không có embedding mà không một lỗi nào báo.
        from odoo.addons.aidt_search.models.embed_client import EmbedError
        Client = self.env['aidt.embed.client']
        with patch.object(type(Client), '_post', return_value=[[0.0] * DIM]):
            with self.assertRaises(EmbedError):
                Client.embed(['van ban a', 'van ban b'])


class _FakeHttpResponse:
    """Giả context manager mà `urllib.request.urlopen(...)` trả về — cho
    phép test chạy xuyên suốt `_post` -> `_order_by_index` thật, không phải
    chỉ patch `_post` để bỏ qua toàn bộ logic ghép theo `index`."""

    def __init__(self, payload):
        self._body = json.dumps(payload).encode('utf-8')

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        return False


class TestEmbedClientOrdering(PipelineCase):
    """Chuẩn embeddings kiểu OpenAI định nghĩa trường 'index' đúng để bên
    gọi tự phát hiện đảo thứ tự — một backend gộp lô/xử lý song song có
    thể hợp lệ trả kết quả không theo thứ tự input. Số lượng đúng và chiều
    đúng không đủ: phải ghép lại theo 'index', không theo vị trí mảng trả
    về, nếu không một phản hồi bị đảo thứ tự sẽ gán sai vector cho chunk
    mà không hề có lỗi nào lộ ra."""

    def _mock_urlopen(self, payload):
        return patch(
            'odoo.addons.aidt_search.models.embed_client.urllib.request.urlopen',
            return_value=_FakeHttpResponse(payload))

    def test_dao_thu_tu_van_ghep_dung_vi_tri_theo_index(self):
        Client = self.env['aidt.embed.client']
        payload = {'data': [
            {'index': 1, 'embedding': [2.0] * DIM},
            {'index': 0, 'embedding': [1.0] * DIM},
        ]}
        with self._mock_urlopen(payload):
            vectors = Client.embed(['van ban a', 'van ban b'])
        self.assertEqual(vectors[0][0], 1.0)
        self.assertEqual(vectors[1][0], 2.0)

    def test_index_trung_lap_nem_loi(self):
        from odoo.addons.aidt_search.models.embed_client import EmbedError
        Client = self.env['aidt.embed.client']
        payload = {'data': [
            {'index': 0, 'embedding': [1.0] * DIM},
            {'index': 0, 'embedding': [2.0] * DIM},
        ]}
        with self._mock_urlopen(payload):
            with self.assertRaises(EmbedError):
                Client.embed(['van ban a', 'van ban b'])

    def test_index_ngoai_pham_vi_nem_loi(self):
        from odoo.addons.aidt_search.models.embed_client import EmbedError
        Client = self.env['aidt.embed.client']
        payload = {'data': [
            {'index': 0, 'embedding': [1.0] * DIM},
            {'index': 5, 'embedding': [2.0] * DIM},
        ]}
        with self._mock_urlopen(payload):
            with self.assertRaises(EmbedError):
                Client.embed(['van ban a', 'van ban b'])


class TestPipelineRun(PipelineCase):
    def _run(self, dms_file, blocks):
        job = self._job(dms_file)
        Pipeline = type(self.env['aidt.index.pipeline'])
        with patch.object(Pipeline, '_extract', return_value=blocks), \
             patch.object(type(self.env['aidt.embed.client']), 'embed', side_effect=fake_vectors):
            self.env['aidt.index.pipeline'].run(job)
        return job

    def test_sinh_chunk_va_danh_dau_done(self):
        f = self._file('mau.docx')
        job = self._run(f, [Block(text='Các sở, ban, ngành có trách nhiệm.', zone='noi_dung')])
        self.assertEqual(job.state, 'done')
        self.assertEqual(self.env['aidt.doc.chunk'].search_count([('file_id', '=', f.id)]), 1)

    def test_embed_text_chua_contextual_header(self):
        f = self._file('mau.docx')
        self._run(f, [Block(text='Nội dung điều khoản.', zone='noi_dung')])
        chunk = self.env['aidt.doc.chunk'].search([('file_id', '=', f.id)], limit=1)
        self.assertIn('145/KH-UBND', chunk.embed_text)
        self.assertNotIn('145/KH-UBND', chunk.text)

    def test_ghi_vector_vao_cot_embedding(self):
        f = self._file('mau.docx')
        self._run(f, [Block(text='Nội dung.', zone='noi_dung')])
        chunk = self.env['aidt.doc.chunk'].search([('file_id', '=', f.id)], limit=1)
        self.env.cr.execute(
            "SELECT embedding IS NOT NULL FROM aidt_doc_chunk WHERE id = %s", (chunk.id,))
        self.assertTrue(self.env.cr.fetchone()[0])

    def test_nap_lai_xoa_chunk_cu_truoc(self):
        f = self._file('mau.docx')
        self._run(f, [Block(text='Bản đầu tiên.', zone='noi_dung')])
        self._job(f).action_retry()
        self._run(f, [Block(text='Bản thứ hai.', zone='noi_dung')])
        chunks = self.env['aidt.doc.chunk'].search([('file_id', '=', f.id)])
        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks.text, 'Bản thứ hai.')

    def test_ghi_stage_ms(self):
        f = self._file('mau.docx')
        job = self._run(f, [Block(text='Nội dung.', zone='noi_dung')])
        self.assertIn('extract', job.stage_ms)
        self.assertIn('embed', job.stage_ms)

    def test_khong_trich_duoc_gi_thi_failed_vinh_vien(self):
        f = self._file('trong.docx')
        job = self._run(f, [])
        self.assertEqual(job.state, 'failed')
        self.assertEqual(job.error_kind, 'permanent')


class TestExtractRouting(PipelineCase):
    def test_dinh_dang_khong_ho_tro_la_loi_vinh_vien(self):
        f = self._file('anh.tiff.xyz', b'\x00\x01rac')
        job = self._job(f)
        self.env['aidt.index.pipeline'].run(job)
        self.assertEqual(job.state, 'failed')
        self.assertEqual(job.error_kind, 'permanent')

    def test_docx_hong_la_loi_vinh_vien(self):
        # Phải bắt đầu bằng đúng magic bytes ZIP để thật sự đi vào nhánh
        # extract_docx/UnreadableDocx — b'khong phai docx' (bản cũ) không có
        # magic này nên rơi vào nhánh 'định dạng chưa hỗ trợ' ở cuối
        # `_extract`, trùng lặp hệt test_dinh_dang_khong_ho_tro_la_loi_vinh_vien
        # và không hề chạm nhánh UnreadableDocx mà tên test này nói tới.
        # Phần sau magic bytes không phải một zip hợp lệ nên python-docx ném
        # BadZipFile, aidt_format_engine bọc lại thành UnreadableDocx.
        f = self._file('hong.docx', b'PK\x03\x04' + b'\x00' * 40)
        job = self._job(f)
        self.env['aidt.index.pipeline'].run(job)
        self.assertEqual(job.state, 'failed')
        self.assertEqual(job.error_kind, 'permanent')
