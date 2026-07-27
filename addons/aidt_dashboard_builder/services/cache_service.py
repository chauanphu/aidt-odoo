import hashlib
import json
from datetime import datetime, timedelta
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT


class CacheService:
    @staticmethod
    def generate_cache_key(dashboard_id, user_id, company_id, filter_values):
        """Tạo khóa md5 hash duy nhất cho truy vấn dựa trên thông số đầu vào."""
        filter_str = json.dumps(filter_values or {}, sort_keys=True)
        raw_key = f"db_{dashboard_id}_usr_{user_id}_cmp_{company_id}_{filter_str}"
        return hashlib.md5(raw_key.encode('utf-8')).hexdigest()

    @classmethod
    def get_cache(cls, env, cache_key):
        """Lấy dữ liệu cache nếu chưa hết hạn."""
        now = datetime.now()
        cache_rec = env['dynamic.dashboard.cache'].sudo().search([
            ('cache_key', '=', cache_key),
            ('expires_at', '>', now)
        ], limit=1)

        if cache_rec:
            try:
                return json.loads(cache_rec.result_json)
            except Exception:
                return None
        return None

    @classmethod
    def set_cache(cls, env, cache_key, user_id, company_id, data, ttl_seconds=60):
        """Lưu trữ dữ liệu cache với thời gian sống (TTL)."""
        if ttl_seconds <= 0:
            return

        expires_at = datetime.now() + timedelta(seconds=ttl_seconds)
        result_json = json.dumps(data)

        cache_obj = env['dynamic.dashboard.cache'].sudo()

        # Tìm và cập nhật hoặc tạo mới
        existing = cache_obj.search([('cache_key', '=', cache_key)], limit=1)
        if existing:
            existing.write({
                'result_json': result_json,
                'expires_at': expires_at
            })
        else:
            cache_obj.create({
                'cache_key': cache_key,
                'user_id': user_id,
                'company_id': company_id,
                'result_json': result_json,
                'expires_at': expires_at
            })
