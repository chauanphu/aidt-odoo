from odoo import fields, models


class ProjectTask(models.Model):
    _inherit = 'project.task'

    meeting_id = fields.Many2one('calendar.event', string='Từ cuộc họp')
