from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged('post_install', '-at_install')
class TestCallHost(TransactionCase):
    """Chủ phòng được chốt lúc cuộc gọi bắt đầu.

    Odoo không có khái niệm chủ phòng cho cuộc gọi. Suy ra sau bằng cách tìm
    phiên RTC sớm nhất là không đáng tin: phiên bị xoá rồi tạo lại mỗi lần
    người ta rớt mạng và vào lại, nên "sớm nhất" đổi theo thời gian.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.channel = cls.env['discuss.channel'].create({
            'name': 'Kênh thử chủ phòng',
            'channel_type': 'channel',
        })
        cls.user_a = cls.env['res.users'].create({
            'name': 'Người A', 'login': 'host_a@test.local'})
        cls.user_b = cls.env['res.users'].create({
            'name': 'Người B', 'login': 'host_b@test.local'})
        cls.channel.add_members(
            partner_ids=[cls.user_a.partner_id.id, cls.user_b.partner_id.id])

    def _member(self, user):
        return self.env['discuss.channel.member'].search([
            ('channel_id', '=', self.channel.id),
            ('partner_id', '=', user.partner_id.id),
        ], limit=1)

    def _join(self, user):
        return self.env['discuss.channel.rtc.session'].sudo().create({
            'channel_member_id': self._member(user).id,
        })

    def test_nguoi_vao_dau_tien_thanh_chu_phong(self):
        self._join(self.user_a)
        self.assertEqual(self.channel.aidt_call_host_partner_id,
                         self.user_a.partner_id)

    def test_nguoi_vao_sau_khong_doi_chu_phong(self):
        self._join(self.user_a)
        self._join(self.user_b)
        self.assertEqual(self.channel.aidt_call_host_partner_id,
                         self.user_a.partner_id)

    def test_chu_phong_roi_nhung_con_nguoi_khac_thi_giu_nguyen(self):
        """Rớt mạng vài giây rồi vào lại là chuyện thường. Đổi chủ phòng
        theo mỗi lần đó thì quyền điều khiển nhảy loạn giữa cuộc họp."""
        session_a = self._join(self.user_a)
        self._join(self.user_b)
        session_a.unlink()
        self.assertEqual(self.channel.aidt_call_host_partner_id,
                         self.user_a.partner_id)

    def test_cuoc_goi_trong_thi_xoa_chu_phong(self):
        session_a = self._join(self.user_a)
        session_a.unlink()
        self.assertFalse(self.channel.aidt_call_host_partner_id)
