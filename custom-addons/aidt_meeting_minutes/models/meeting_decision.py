from odoo import fields, models


class AidtMeetingDecision(models.Model):
    _name = 'aidt.meeting.decision'
    _description = 'Meeting Decision'

    recording_id = fields.Many2one('aidt.meeting.recording', string='Bản ghi', ondelete='cascade')
    content = fields.Text(string='Quyết định')
    timestamp = fields.Char(string='Thời gian trong file')
