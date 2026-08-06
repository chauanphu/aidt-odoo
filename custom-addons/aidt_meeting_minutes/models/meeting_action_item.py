from odoo import fields, models


class AidtMeetingActionItem(models.Model):
    _name = 'aidt.meeting.action.item'
    _description = 'Meeting Action Item'

    recording_id = fields.Many2one('aidt.meeting.recording', string='Bản ghi', ondelete='cascade')
    task = fields.Text(string='Công việc')
    owner = fields.Char(string='Người phụ trách')
    deadline = fields.Char(string='Thời hạn')
    priority = fields.Selection([('high', 'Cao'), ('medium', 'Trung bình'), ('low', 'Thấp')], string='Mức độ', default='medium')
    timestamp = fields.Char(string='Thời gian trong file')
