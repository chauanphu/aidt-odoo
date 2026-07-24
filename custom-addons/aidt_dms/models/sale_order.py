# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).
from odoo import models


class SaleOrder(models.Model):
    _name = "sale.order"
    _inherit = ["sale.order", "dms.field.mixin"]

    def create(self, vals_list):
        records = super().create(vals_list)
        # dms.field.mixin.create() (extra-addons/dms/dms_field/models/
        # dms_field_mixin.py) creates the dms.directory *after* the record
        # has been inserted, as a separate record on a model whose "res_id"
        # inverse field is a plain Integer (not a Many2one). Odoo's ORM can
        # only auto-invalidate a One2many cache when the inverse is a
        # Many2one, so `records.dms_directory_ids` would read back stale
        # (empty) data immediately after create() without this. OCA's own
        # dms_field tests hit the same gap and work around it the same way,
        # e.g. `partner.invalidate_model()` in
        # dms_field/tests/test_dms_field.py.
        records.invalidate_recordset(["dms_directory_ids"])
        return records
