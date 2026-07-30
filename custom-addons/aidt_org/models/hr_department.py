from odoo import fields, models


class HrDepartment(models.Model):
    _inherit = 'hr.department'

    unit_type = fields.Selection(
        [('cap_uy', 'Cấp ủy'), ('ban', 'Ban'), ('phong', 'Phòng')],
        string='Loại đơn vị',
    )
