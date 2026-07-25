import yaml

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

from odoo.addons.aidt_format_engine.schema import RulesetError, validate_ruleset


class AidtFormatRuleset(models.Model):
    _name = 'aidt.format.ruleset'
    _description = 'Bộ luật thể thức văn bản'
    _order = 'code, version desc'

    code = fields.Char(
        string='Mã bộ luật', required=True,
        help="Ví dụ: 66-QD/TW, ND-30/2020.")
    version = fields.Char(
        string='Phiên bản', required=True,
        help="Đổi quy định thì tạo phiên bản mới rồi lưu trữ phiên bản cũ, "
             "không sửa tại chỗ — để văn bản cũ còn đối chiếu được với đúng "
             "bộ luật đã dùng ngày đó.")
    ap_dung = fields.Selection(
        [('dang', 'Văn bản Đảng'), ('hanh_chinh', 'Văn bản hành chính')],
        string='Áp dụng cho', required=True)
    spec_yaml = fields.Text(
        string='Bộ luật (YAML)', required=True,
        help="Toàn bộ quy định thể thức. Sửa ở đây, không cần cập nhật mã nguồn.")
    active = fields.Boolean(string='Đang dùng', default=True)

    # Odoo 19 dùng models.Constraint, không dùng _sql_constraints — theo đúng
    # quy ước của addons/mail/models/mail_alias_domain.py trong repo này.
    _code_version_uniq = models.Constraint(
        'UNIQUE(code, version)',
        'Mỗi bộ luật chỉ có một bản ghi cho mỗi phiên bản.',
    )

    @api.depends('code', 'version')
    def _compute_display_name(self):
        for ruleset in self:
            ruleset.display_name = '%s %s' % (ruleset.code or '',
                                              ruleset.version or '')

    @api.constrains('spec_yaml', 'ap_dung')
    def _check_spec_yaml(self):
        for ruleset in self:
            spec = ruleset._parse_yaml()
            try:
                validate_ruleset(spec)
            except RulesetError as exc:
                raise ValidationError(_(
                    "Bộ luật %(name)s sai cấu trúc — %(detail)s",
                    name=ruleset.display_name, detail=str(exc))) from exc
            if spec.get('ap_dung') != ruleset.ap_dung:
                raise ValidationError(_(
                    "Trường 'Áp dụng cho' là %(field)s nhưng khóa ap_dung "
                    "trong YAML là %(yaml)s. Hai giá trị phải khớp nhau.",
                    field=ruleset.ap_dung, yaml=spec.get('ap_dung')))

    def _parse_yaml(self):
        self.ensure_one()
        try:
            spec = yaml.safe_load(self.spec_yaml or '')
        except yaml.YAMLError as exc:
            raise ValidationError(_(
                "Bộ luật %(name)s không phải YAML hợp lệ — %(detail)s",
                name=self.display_name, detail=str(exc))) from exc
        if not isinstance(spec, dict):
            raise ValidationError(_(
                "Bộ luật %(name)s phải là một từ điển khóa-giá trị ở cấp cao nhất.",
                name=self.display_name))
        return spec

    def spec(self):
        """Bộ luật đã parse, dạng dict. Dùng bởi aidt.format.checker."""
        return self._parse_yaml()
