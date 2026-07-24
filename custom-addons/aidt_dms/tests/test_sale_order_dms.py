# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).
from odoo.addons.base.tests.common import BaseCommon
from odoo.service.model import call_kw


class TestSaleOrderDms(BaseCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # dms.field.mixin.create() bỏ qua template khi chạy test, trừ khi
        # context test_dms_field được bật. Xem dms_field/models/dms_field_mixin.py.
        cls.env = cls.env(context=dict(cls.env.context, test_dms_field=True))
        cls.storage = cls.env["dms.storage"].create(
            {"name": "AIDT Test Storage", "save_type": "database"}
        )
        cls.access_group = cls.env["dms.access.group"].create(
            {
                "name": "AIDT Test Group",
                "perm_create": True,
                "perm_write": True,
                "perm_unlink": True,
                "explicit_user_ids": [(6, 0, [cls.env.user.id])],
            }
        )
        # install_mode làm dms.field.template tự tạo thư mục gốc của chính nó,
        # là thứ create_dms_directory() sao chép sang từng record.
        cls.template = (
            cls.env["dms.field.template"]
            .with_context(install_mode=True)
            .create(
                {
                    "name": "Sale Order",
                    "storage_id": cls.storage.id,
                    "model_id": cls.env["ir.model"]._get_id("sale.order"),
                    "group_ids": [(6, 0, cls.access_group.ids)],
                    "directory_format_name": "{{object.name}}",
                }
            )
        )
        # dms.field.template.create() (install_mode) creates its own root
        # directory as a *separate* dms.directory record after the template
        # row is inserted. Because dms.directory's "res_id" inverse is a
        # plain Integer (not a Many2one), the ORM cannot auto-invalidate the
        # template's dms_directory_ids cache, which was already primed empty
        # at creation time. Without this, template.dms_directory_ids reads
        # stale (empty), and create_dms_directory() for the sale order fails
        # with "A root directory has to have a storage." OCA's own dms_field
        # tests hit the same gap (see dms_field/tests/test_dms_field.py,
        # e.g. `partner.invalidate_model()`).
        cls.template.invalidate_recordset()
        cls.partner = cls.env["res.partner"].create({"name": "AIDT Test Customer"})

    def test_sale_order_has_dms_directory_field(self):
        self.assertIn("dms_directory_ids", self.env["sale.order"]._fields)

    def test_creating_sale_order_creates_dms_directory(self):
        order = self.env["sale.order"].create({"partner_id": self.partner.id})
        self.assertEqual(len(order.dms_directory_ids), 1)
        directory = order.dms_directory_ids
        self.assertEqual(directory.name, order.name)
        self.assertEqual(directory.storage_id, self.storage)
        self.assertEqual(directory.res_model, "sale.order")
        self.assertEqual(directory.res_id, order.id)

    def test_deleting_sale_order_removes_dms_directory(self):
        order = self.env["sale.order"].create({"partner_id": self.partner.id})
        directory = order.dms_directory_ids
        self.assertTrue(directory.exists())
        order.unlink()
        self.assertFalse(directory.exists())

    def test_create_via_call_kw_dispatch(self):
        # Regression: the create() override must carry @api.model_create_multi
        # so that the RPC/external-API dispatch path (odoo.service.model.call_kw,
        # used by XML-RPC / JSON-RPC / call_kw-based JS orm.create) works.
        # Without the decorator, create._api_model is unset, so call_kw takes
        # the "has ids" branch and tries `model.browse(vals_dict)` instead of
        # calling create() with the vals, raising a TypeError.
        # call_kw() replaces (not merges) the recordset's context with
        # kwargs["context"], mirroring real RPC calls, so we must pass the
        # test_dms_field flag explicitly here for the dms directory to be
        # created the same way the other tests in this class expect.
        order_id = call_kw(
            self.env["sale.order"],
            "create",
            [{"partner_id": self.partner.id}],
            {"context": {"test_dms_field": True}},
        )
        self.assertIsInstance(order_id, int)
        order = self.env["sale.order"].browse(order_id)
        self.assertTrue(order.exists())
        self.assertEqual(len(order.dms_directory_ids), 1)
