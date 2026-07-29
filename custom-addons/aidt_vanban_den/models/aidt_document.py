from odoo import api, fields, models
from odoo.exceptions import UserError

class AidtDocument(models.Model):
    _inherit = 'aidt.document'

    so_den = fields.Char(string='Số đến', readonly=True, copy=False)
    ngay_den = fields.Date(string='Ngày đến', default=fields.Date.context_today)
    co_quan_gui = fields.Char(string='Cơ quan gửi')
    so_ky_hieu_gui = fields.Char(string='Số ký hiệu gốc')
    ngay_ban_hanh_gui = fields.Date(string='Ngày ban hành gốc')
    so_ban = fields.Integer(string='Số bản', default=1)
    do_khan = fields.Selection([
        ('thuong', 'Thường'),
        ('khan', 'Khẩn'),
        ('thuong_khan', 'Thượng khẩn'),
        ('hoa_toc', 'Hỏa tốc'),
    ], string='Độ khẩn', default='thuong', tracking=True)
    
    lanh_dao_but_phe_id = fields.Many2one('res.users', string='Lãnh đạo bút phê')
    y_kien_but_phe = fields.Html(string='Ý kiến chỉ đạo')
    don_vi_chu_tri_id = fields.Many2one('hr.department', string='Đơn vị chủ trì')
    don_vi_phoi_hop_ids = fields.Many2many(
        'hr.department', 
        'aidt_document_phoi_hop_rel', 
        'document_id', 
        'department_id', 
        string='Đơn vị phối hợp'
    )
    han_xu_ly = fields.Date(string='Hạn xử lý')
    is_overdue = fields.Boolean(compute='_compute_is_overdue', store=True)

    state = fields.Selection(
        selection_add=[
            ('tiep_nhan', 'Tiếp nhận'),
            ('da_dang_ky', 'Đã đăng ký'),
            ('trinh_lanh_dao', 'Trình lãnh đạo'),
            ('dang_xu_ly', 'Đang xử lý'),
            ('hoan_thanh', 'Hoàn thành'),
        ],
        ondelete={
            'tiep_nhan': 'set default',
            'da_dang_ky': 'set default',
            'trinh_lanh_dao': 'set default',
            'dang_xu_ly': 'set default',
            'hoan_thanh': 'set default',
        },
    )

    @api.depends('han_xu_ly', 'state')
    def _compute_is_overdue(self):
        today = fields.Date.today()
        for rec in self:
            rec.is_overdue = (
                rec.direction == 'den'
                and rec.han_xu_ly
                and rec.han_xu_ly < today
                and rec.state not in ('hoan_thanh', 'archived', False)
            )

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if res.get('direction') == 'den':
            res['state'] = 'tiep_nhan'
        return res

    def action_register(self):
        """Văn thư cấp số đến."""
        for rec in self:
            if rec.direction != 'den':
                continue
            if not rec.so_den:
                seq_code = ('aidt.vanban.den.mat'
                            if rec.secrecy != 'thuong'
                            else 'aidt.vanban.den.thuong')
                rec.so_den = self.env['ir.sequence'].next_by_code(seq_code)
            rec.state = 'da_dang_ky'

    def action_submit_leader(self):
        """Trình lãnh đạo bút phê."""
        for rec in self:
            if rec.direction != 'den':
                continue
            if not rec.file_count:
                raise UserError("Chưa có tệp đính kèm. Vui lòng upload file scan trước khi trình.")
            rec.state = 'trinh_lanh_dao'

    def action_but_phe(self):
        """Lãnh đạo ghi bút phê + giao đơn vị → auto-create task."""
        for rec in self:
            if rec.direction != 'den':
                continue
            if not rec.don_vi_chu_tri_id:
                raise UserError("Chưa chọn đơn vị chủ trì.")
            rec.state = 'dang_xu_ly'
            # Auto-create task from bút phê (T-01)
            self.env['aidt.task'].create({
                'name': f"Xử lý: {rec.name}",
                'document_id': rec.id,
                'department_id': rec.don_vi_chu_tri_id.id,
                'deadline': rec.han_xu_ly,
                'secrecy': rec.secrecy,
            })

    def action_complete(self):
        """Duyệt hoàn thành."""
        self.filtered(lambda r: r.direction == 'den').write({'state': 'hoan_thanh'})

    @api.model
    def _cron_vanban_den_deadline_reminders(self):
        """Cron hàng ngày kiểm tra hạn xử lý VB Đến và tự tạo mail.activity nhắc nhở."""
        today = fields.Date.today()
        docs = self.search([
            ('direction', '=', 'den'),
            ('state', '=', 'dang_xu_ly'),
            ('han_xu_ly', '!=', False),
        ])
        activity_type = self.env.ref('mail.mail_activity_data_todo', raise_if_not_found=False)
        doc_model = self.env.ref('aidt_org.model_aidt_document', raise_if_not_found=False)
        if not activity_type or not doc_model:
            return

        for doc in docs:
            recipient_user = doc.don_vi_chu_tri_id.manager_id.user_id or doc.lanh_dao_but_phe_id
            if not recipient_user:
                continue

            days_diff = (doc.han_xu_ly - today).days
            if days_diff < 0:
                summary = f"QUÁ HẠN: {doc.so_den or doc.name}"
                note = f"Văn bản '{doc.name}' đã quá hạn xử lý {abs(days_diff)} ngày (Hạn: {doc.han_xu_ly})."
            elif days_diff <= 3:
                summary = f"SẮP HẾT HẠN: {doc.so_den or doc.name}"
                note = f"Văn bản '{doc.name}' còn {days_diff} ngày nữa hết hạn xử lý (Hạn: {doc.han_xu_ly})."
            else:
                continue

            existing = self.env['mail.activity'].search([
                ('res_model', '=', 'aidt.document'),
                ('res_id', '=', doc.id),
                ('user_id', '=', recipient_user.id),
                ('summary', '=', summary),
            ], limit=1)

            if not existing:
                self.env['mail.activity'].create({
                    'activity_type_id': activity_type.id,
                    'summary': summary,
                    'note': note,
                    'res_model_id': doc_model.id,
                    'res_id': doc.id,
                    'user_id': recipient_user.id,
                    'date_deadline': doc.han_xu_ly,
                })

