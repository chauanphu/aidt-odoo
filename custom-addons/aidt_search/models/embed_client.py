import json
import logging
import urllib.error
import urllib.request

from odoo import api, models

_logger = logging.getLogger(__name__)

BATCH_SIZE = 32
TIMEOUT = 120


class EmbedError(RuntimeError):
    """Không gọi được service embedding."""


class EmbedDimensionError(RuntimeError):
    """Vector trả về không đúng số chiều của cột."""


class AidtEmbedClient(models.AbstractModel):
    _name = 'aidt.embed.client'
    _description = 'Client dịch vụ embedding'

    @api.model
    def _config(self, key, default=None):
        return self.env['ir.config_parameter'].sudo().get_param(
            f'aidt_search.{key}', default)

    @api.model
    def _post(self, texts):
        url = f"{self._config('embed_url', '').rstrip('/')}/embeddings"
        body = {'model': self._config('embed_model'), 'input': texts}
        req = urllib.request.Request(
            url, data=json.dumps(body).encode('utf-8'),
            headers={'Content-Type': 'application/json'})
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
                data = json.loads(resp.read().decode('utf-8'))
        except (urllib.error.URLError, OSError, ValueError) as exc:
            raise EmbedError(f'gọi embedding thất bại: {exc}') from exc
        try:
            rows = data['data']
        except (KeyError, TypeError) as exc:
            raise EmbedError(f'embedding trả về cấu trúc lạ: {data!r}') from exc
        return self._order_by_index(rows, len(texts))

    @api.model
    def _order_by_index(self, rows, expected_count):
        """Sắp lại danh sách vector theo trường 'index' của từng phần tử —
        KHÔNG bao giờ ngầm định service trả đúng thứ tự đã gửi.

        Chuẩn embeddings kiểu OpenAI định nghĩa 'index' chính là để bên gọi
        tự phát hiện đảo thứ tự: một backend gộp lô hoặc xử lý song song có
        thể hợp lệ trả kết quả không theo thứ tự input. Một phản hồi ĐỦ SỐ
        LƯỢNG, ĐÚNG CHIỀU nhưng ĐẢO THỨ TỰ vẫn lọt qua mọi kiểm tra khác của
        `embed()` — hậu quả là ghép sai vector cho chunk một cách hoàn toàn
        im lặng, không có ngoại lệ nào báo. Bắt buộc mỗi phần tử phải có
        'index' (không coi là tuỳ chọn): thiếu, trùng lặp, hoặc lệch khỏi
        đúng tập {0..expected_count-1} đều là lỗi cấu trúc — không đoán mò
        để "tự sửa" giúp service.
        """
        try:
            by_index = {}
            for row in rows:
                idx = row['index']
                if idx in by_index:
                    raise EmbedError(f'embedding trả về index trùng lặp: {idx}')
                by_index[idx] = row['embedding']
        except (KeyError, TypeError) as exc:
            raise EmbedError(
                f'embedding trả về cấu trúc lạ (thiếu index/embedding): '
                f'{rows!r}') from exc
        if set(by_index) != set(range(expected_count)):
            raise EmbedError(
                f'embedding trả về tập index {sorted(by_index)!r} không '
                f'khớp {expected_count} văn bản gửi đi — không thể ghép '
                f'theo vị trí một cách an toàn')
        return [by_index[i] for i in range(expected_count)]

    @api.model
    def _embed(self, texts):
        """list[str] -> list[list[float]]. Ném EmbedDimensionError nếu lệch chiều.

        Kiểm số chiều là bắt buộc: cột là vector(1024) cố định, ghi bừa một
        vector 768 chiều sẽ hỏng chỉ mục theo cách rất khó truy.

        Kiểm cả SỐ LƯỢNG vector mỗi lô trả về so với số văn bản gửi đi: một
        phản hồi thiếu (service trả về ít hơn) không được phép âm thầm dồn
        toa — nếu không, `zip(records, vectors)` ở tầng gọi sẽ ghép lệch vị
        trí, gán vector của chunk này cho chunk khác mà không một dấu hiệu
        nào lộ ra.
        """
        if not texts:
            return []
        expected = int(self._config('embed_dim', 1024))
        vectors = []
        for start in range(0, len(texts), BATCH_SIZE):
            batch_texts = texts[start:start + BATCH_SIZE]
            batch = self._post(batch_texts)
            if len(batch) != len(batch_texts):
                raise EmbedError(
                    f'embedding service trả về {len(batch)} vector cho '
                    f'{len(batch_texts)} văn bản gửi đi — không thể ghép '
                    f'theo vị trí một cách an toàn')
            for vec in batch:
                if len(vec) != expected:
                    raise EmbedDimensionError(
                        f'model trả vector {len(vec)} chiều nhưng cột là '
                        f'vector({expected}) — đổi model là một migration, '
                        f'không phải đổi một tham số')
            vectors.extend(batch)
        return vectors
