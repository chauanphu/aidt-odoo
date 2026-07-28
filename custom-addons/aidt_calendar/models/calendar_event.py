from odoo import api, fields, models
from odoo.exceptions import ValidationError

_SECRECY_LEVEL = {'thuong': 0, 'mat': 1, 'toi_mat': 2, 'tuyet_mat': 3}


class CalendarEvent(models.Model):
    _inherit = 'calendar.event'

    secrecy = fields.Selection([
        ('thuong', 'Thường'),
        ('mat', 'Mật'),
        ('toi_mat', 'Tối mật'),
        ('tuyet_mat', 'Tuyệt mật'),
    ], string='Độ mật', default='thuong', required=True, tracking=True)
    secrecy_level = fields.Integer(
        string='Mức mật', compute='_compute_secrecy_level', store=True, index=True
    )
    document_id = fields.Many2one('aidt.document', string='Văn bản liên quan')
    room_id = fields.Many2one('resource.resource', string='Phòng họp')
    department_id = fields.Many2one('hr.department', string='Đơn vị chủ trì')
    is_weekly_schedule = fields.Boolean('Lịch công tác tuần', default=False)
    appointment_type = fields.Selection([
        ('internal', 'Nội bộ'),
        ('leadership', 'Lịch Cấp ủy'),
        ('citizen', 'Tiếp công dân'),
    ], string='Loại lịch', default='internal')

    @api.depends('secrecy')
    def _compute_secrecy_level(self):
        for event in self:
            event.secrecy_level = _SECRECY_LEVEL.get(event.secrecy, 0)

    @api.constrains('room_id', 'start', 'stop')
    def _check_room_booking_conflict(self):
        for event in self:
            if not event.room_id or not event.start or not event.stop:
                continue
            conflicts = self.search([
                ('id', '!=', event.id),
                ('room_id', '=', event.room_id.id),
                ('start', '<', event.stop),
                ('stop', '>', event.start),
            ])
            if conflicts:
                raise ValidationError(
                    f"Phòng họp '{event.room_id.name}' đã được đăng ký cho cuộc họp khác trong khoảng thời gian này!"
                )

    def action_create_followup_task(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'Nhiệm vụ từ cuộc họp: {self.name}',
            'res_model': 'project.task',
            'view_mode': 'form',
            'target': 'current',
            'context': {
                'default_name': f'Thực hiện kết luận cuộc họp: {self.name}',
                'default_meeting_id': self.id,
                'default_department_id': self.department_id.id if self.department_id else False,
            }
        }

