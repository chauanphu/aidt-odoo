from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestDemoSecrecy(TransactionCase):
    """N-04 (độ mật) trên dữ liệu demo: người dùng clearance thấp không đọc
    được văn bản/tệp 'tuyệt mật', người dùng clearance cao thì đọc được.

    doc_nv1_01 (aidt_org_demo) = tuyệt mật, thuộc phòng Nghiệp vụ 1 (Ủy ban
    Kiểm tra). post_init_hook của aidt_dms_demo gắn 1 tệp mẫu vào thư mục
    DMS của văn bản này.
    """

    def test_low_clearance_blocked_high_clearance_allowed(self):
        doc = self.env.ref('aidt_org_demo.doc_nv1_01')
        low_user = self.env.ref('aidt_org_demo.user_cv_lyluan')
        high_user = self.env.ref('aidt_org_demo.user_bithu')

        self.assertEqual(doc.secrecy, 'tuyet_mat')
        self.assertEqual(low_user.clearance_level, 0)
        self.assertEqual(high_user.clearance_level, 3)

        # Văn bản: vô hình với người dùng thiếu clearance, hiện với người có
        # đủ clearance (và cùng phạm vi phòng ban, vì bithu ở Tỉnh ủy - cha
        # của Ủy ban Kiểm tra).
        self.assertFalse(
            self.env['aidt.document'].with_user(low_user).search(
                [('id', '=', doc.id)]),
            "Người dùng clearance 0 không được thấy văn bản tuyệt mật.")
        self.assertTrue(
            self.env['aidt.document'].with_user(high_user).search(
                [('id', '=', doc.id)]),
            "Người dùng clearance 3 phải thấy được văn bản tuyệt mật.")

        # Tệp DMS mẫu gắn dưới thư mục của văn bản này (do post_init_hook
        # của aidt_dms_demo tạo) phải kế thừa đúng quy tắc độ mật.
        sample_file = self.env['dms.file'].sudo().search(
            [('directory_id', '=', doc.directory_id.id)], limit=1)
        self.assertTrue(
            sample_file,
            "post_init_hook lẽ ra phải gắn một tệp mẫu vào doc_nv1_01.")

        self.assertFalse(
            self.env['dms.file'].with_user(low_user).search(
                [('id', '=', sample_file.id)]),
            "Người dùng clearance 0 không được thấy tệp tuyệt mật.")
        self.assertTrue(
            self.env['dms.file'].with_user(high_user).search(
                [('id', '=', sample_file.id)]),
            "Người dùng clearance 3 phải thấy được tệp tuyệt mật.")
