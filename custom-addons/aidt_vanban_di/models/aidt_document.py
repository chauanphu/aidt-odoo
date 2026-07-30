from odoo import api, fields, models
from odoo.exceptions import UserError

class AidtDocument(models.Model):
    _inherit = 'aidt.document'

    state = fields.Selection(
        selection_add=[
            ('cho_duyet_tp', 'Chờ duyệt TP'),
            ('cho_duyet_cvp', 'Chờ duyệt CVP'),
            ('cho_duyet_lanh_dao', 'Chờ duyệt Lãnh đạo'),
            ('cho_ky', 'Chờ ký'),
            ('cho_cap_so', 'Chờ cấp số'),
            ('da_ban_hanh', 'Đã ban hành'),
        ],
        ondelete={
            'cho_duyet_tp': 'set default',
            'cho_duyet_cvp': 'set default',
            'cho_duyet_lanh_dao': 'set default',
            'cho_ky': 'set default',
            'cho_cap_so': 'set default',
            'da_ban_hanh': 'set default',
        },
    )

    so_ky_hieu = fields.Char('Số/Ký hiệu phát hành', readonly=True, copy=False)
    nguoi_soan_id = fields.Many2one('res.users', string='Người soạn', default=lambda self: self.env.user)
    template_id = fields.Many2one('aidt.document.template', string='Mẫu văn bản')

    @api.onchange('template_id')
    def _onchange_template_id(self):
        if self.template_id and self.template_id.doc_type and not self.doc_type:
            self.doc_type = self.template_id.doc_type

    
    nguoi_duyet_tp_id = fields.Many2one('res.users', string='Trưởng phòng duyệt', tracking=True)
    y_kien_tp = fields.Text('Ý kiến TP')
    ngay_duyet_tp = fields.Datetime('Ngày duyệt TP', readonly=True)
    
    nguoi_duyet_cvp_id = fields.Many2one('res.users', string='CVP duyệt', tracking=True)
    y_kien_cvp = fields.Text('Ý kiến CVP')
    ngay_duyet_cvp = fields.Datetime('Ngày duyệt CVP', readonly=True)
    
    nguoi_duyet_lanh_dao_id = fields.Many2one('res.users', string='Lãnh đạo duyệt', tracking=True)
    y_kien_lanh_dao = fields.Text('Ý kiến Lãnh đạo')
    ngay_duyet_lanh_dao = fields.Datetime('Ngày duyệt Lãnh đạo', readonly=True)
    
    nguoi_ky_id = fields.Many2one('res.users', string='Người ký')
    ngay_ky = fields.Datetime('Ngày ký', readonly=True)
    
    noi_nhan = fields.Text('Nơi nhận', help='Danh sách nơi nhận, mỗi dòng 1 đơn vị')
    so_ban_phat_hanh = fields.Integer('Số bản phát hành', default=1)
    
    format_ok = fields.Boolean('Thể thức đạt', default=False, readonly=True)
    format_note = fields.Text('Ghi chú thể thức', readonly=True)

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if res.get('direction') == 'di':
            res['state'] = 'draft'
        return res

    def action_submit_tp(self):
        """Chuyên viên trình Trưởng phòng."""
        for rec in self:
            if rec.direction != 'di':
                continue
            if not rec.file_count:
                raise UserError("Chưa đính kèm file dự thảo.")
            rec.state = 'cho_duyet_tp'

    def action_approve_tp(self):
        """Trưởng phòng duyệt."""
        allowed_groups = ['aidt_org.group_truong_phong', 'aidt_org.group_aidt_admin']
        if not any(self.env.user.has_group(g) for g in allowed_groups):
            raise UserError("Bạn không có quyền duyệt với vai trò Trưởng phòng.")
        for rec in self:
            if rec.direction != 'di':
                continue
            rec.write({
                'state': 'cho_duyet_cvp',
                'nguoi_duyet_tp_id': self.env.uid,
                'ngay_duyet_tp': fields.Datetime.now(),
            })

    def action_reject_tp(self):
        """TP trả về chuyên viên."""
        self.filtered(lambda r: r.direction == 'di').write({'state': 'draft'})

    def action_approve_cvp(self):
        """CVP duyệt."""
        allowed_groups = ['aidt_org.group_chanh_vp', 'aidt_org.group_aidt_admin']
        if not any(self.env.user.has_group(g) for g in allowed_groups):
            raise UserError("Bạn không có quyền duyệt với vai trò Chánh văn phòng.")
        for rec in self:
            if rec.direction != 'di':
                continue
            rec.write({
                'state': 'cho_duyet_lanh_dao',
                'nguoi_duyet_cvp_id': self.env.uid,
                'ngay_duyet_cvp': fields.Datetime.now(),
            })

    def action_reject_cvp(self):
        """CVP trả về TP."""
        self.filtered(lambda r: r.direction == 'di').write({'state': 'cho_duyet_tp'})

    def action_approve_lanh_dao(self):
        """Lãnh đạo duyệt nội dung."""
        allowed_groups = ['aidt_org.group_bi_thu', 'aidt_org.group_pho_bi_thu', 'aidt_org.group_aidt_admin']
        if not any(self.env.user.has_group(g) for g in allowed_groups):
            raise UserError("Bạn không có quyền duyệt với vai trò Lãnh đạo.")
        for rec in self:
            if rec.direction != 'di':
                continue
            rec.write({
                'state': 'cho_ky',
                'nguoi_duyet_lanh_dao_id': self.env.uid,
                'ngay_duyet_lanh_dao': fields.Datetime.now(),
            })

    def action_reject_lanh_dao(self):
        """Lãnh đạo trả về CVP."""
        self.filtered(lambda r: r.direction == 'di').write({'state': 'cho_duyet_cvp'})

    def action_sign(self):
        """Ký số (placeholder MVP — just records who signed and when)."""
        allowed_groups = ['aidt_org.group_bi_thu', 'aidt_org.group_pho_bi_thu', 'aidt_org.group_aidt_admin']
        if not any(self.env.user.has_group(g) for g in allowed_groups):
            raise UserError("Bạn không có quyền thực hiện ký số.")
        for rec in self:
            if rec.direction != 'di':
                continue
            rec.write({
                'state': 'cho_cap_so',
                'nguoi_ky_id': self.env.uid,
                'ngay_ky': fields.Datetime.now(),
            })

    def action_issue_vbd(self):
        """Văn thư cấp số ký hiệu → ban hành."""
        allowed_groups = ['aidt_org.group_van_thu', 'aidt_org.group_aidt_admin']
        if not any(self.env.user.has_group(g) for g in allowed_groups):
            raise UserError("Bạn không có quyền cấp số và ban hành văn bản.")
        for rec in self:
            if rec.direction != 'di':
                continue
            if not rec.so_ky_hieu:
                seq_code = ('aidt.vanban.di.mat'
                            if rec.secrecy != 'thuong'
                            else 'aidt.vanban.di.thuong')
                rec.so_ky_hieu = self.env['ir.sequence'].next_by_code(seq_code)
            rec.write({
                'state': 'da_ban_hanh',
                'date': fields.Date.today(),
            })

