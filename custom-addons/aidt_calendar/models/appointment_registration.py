from datetime import timedelta
import random

from odoo import api, fields, models


class AppointmentRegistration(models.Model):
    _name = 'aidt.appointment.registration'
    _description = 'Đăng ký tiếp dân / làm việc'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc, id desc'

    code = fields.Char('Mã đăng ký', required=True, readonly=True, copy=False, default='New', index=True)
    name = fields.Char('Họ và tên', required=True, tracking=True)
    identity_card = fields.Char('Số CCCD / MST', tracking=True)
    phone = fields.Char('Số điện thoại', required=True, tracking=True)
    email = fields.Char('Email', tracking=True)
    organization = fields.Char('Cơ quan / Đơn vị', tracking=True)
    content = fields.Text('Nội dung làm việc', required=True, tracking=True)
    preferred_date = fields.Datetime('Thời gian đề xuất', required=True, tracking=True)
    state = fields.Selection([
        ('draft', 'Mới tiếp nhận'),
        ('approved', 'Đã duyệt'),
        ('rejected', 'Từ chối'),
    ], string='Trạng thái', default='draft', tracking=True)
    event_id = fields.Many2one('calendar.event', string='Cuộc họp tạo ra', readonly=True)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('code', 'New') == 'New':
                today_str = fields.Date.today().strftime('%Y%m%d')
                rand_num = random.randint(1000, 9999)
                vals['code'] = f"DK-{today_str}-{rand_num}"
        return super().create(vals_list)

    def action_approve(self):
        for reg in self:
            event = self.env['calendar.event'].create({
                'name': f'Tiếp dân: [{reg.code}] {reg.name} - {reg.content[:50]}',
                'start': reg.preferred_date,
                'stop': reg.preferred_date + timedelta(hours=1),
                'appointment_type': 'citizen',
                'is_weekly_schedule': False,
                'partner_ids': [(4, self.env.user.partner_id.id)],
                'description': f'Mã đăng ký: {reg.code}\nNgười đăng ký: {reg.name}\nCCCD/MST: {reg.identity_card or "N/A"}\nSĐT: {reg.phone}\nNội dung: {reg.content}',
            })
            reg.write({'state': 'approved', 'event_id': event.id})
            reg.message_post(body=f"Đã duyệt đăng ký làm việc/tiếp dân. Sự kiện cuộc họp đã được tạo: {event.name}")

    def action_reject(self):
        for reg in self:
            reg.write({'state': 'rejected'})
            reg.message_post(body="Yêu cầu đăng ký làm việc/tiếp dân đã bị từ chối.")

