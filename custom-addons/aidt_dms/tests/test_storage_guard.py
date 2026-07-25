from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase


class TestStorageGuard(TransactionCase):
    """R1: kho văn bản AIDT phải giữ chế độ attachment + kế thừa quyền.
    Không cho phép quản trị DMS tắt chế độ này (sẽ sập N-04/V-13)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.storage = cls.env.ref('aidt_dms.storage_aidt')

    def test_cannot_disable_inherit_access(self):
        with self.assertRaises(ValidationError):
            self.storage.inherit_access_from_parent_record = False

    def test_cannot_change_save_type_off_attachment(self):
        with self.assertRaises(ValidationError):
            self.storage.save_type = 'database'

    def test_other_storage_is_unconstrained(self):
        """Ràng buộc chỉ áp cho kho AIDT, không ảnh hưởng kho DMS khác."""
        other = self.env['dms.storage'].create({
            'name': 'Kho khác', 'save_type': 'database',
            'inherit_access_from_parent_record': False})
        self.assertTrue(other.id)
