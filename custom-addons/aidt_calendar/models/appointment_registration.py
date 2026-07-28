from odoo import fields, models


class AppointmentRegistration(models.Model):
    _name = 'aidt.appointment.registration'
    _description = 'Đăng ký tiếp dân / làm việc'
    _inherit = ['mail.thread']

    name = fields.Char('Họ và tên', required=True)
    identity_card = fields.Char('Số CCCD / MST')
    phone = fields.Char('Số điện thoại', required=True)
    email = fields.Char('Email')
    organization = fields.Char('Cơ quan / Đơn vị')
    content = fields.Text('Nội dung làm việc', required=True)
    preferred_date = fields.Datetime('Thời gian đề xuất', required=True)
    state = fields.Selection([
        ('draft', 'Mới tiếp nhận'),
        ('approved', 'Đã duyệt'),
        ('rejected', 'Từ chối'),
    ], string='Trạng thái', default='draft', tracking=True)
    event_id = fields.Many2one('calendar.event', string='Cuộc họp tạo ra')

    def action_approve(self):
        for reg in self:
            event = self.env['calendar.event'].create({
                'name': f'Tiếp dân: {reg.name} - {reg.content[:50]}',
                'start': reg.preferred_date,
                'stop': reg.preferred_date,
                'appointment_type': 'citizen',
                'description': f'Người đăng ký: {reg.name}\nSĐT: {reg.phone}\nNội dung: {reg.content}',
            })
            reg.write({'state': 'approved', 'event_id': event.id})

    def action_reject(self):
        for reg in self:
            reg.write({'state': 'rejected'})
