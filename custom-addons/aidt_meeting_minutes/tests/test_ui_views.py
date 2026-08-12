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
