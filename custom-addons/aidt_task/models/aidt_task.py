from odoo import api, fields, models
from odoo.exceptions import UserError

# Cùng thang với aidt.document (aidt_org): thuong=0 .. tuyet_mat=3
_SECRECY_LEVEL = {'thuong': 0, 'mat': 1, 'toi_mat': 2, 'tuyet_mat': 3}
_SECRECY_SELECTION = [
    ('thuong', 'Thường'), ('mat', 'Mật'),
    ('toi_mat', 'Tối mật'), ('tuyet_mat', 'Tuyệt mật'),
]


class AidtTask(models.Model):
    _name = 'aidt.task'
    _description = 'Nhiệm vụ'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'deadline asc, id desc'

    name = fields.Char(string='Nội dung nhiệm vụ', required=True, tracking=True)

    # Nguồn (T-07): tùy chọn — cho phép nhiệm vụ ad-hoc không có văn bản.
    document_id = fields.Many2one(
        'aidt.document', string='Văn bản nguồn', index=True,
        ondelete='set null', tracking=True)
    source_quote = fields.Text(string='Đoạn trích nguồn')
    source_ref = fields.Char(string='Vị trí đoạn (trang/mục)')

    # Phân công (T-02/03/08/13)
    department_id = fields.Many2one(
        'hr.department', string='Đơn vị chủ trì', required=True, index=True,
        tracking=True)
    collaborator_department_ids = fields.Many2many(
        'hr.department', 'aidt_task_collab_dept_rel', 'task_id', 'dept_id',
        string='Đơn vị phối hợp')
    assignee_id = fields.Many2one(
        'res.users', string='Người thực hiện', tracking=True)
    assigner_id = fields.Many2one(
        'res.users', string='Người giao', tracking=True,
        default=lambda self: self.env.user)

    # Thời hạn (T-04)
    deadline = fields.Date(string='Hạn hoàn thành', tracking=True)
    deadline_note = fields.Char(
        string='Mô tả hạn',
        help='Giữ nguyên câu gốc, ví dụ "trong quý II" — chỗ AI dùng sau.')

    # Vòng đời (T-09). "Quá hạn" KHÔNG phải state — xem is_overdue.
    state = fields.Selection(
        [('new', 'Mới'), ('in_progress', 'Đang thực hiện'),
         ('pending_review', 'Chờ duyệt'), ('done', 'Hoàn thành'),
         ('on_hold', 'Tạm dừng')],
        string='Trạng thái', default='new', required=True, tracking=True)
    is_overdue = fields.Boolean(
        string='Quá hạn', compute='_compute_overdue', store=True,
        help='deadline đã qua và nhiệm vụ chưa hoàn thành. '
             'Được cron làm mới hằng ngày.')

    # Độ mật (N-04): kế thừa từ văn bản nguồn, vẫn cho sửa.
    secrecy = fields.Selection(
        _SECRECY_SELECTION, string='Độ mật', required=True,
        default='thuong', tracking=True)
    secrecy_level = fields.Integer(
        string='Mức mật', compute='_compute_secrecy_level',
        store=True, index=True)

    # Kết quả (T-12)
    result_ids = fields.One2many(
        'aidt.task.result', 'task_id', string='Báo cáo kết quả')
    result_count = fields.Integer(
        string='Số báo cáo', compute='_compute_result_count')

    @api.depends('secrecy')
    def _compute_secrecy_level(self):
        for task in self:
            task.secrecy_level = _SECRECY_LEVEL.get(task.secrecy, 0)

    @api.depends('deadline', 'state')
    def _compute_overdue(self):
        today = fields.Date.context_today(self)
        for task in self:
            task.is_overdue = bool(
                task.deadline and task.deadline < today
                and task.state != 'done')

    @api.depends('result_ids')
    def _compute_result_count(self):
        for task in self:
            task.result_count = len(task.result_ids)

    @api.onchange('document_id')
    def _onchange_document_secrecy(self):
        """UI: chọn văn bản nguồn thì điền sẵn độ mật + đơn vị (vẫn sửa được)."""
        if self.document_id:
            self.secrecy = self.document_id.secrecy
            if not self.department_id:
                self.department_id = self.document_id.department_id

    @api.model_create_multi
    def create(self, vals_list):
        """Kế thừa độ mật/đơn vị từ văn bản nguồn khi tạo bằng ORM
        (demo, sau này là AI) — onchange chỉ chạy ở form UI."""
        for vals in vals_list:
            if vals.get('document_id'):
                doc = self.env['aidt.document'].browse(vals['document_id'])
                if 'secrecy' not in vals:
                    vals['secrecy'] = doc.secrecy
                if not vals.get('department_id'):
                    vals['department_id'] = doc.department_id.id
        return super().create(vals_list)

    # --- Vòng đời (T-09, T-13) ---

    def action_start(self):
        self.write({'state': 'in_progress'})

    def action_submit_review(self):
        self.write({'state': 'pending_review'})

    def action_approve(self):
        """Duyệt đóng nhiệm vụ — chỉ người giao (assigner_id) được duyệt."""
        for task in self:
            if task.assigner_id and task.assigner_id != self.env.user:
                raise UserError(
                    'Chỉ người giao (%s) mới được duyệt đóng nhiệm vụ này.'
                    % task.assigner_id.name)
        self.write({'state': 'done'})

    def action_reject(self):
        """Trả lại để làm tiếp."""
        self.write({'state': 'in_progress'})

    def action_hold(self):
        self.write({'state': 'on_hold'})
