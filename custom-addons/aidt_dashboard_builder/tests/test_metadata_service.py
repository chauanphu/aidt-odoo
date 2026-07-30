from odoo.tests.common import TransactionCase
from ..services.metadata_service import MetadataService


class TestMetadataService(TransactionCase):

    def test_allowed_models_filtering(self):
        """Kiểm tra danh sách models được phép trả về."""
        allowed_models = MetadataService.get_allowed_models(self.env)
        model_names = [m['model'] for m in allowed_models]

        self.assertNotIn('ir.config_parameter', model_names)
        self.assertNotIn('res.users.log', model_names)

    def test_forbidden_fields_filtering(self):
        """Kiểm tra loại bỏ các trường nhạy cảm khỏi metadata."""
        fields_data = MetadataService.get_model_fields(self.env, 'res.users')
        field_names = [f['name'] for f in fields_data]

        self.assertNotIn('password', field_names)
