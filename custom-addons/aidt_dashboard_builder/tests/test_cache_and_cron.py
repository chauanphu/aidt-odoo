from datetime import datetime, timedelta
from odoo.tests.common import TransactionCase
from ..services.cache_service import CacheService


class TestCacheAndCron(TransactionCase):

    def test_cache_set_and_get(self):
        """Kiểm tra lưu và đọc cache dữ liệu."""
        cache_key = CacheService.generate_cache_key(1, self.env.user.id, self.env.company.id, {'test': 123})
        data = {'status': 'ok', 'value': 99}

        CacheService.set_cache(self.env, cache_key, self.env.user.id, self.env.company.id, data, ttl_seconds=300)
        cached_result = CacheService.get_cache(self.env, cache_key)

        self.assertIsNotNone(cached_result)
        self.assertEqual(cached_result['value'], 99)

    def test_cache_expiration(self):
        """Kiểm tra cache hết hạn không được trả về."""
        cache_key = CacheService.generate_cache_key(2, self.env.user.id, self.env.company.id, {})
        data = {'value': 50}

        # Lưu cache với TTL âm (đã hết hạn)
        expired_time = datetime.now() - timedelta(seconds=10)
        self.env['dynamic.dashboard.cache'].sudo().create({
            'cache_key': cache_key,
            'user_id': self.env.user.id,
            'company_id': self.env.company.id,
            'result_json': '{"value": 50}',
            'expires_at': expired_time,
        })

        cached_result = CacheService.get_cache(self.env, cache_key)
        self.assertIsNone(cached_result)
