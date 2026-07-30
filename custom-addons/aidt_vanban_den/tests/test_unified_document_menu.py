from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestUnifiedDocumentMenu(TransactionCase):

    def test_unified_root_menu_exists(self):
        """Verify that the unified root menu 'Văn bản' exists and is active."""
        unified_menu = self.env.ref('aidt_vanban_den.menu_aidt_document_unified_root', raise_if_not_found=False)
        self.assertTrue(unified_menu, "Unified root menu 'menu_aidt_document_unified_root' should exist.")
        self.assertTrue(unified_menu.active, "Unified root menu should be active.")
        self.assertEqual(unified_menu.name, "Văn bản")
        self.assertFalse(unified_menu.parent_id, "Unified root menu should not have a parent menu.")

    def test_legacy_root_menus_deactivated(self):
        """Verify that legacy 'Văn bản đến' and 'Văn bản đi' root menus are deactivated."""
        legacy_den_root = self.env.ref('aidt_vanban_den.menu_vanban_den_root', raise_if_not_found=False)
        self.assertTrue(legacy_den_root, "Legacy root menu 'menu_vanban_den_root' should exist.")
        self.assertFalse(legacy_den_root.active, "Legacy root menu 'menu_vanban_den_root' should be deactivated (active=False).")

        legacy_di_root = self.env.ref('aidt_vanban_di.menu_vanban_di_root', raise_if_not_found=False)
        self.assertTrue(legacy_di_root, "Legacy root menu 'menu_vanban_di_root' should exist.")
        self.assertFalse(legacy_di_root.active, "Legacy root menu 'menu_vanban_di_root' should be deactivated (active=False).")

    def test_reparented_submenus_active_under_unified_root(self):
        """Verify that sub-menus for incoming, outgoing, and register are under unified root menu hierarchy."""
        unified_root = self.env.ref('aidt_vanban_den.menu_aidt_document_unified_root')

        # Categories under unified root
        den_cate = self.env.ref('aidt_vanban_den.menu_vanban_den_cate', raise_if_not_found=False)
        di_cate = self.env.ref('aidt_vanban_den.menu_vanban_di_cate', raise_if_not_found=False)
        so_cate = self.env.ref('aidt_vanban_den.menu_so_vanban_cate', raise_if_not_found=False)

        self.assertTrue(den_cate and den_cate.active and den_cate.parent_id == unified_root, "Văn bản đến category should be active under unified root.")
        self.assertTrue(di_cate and di_cate.active and di_cate.parent_id == unified_root, "Văn bản đi category should be active under unified root.")
        self.assertTrue(so_cate and so_cate.active and so_cate.parent_id == unified_root, "Sổ Văn bản category should be active under unified root.")

        # Check submenus for Văn bản đến
        den_all = self.env.ref('aidt_vanban_den.menu_vanban_den_all')
        self.assertTrue(den_all.active)
        self.assertEqual(den_all.parent_id, den_cate)

        # Check submenus for Văn bản đi
        di_tat_ca = self.env.ref('aidt_vanban_di.menu_vanban_di_tat_ca')
        self.assertTrue(di_tat_ca.active)
        self.assertEqual(di_tat_ca.parent_id, di_cate)

        # Check submenus for Sổ Văn bản
        so_den = self.env.ref('aidt_vanban_den.menu_so_vanban_den')
        self.assertTrue(so_den.active)
        self.assertEqual(so_den.parent_id, so_cate)
