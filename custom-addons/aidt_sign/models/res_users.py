from odoo import models, fields, api

class ResUsers(models.Model):
    _inherit = 'res.users'

    digital_signature_img = fields.Binary(string='Ảnh chữ ký tay tươi')
    certificate_ids = fields.One2many('aidt.sign.certificate', 'owner_id', string='Chứng thư số cá nhân')

    is_digital_signature_leader = fields.Boolean(
        string='Là Lãnh đạo (Bí thư) có quyền Chữ ký tay tươi',
        compute='_compute_digital_signature_permissions'
    )
    is_digital_signature_user = fields.Boolean(
        string='Có quyền sử dụng Tab Chữ ký số',
        compute='_compute_digital_signature_permissions'
    )

    def _compute_digital_signature_permissions(self):
        # Chỉ có Bí thư và Admin mới có quyền ký cá nhân (Cột 1 Chữ ký tay tươi + Cột 2 Cert cá nhân)
        g_leader = [
            'aidt_org.group_bi_thu',
            'aidt_org.group_aidt_admin',
        ]
        # Văn thư có quyền quản lý Cert Cơ quan & Con dấu đỏ (Cột 2 Full Width)
        g_vanthu = 'aidt_org.group_van_thu'

        for user in self:
            is_leader = any(user.has_group(xml_id) for xml_id in g_leader)
            is_vt = user.has_group(g_vanthu)
            user.is_digital_signature_leader = is_leader
            user.is_digital_signature_user = is_leader or is_vt

    # Bổ sung digital_signature_img & certificate_ids vào danh sách các trường người dùng có quyền tự đọc/sửa trên trang My Preferences của chính mình
    @property
    def SELF_READABLE_FIELDS(self):
        return super().SELF_READABLE_FIELDS + [
            'digital_signature_img',
            'certificate_ids',
            'is_digital_signature_leader',
            'is_digital_signature_user',
        ]

    @property
    def SELF_WRITEABLE_FIELDS(self):
        return super().SELF_WRITEABLE_FIELDS + ['digital_signature_img', 'certificate_ids']

    # Bổ sung related_sudo=True cho tất cả các trường thông tin cá nhân liên kết tới hr.employee
    # để người dùng mở trang My Preferences không bị lỗi Access Error do phân quyền nhóm hr.group_hr_user của hr.employee
    private_street = fields.Char(related='employee_id.private_street', readonly=False, related_sudo=True)
    private_street2 = fields.Char(related='employee_id.private_street2', readonly=False, related_sudo=True)
    private_city = fields.Char(related='employee_id.private_city', readonly=False, related_sudo=True)
    private_state_id = fields.Many2one(related='employee_id.private_state_id', readonly=False, related_sudo=True)
    private_zip = fields.Char(related='employee_id.private_zip', readonly=False, related_sudo=True)
    private_country_id = fields.Many2one(related='employee_id.private_country_id', readonly=False, related_sudo=True)
    private_phone = fields.Char(related='employee_id.private_phone', readonly=False, related_sudo=True)
    private_email = fields.Char(related='employee_id.private_email', readonly=False, related_sudo=True)
    km_home_work = fields.Integer(related='employee_id.km_home_work', readonly=False, related_sudo=True)
    emergency_contact = fields.Char(related='employee_id.emergency_contact', readonly=False, related_sudo=True)
    emergency_phone = fields.Char(related='employee_id.emergency_phone', readonly=False, related_sudo=True)
    visa_expire = fields.Date(related='employee_id.visa_expire', readonly=False, related_sudo=True)
    additional_note = fields.Text(related='employee_id.additional_note', readonly=False, related_sudo=True)
    barcode = fields.Char(related='employee_id.barcode', readonly=False, related_sudo=True)
    pin = fields.Char(related='employee_id.pin', readonly=False, related_sudo=True)
