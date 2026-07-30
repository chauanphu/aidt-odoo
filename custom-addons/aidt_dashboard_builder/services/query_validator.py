import logging
from odoo.exceptions import UserError, AccessError

_logger = logging.getLogger(__name__)

# Bảng các model cấm truy cập nhạy cảm vì lý do bảo mật hệ thống
FORBIDDEN_MODELS = {
    'ir.config_parameter',
    'res.users.log',
    'ir.cron',
    'ir.module.module',
    'res.groups',
    'ir.model.access',
    'ir.rule',
}

# Các trường thông tin nhạy cảm không cho phép query trực tiếp
FORBIDDEN_FIELDS = {
    'password',
    'secret',
    'token',
    'api_key',
    'access_token',
}


class QueryValidator:
    @staticmethod
    def validate_model_access(env, model_name):
        """Kiểm tra quyền truy cập Model và Whitelist bảo mật."""
        if not model_name:
            raise UserError("Model name không được để trống.")

        if model_name in FORBIDDEN_MODELS:
            _logger.warning("Truy cập vi phạm bảo mật: Model %s nằm trong danh sách cấm.", model_name)
            raise AccessError(f"Không có quyền truy cập dữ liệu của model '{model_name}'.")

        if model_name not in env:
            raise UserError(f"Model '{model_name}' không tồn tại trong hệ thống.")

        # Kiểm tra Access Right qua ORM của user hiện tại
        model_obj = env[model_name]
        if not model_obj.check_access_rights('read', raise_exception=False):
            _logger.warning("User %s không có quyền 'read' trên model %s", env.user.id, model_name)
            raise AccessError(f"Bạn không có quyền đọc dữ liệu từ '{model_name}'.")

        return model_obj

    @staticmethod
    def validate_field(model_obj, field_name):
        """Kiểm tra sự tồn tại của Field và loại bỏ các trường nhạy cảm."""
        if not field_name:
            return False

        # Xử lý quan hệ liên kết liên quan (ví dụ: partner_id.country_id)
        sub_fields = field_name.split('.')
        current_model = model_obj

        for fname in sub_fields:
            if fname in FORBIDDEN_FIELDS:
                raise AccessError(f"Trường dữ liệu '{fname}' bị cấm truy cập vì lý do bảo mật.")

            if fname not in current_model._fields:
                raise UserError(f"Trường dữ liệu '{fname}' không tồn tại trên model '{current_model._name}'.")

            field_type = current_model._fields[fname].type
            if field_type in ('many2one', 'one2many', 'many2many'):
                comodel_name = current_model._fields[fname].comodel_name
                if comodel_name and comodel_name in current_model.env:
                    current_model = current_model.env[comodel_name]

        return True
