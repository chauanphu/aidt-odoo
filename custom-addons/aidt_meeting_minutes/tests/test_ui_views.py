import os
import xml.etree.ElementTree as ET

try:
    from odoo.tests.common import TransactionCase
except ImportError:
    TransactionCase = object

class TestUIViews(TransactionCase):

    def test_menu_quan_ly_cuoc_hop_nam_trong_thao_luan(self):
        menu = self.env.ref('aidt_meeting_minutes.menu_meeting_management')
        self.assertEqual(
            menu.parent_id, self.env.ref('mail.menu_root_discuss'))
        self.assertEqual(menu.sequence, 3)
        self.assertEqual(menu.action.res_model, 'calendar.event')

    def test_trang_ban_ghi_doi_ten_thanh_lich_su(self):
        menu = self.env.ref('aidt_meeting_minutes.menu_meeting_recording')
        self.assertEqual(menu.name, 'Lịch sử cuộc họp')
        self.assertEqual(menu.sequence, 4)

    def test_cau_hinh_bi_day_xuong_5(self):
        """Giữa 3 và 4 không còn số nguyên nào, nên "Cấu hình" phải xuống 5."""
        self.assertEqual(
            self.env.ref('mail.menu_configuration').sequence, 5)

    def test_thu_tu_that_cua_cac_muc_con_trong_thao_luan(self):
        """Đọc thứ tự THẬT, không chỉ đọc `sequence` của riêng một mục.

        Bốn test kia đều chỉ khẳng định `sequence` của một bản ghi. Chúng
        vẫn xanh khi một menu khác cũng nhảy vào `sequence` 3 rồi chen lên
        TRƯỚC mục của ta — `_order = "sequence,id"` phân giải hoà bằng id,
        tức bằng thứ tự cài module, thứ không có gì bảo đảm. Test này duyệt
        đúng cái danh sách người dùng nhìn thấy.

        Chỉ so năm mục đầu: `mail` còn treo `discuss_technical` ở sequence
        10, và module khác vẫn được quyền thêm mục sau nó.

        `search` để nguyên `active_test`, tức BỎ QUA menu đã tắt — đúng cái
        người dùng nhìn thấy. `mail.discuss_channel_integrations_menu` là một
        ví dụ thật: nó nằm dưới cùng gốc này nhưng `active = False`, nên câu
        SQL thô trả về 7 dòng còn danh sách thật chỉ có 6.
        """
        root = self.env.ref('mail.menu_root_discuss')
        children = self.env['ir.ui.menu'].search([('parent_id', '=', root.id)])
        self.assertEqual(
            children[:5].ids,
            [
                self.env.ref(xmlid).id
                for xmlid in (
                    'mail.main_menu_discuss',
                    'mail.menu_channel',
                    'aidt_meeting_minutes.menu_meeting_management',
                    'aidt_meeting_minutes.menu_meeting_recording',
                    'mail.menu_configuration',
                )
            ],
        )

    def test_action_dung_chung_view_cua_aidt_calendar(self):
        """Không nhân bản view: thêm một trường thì chỉ sửa một chỗ."""
        action = self.env.ref('aidt_meeting_minutes.action_meeting_management')
        view_ids = action.view_ids.mapped('view_id')
        self.assertIn(
            self.env.ref('aidt_calendar.calendar_event_view_list_aidt'),
            view_ids)
        self.assertIn(
            self.env.ref('aidt_calendar.calendar_event_view_kanban_aidt'),
            view_ids)

    def test_quan_ly_cuoc_hop_mo_cho_moi_nguoi_dung_noi_bo(self):
        """Menu này KHÔNG có nhóm quyền, và đó là chủ ý — không phải sót.

        Đặt lịch họp là việc ai cũng làm được ở ứng dụng Lịch; cửa vào từ
        Thảo luận không được hẹp hơn. Không có khẳng định này thì một lần
        "dọn cho nhất quán" gắn `groups` của nhóm quản trị biên bản vào đây
        sẽ lấy mất tính năng của toàn bộ người dùng nội bộ mà cả năm test
        kia vẫn xanh.
        """
        menu = self.env.ref('aidt_meeting_minutes.menu_meeting_management')
        self.assertFalse(menu.group_ids)

    def test_lich_su_cuoc_hop_chi_danh_cho_nhom_quan_tri_bien_ban(self):
        """Mặt còn lại của cùng một chủ ý, và là mặt nguy hiểm hơn.

        Trang này bày bản ghi tiếng và biên bản cuộc họp. Gỡ `groups` khỏi
        nó là mở biên bản cho toàn cơ quan — im lặng, không lỗi, không dấu
        vết. So bằng `assertEqual` chứ không `assertTrue`: đổi sang một
        nhóm rộng hơn cũng phải đỏ.
        """
        menu = self.env.ref('aidt_meeting_minutes.menu_meeting_recording')
        self.assertEqual(
            menu.group_ids,
            self.env.ref('aidt_meeting_minutes.group_meeting_minutes_manager'))

    def test_danh_sach_cuoc_hop_khong_cho_sua_do_mat_hang_loat(self):
        """Cột `Độ mật` phải `readonly` và danh sách không được `multi_edit`.

        `calendar_event_view_list_aidt` nằm im trong CSDL từ lâu nhưng chưa
        bao giờ lên màn hình: hai action còn lại của `calendar.event` đều
        rơi về view list upstream. Chính action này là thứ render nó lần
        đầu — nên chính nó phải gánh khẳng định.

        Kịch bản chặn: chọn-tất-cả 40 cuộc họp, sửa một ô `Độ mật` thành
        `Tuyệt mật`, và cả 40 biến mất khỏi tầm nhìn của mọi người dưới
        clearance 3 (`aidt_calendar.calendar_event_rule_secrecy` là rule
        toàn cục). ACL cho phép, nhưng không trang nào được biến nó thành
        hai cú click.

        Đọc arch qua `get_views` chứ không đọc thẳng `view.arch`: như thế
        khẳng định phủ luôn cả dây nối action -> view, tức vẫn đỏ nếu ai đó
        trỏ action sang một view list khác có `multi_edit`.
        """
        action = self.env.ref('aidt_meeting_minutes.action_meeting_management')
        view = self.env.ref('aidt_calendar.calendar_event_view_list_aidt')
        self.assertEqual(
            [spec for spec in action.views if spec[1] == 'list'],
            [(view.id, 'list')])
        arch = ET.fromstring(
            self.env['calendar.event'].get_views(
                [(view.id, 'list')])['views']['list']['arch'])
        self.assertNotIn('multi_edit', arch.attrib)
        secrecy = arch.find(".//field[@name='secrecy']")
        self.assertIsNotNone(secrecy)
        self.assertEqual(secrecy.get('readonly'), '1')

    def test_menuitem_groups_trong_ma_nguon(self):
        """Đọc thẳng XML, vì bản ghi trong CSDL KHÔNG kể hết câu chuyện.

        `odoo/tools/convert.py:323` — `if groups: values['group_ids'] = groups`.
        Xoá thuộc tính `groups` khỏi một `<menuitem>` đã cài thì lần `-u`
        sau KHÔNG xoá `group_ids` đang có: m2m không phải xml_id mồ côi nên
        không ai dọn nó. Trên `aidt_demo` (CSDL cài từ trước) menu vẫn khoá,
        hai test đọc CSDL ở trên vẫn xanh — nhưng một lần cài MỚI, tức lần
        triển khai thật, sẽ bày biên bản cuộc họp cho toàn cơ quan.

        Nên hai tầng: hai test trên giữ trạng thái đang chạy, test này giữ
        ý định trong mã nguồn. Chỉ một tầng là để hở đúng cái lỗ nguy hiểm
        nhất.
        """
        views = os.path.join(os.path.dirname(__file__), '..', 'views')

        def menuitem(filename, menu_id):
            root = ET.parse(os.path.join(views, filename)).getroot()
            el = root.find(".//menuitem[@id='%s']" % menu_id)
            self.assertIsNotNone(
                el, "Không tìm thấy <menuitem id='%s'>" % menu_id)
            return el

        self.assertIsNone(
            menuitem('calendar_event_views.xml',
                     'menu_meeting_management').get('groups'),
            '"Quản lý cuộc họp" phải mở cho mọi người dùng nội bộ')
        self.assertEqual(
            menuitem('meeting_recording_views.xml',
                     'menu_meeting_recording').get('groups'),
            'aidt_meeting_minutes.group_meeting_minutes_manager',
            '"Lịch sử cuộc họp" phải khoá theo nhóm quản trị biên bản')

def test_xml_premium_layout():
    xml_path = os.path.join(os.path.dirname(__file__), '..', 'views', 'meeting_recording_views.xml')
    tree = ET.parse(xml_path)
    root = tree.getroot()
    
    # Check for the premium container
    container = root.find(".//div[@class='premium-dashboard-container']")
    assert container is not None, "Missing <div class='premium-dashboard-container'>"
    
    # Check for the 50/50 layout (at least two col-md-6)
    col_6_elements = root.findall(".//div[@class='col-md-6']")
    assert len(col_6_elements) >= 2, "Main layout must use col-md-6 for a 50/50 split"

if __name__ == '__main__':
    test_xml_premium_layout()
    print("XML premium layout test passed!")
