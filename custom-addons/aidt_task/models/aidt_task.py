from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError

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

    @api.constrains('secrecy', 'document_id')
    def _check_secrecy_floor(self):
        """Nhiệm vụ trích/dẫn văn bản nguồn KHÔNG được kém mật hơn văn bản đó —
        chặn rò rỉ nội dung mật qua trích yếu/đoạn nguồn (N-04/V-13). Sàn độ mật,
        vẫn cho đặt cao hơn. Fires cả create lẫn write."""
        for task in self:
            doc = task.document_id
            if doc and task.secrecy_level < doc.secrecy_level:
                raise ValidationError(self.env._(
                    'Độ mật của nhiệm vụ (%(t)s) không được thấp hơn văn bản '
                    'nguồn "%(d)s" (%(ds)s).',
                    t=dict(_SECRECY_SELECTION).get(task.secrecy),
                    d=doc.name,
                    ds=dict(_SECRECY_SELECTION).get(doc.secrecy)))

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

    def write(self, vals):
        header_fields = {'name', 'document_id', 'source_quote', 'source_ref', 'department_id',
                         'collaborator_department_ids', 'assignee_id', 'assigner_id', 'deadline',
                         'deadline_note', 'secrecy'}
        for task in self:
            if set(vals.keys()) & header_fields:
                if task.state in ('pending_review', 'done', 'on_hold'):
                    raise UserError("Thông tin giao việc của nhiệm vụ ở trạng thái '%s' đã bị khóa. Không thể điều chỉnh." % task.state)
                elif task.state == 'in_progress':
                    is_admin_or_assigner = self.env.is_admin() or (task.assigner_id and task.assigner_id == self.env.user)
                    if not is_admin_or_assigner:
                        raise UserError("Chỉ người giao nhiệm vụ mới có quyền điều chỉnh thông tin phân công khi nhiệm vụ đang thực hiện.")
            if 'result_ids' in vals:
                if task.state == 'new':
                    raise UserError("Nhiệm vụ ở trạng thái 'Mới' (chưa nhấn Bắt đầu). Vui lòng nhấn 'Bắt đầu' trước khi nhập báo cáo kết quả.")
                elif task.state in ('pending_review', 'done', 'on_hold'):
                    raise UserError("Nhiệm vụ ở trạng thái '%s' đã bị khóa. Không thể chỉnh sửa báo cáo kết quả." % task.state)
        return super().write(vals)

    def action_submit_review(self):
        for task in self:
            if not task.result_ids:
                raise UserError("Vui lòng nhập Báo cáo kết quả xử lý trong tab 'Báo cáo kết quả' trước khi gửi duyệt.")
        self.write({'state': 'pending_review'})

    def action_approve(self):
        """Duyệt đóng nhiệm vụ — chỉ người giao (assigner_id) hoặc Admin được duyệt."""
        for task in self:
            if not task.assigner_id:
                raise UserError('Nhiệm vụ chưa có người giao. Không thể duyệt đóng.')
            is_admin_or_assigner = self.env.is_admin() or (task.assigner_id == self.env.user)
            if not is_admin_or_assigner:
                raise UserError(
                    'Chỉ người giao (%s) mới được duyệt đóng nhiệm vụ này.'
                    % (task.assigner_id.name or '—'))
        self.write({'state': 'done'})

        # Tự động cập nhật trạng thái Văn bản nguồn khi tất cả Nhiệm vụ thuộc Văn bản đó đã Hoàn thành
        for task in self:
            doc = task.document_id
            if doc and doc.direction == 'den' and doc.state == 'dang_xu_ly':
                remaining_tasks = doc.task_ids.filtered(lambda t: t.state != 'done')
                if not remaining_tasks:
                    doc.write({'state': 'hoan_thanh'})
                    doc.message_post(body="Tất cả nhiệm vụ thuộc văn bản này đã được duyệt hoàn thành. Văn bản tự động chuyển sang trạng thái Hoàn thành.")

    def action_reject(self):
        """Trả lại để làm tiếp."""
        self.write({'state': 'in_progress'})

    def action_hold(self):
        self.write({'state': 'on_hold'})

    # --- Nhắc việc (T-11) & cảnh báo lãnh đạo (T-14) ---

    def _ensure_reminder_activity(self, label):
        """Tạo 1 mail.activity nhắc hạn cho người thực hiện, không trùng.
        Idempotent theo (nhiệm vụ, nhãn mốc): mỗi mốc 7/3/1/quá-hạn tạo 1 lần."""
        self.ensure_one()
        if not self.assignee_id:
            return
        Activity = self.env['mail.activity']
        summary = 'Nhắc hạn nhiệm vụ: %s' % label
        existing = Activity.search([
            ('res_model', '=', 'aidt.task'),
            ('res_id', '=', self.id),
            ('summary', '=', summary),
            ('user_id', '=', self.assignee_id.id),
        ], limit=1)
        if existing:
            return
        Activity.create({
            'res_model_id': self.env['ir.model']._get_id('aidt.task'),
            'res_id': self.id,
            'activity_type_id': self.env.ref('mail.mail_activity_data_todo').id,
            'summary': summary,
            'note': self.name,
            'date_deadline': self.deadline,
            'user_id': self.assignee_id.id,
        })

    @api.model
    def _cron_deadline_reminders(self):
        """Cron hằng ngày: làm mới is_overdue theo ngày hôm nay, rồi nhắc trước
        hạn 7/3/1 ngày và khi quá hạn."""
        today = fields.Date.context_today(self)

        # is_overdue là field stored phụ thuộc deadline/state — KHÔNG phụ thuộc
        # "hôm nay", nên phải ép tính lại hằng ngày để dashboard tile + digest
        # lãnh đạo (quét is_overdue) không bỏ sót nhiệm vụ vừa quá hạn qua đêm.
        to_refresh = self.search([
            ('state', '!=', 'done'), ('deadline', '!=', False)])
        to_refresh._compute_overdue()
        to_refresh.flush_recordset(['is_overdue'])

        tasks = self.search([
            ('state', 'not in', ('done', 'on_hold')),
            ('deadline', '!=', False),
            ('assignee_id', '!=', False),
        ])
        for task in tasks:
            delta = (task.deadline - today).days
            if delta in (7, 3, 1):
                task._ensure_reminder_activity('còn %d ngày' % delta)
            elif delta < 0:
                task._ensure_reminder_activity('quá hạn')

    @api.model
    def _cron_leader_overdue_digest(self):
        """Cron hàng tuần: gộp nhiệm vụ quá hạn theo đơn vị, gửi Chánh VP."""
        overdue = self.search([('is_overdue', '=', True)])
        if not overdue:
            return
        leaders = self.env.ref('aidt_org.group_chanh_vp').user_ids.filtered(
            'email')
        if not leaders:
            return
        lines = []
        for dept in overdue.mapped('department_id'):
            count = len(overdue.filtered(lambda t: t.department_id == dept))
            lines.append('<li><b>%s</b>: %d nhiệm vụ quá hạn</li>'
                         % (dept.name, count))
        body = ('<p>Danh sách nhiệm vụ quá hạn tính đến hôm nay:</p>'
                '<ul>%s</ul>' % ''.join(lines))
        self.env['mail.mail'].create({
            'subject': 'Cảnh báo: %d nhiệm vụ quá hạn' % len(overdue),
            'body_html': body,
            'email_to': ','.join(leaders.mapped('email')),
        })
