from odoo import api, fields, models


class DynamicDashboard(models.Model):
    _name = 'dynamic.dashboard'
    _description = 'Dynamic Dashboard'
    _inherit = ['mail.thread']
    _order = 'sequence, id desc'

    name = fields.Char(string='Tên Dashboard', required=True, tracking=True)
    sequence = fields.Integer(string='Thứ tự', default=10)
    description = fields.Text(string='Mô tả')
    owner_id = fields.Many2one(
        'res.users', string='Chủ sở hữu', default=lambda self: self.env.user, required=True
    )
    company_id = fields.Many2one(
        'res.company', string='Công ty', default=lambda self: self.env.company
    )
    company_ids = fields.Many2many('res.company', string='Chia sẻ theo công ty')
    group_ids = fields.Many2many('res.groups', string='Chia sẻ theo nhóm quyền')
    viewer_ids = fields.Many2many(
        'res.users', 'dashboard_viewer_rel', 'dashboard_id', 'user_id', string='Người xem chỉ định'
    )
    designer_ids = fields.Many2many(
        'res.users', 'dashboard_designer_rel', 'dashboard_id', 'user_id', string='Người thiết kế chỉ định'
    )

    state = fields.Selection([
        ('draft', 'Dự thảo'),
        ('published', 'Đã xuất bản'),
        ('archived', 'Lưu trữ')
    ], string='Trạng thái', default='draft', required=True, tracking=True)

    theme = fields.Selection([
        ('light', 'Sáng (Light)'),
        ('dark', 'Tối (Dark)'),
        ('custom', 'Tùy chỉnh')
    ], string='Giao diện', default='light', required=True)

    refresh_interval = fields.Integer(
        string='Tự động làm mới (giây)', default=0,
        help='0 = Tắt tự động làm mới'
    )
    default_filter_json = fields.Text(string='Bộ lọc mặc định (JSON)', default='{}')
    is_default = fields.Boolean(string='Dashboard mặc định', default=False)
    is_template = fields.Boolean(string='Là Mẫu (Template)', default=False)
    version = fields.Integer(string='Phiên bản', default=1, readonly=True)

    page_ids = fields.One2many('dynamic.dashboard.page', 'dashboard_id', string='Danh sách trang (Tabs)')
    widget_ids = fields.One2many('dynamic.dashboard.widget', 'dashboard_id', string='Danh sách Widgets')
    filter_ids = fields.One2many('dynamic.dashboard.filter', 'dashboard_id', string='Danh sách Bộ lọc')

    def action_publish(self):
        """Chuyển trạng thái sang Đã xuất bản."""
        for rec in self:
            rec.state = 'published'

    def action_set_draft(self):
        """Chuyển trạng thái về Dự thảo."""
        for rec in self:
            rec.state = 'draft'

    def action_view_dashboard(self):
        """Mở ngay Client Action xem Dashboard."""
        self.ensure_one()
        return {
            'type': 'ir.actions.client',
            'tag': 'action_dashboard_viewer',
            'name': self.name,
            'params': {
                'dashboard_id': self.id,
            }
        }

    def copy(self, default=None):
        default = dict(default or {})
        default.setdefault('name', f"{self.name} (Bản sao)")
        default.setdefault('state', 'draft')
        return super().copy(default)
