from odoo import _, api, models
from odoo.exceptions import ValidationError


class DmsStorage(models.Model):
    _inherit = 'dms.storage'

    @api.constrains('inherit_access_from_parent_record', 'save_type')
    def _check_aidt_storage_inherit_mode(self):
        """R1: Kho văn bản AIDT phải giữ save_type='attachment' và
        inherit_access_from_parent_record=True. Nếu tắt, dms.file không còn
        ủy quyền cho aidt.document -> sập phân quyền độ mật/phạm vi (N-04/V-13).
        Ràng buộc này khóa bất biến ở tầng code, không chỉ dữ liệu seed."""
        aidt_storage = self.env.ref(
            'aidt_dms.storage_aidt', raise_if_not_found=False)
        if not aidt_storage:
            return
        for storage in self:
            if storage.id != aidt_storage.id:
                continue
            if (not storage.inherit_access_from_parent_record
                    or storage.save_type != 'attachment'):
                raise ValidationError(_(
                    "Kho văn bản AIDT phải giữ chế độ 'Attachment' và 'Kế thừa "
                    "quyền từ bản ghi liên kết' để đảm bảo phân quyền theo độ "
                    "mật và phạm vi (N-04/V-13). Không được thay đổi hai thiết "
                    "lập này."))
