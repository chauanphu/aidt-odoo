from .query_validator import FORBIDDEN_MODELS, FORBIDDEN_FIELDS


class MetadataService:
    """Service cung cấp danh sách Models, Fields hợp lệ cho Visual Query Builder."""

    @classmethod
    def get_allowed_models(cls, env):
        """Lấy danh sách các models hợp lệ mà user hiện tại có quyền truy cập."""
        models = env['ir.model'].search([
            ('transient', '=', False),
            ('model', 'not in', list(FORBIDDEN_MODELS))
        ])

        result = []
        for m in models:
            if m.model in env and env[m.model].check_access_rights('read', raise_exception=False):
                result.append({
                    'id': m.id,
                    'name': m.name,
                    'model': m.model,
                })
        return result

    @classmethod
    def get_model_fields(cls, env, model_name):
        """Lấy danh sách các fields hợp lệ của một model."""
        if not model_name or model_name not in env:
            return []

        model_obj = env[model_name]
        fields_data = []

        for fname, field in model_obj._fields.items():
            if fname in FORBIDDEN_FIELDS or fname.startswith('_'):
                continue

            fields_data.append({
                'name': fname,
                'string': field.string or fname,
                'type': field.type,
                'store': getattr(field, 'store', True),
                'relation': getattr(field, 'comodel_name', False),
            })
        return fields_data
