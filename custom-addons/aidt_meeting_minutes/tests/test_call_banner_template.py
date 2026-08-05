import re

from lxml import etree

from odoo.tests.common import TransactionCase
from odoo.tools import file_path
from odoo.tools.template_inheritance import apply_inheritance_specs


class TestCallBannerTemplate(TransactionCase):
    """`recording_banner.xml` mở rộng `discuss.Call` bằng `t-inherit` — QWeb
    của Owl không chạy qua ir.ui.view nên không có gì kiểm tra xpath này lúc
    build; một `//PttAdBanner` sai, hoặc `RecordingBanner` chưa đăng ký vào
    `Call.components`, đều là lỗi ÂM THẦM lúc chạy thật (không crash, chỉ
    đơn giản là không có gì được chèn). Hai test dưới đây đóng từng vế:

    - `test_recording_banner_lands_after_ptt_ad_banner` áp đúng cơ chế xpath
      mà Odoo dùng để ghép view (`apply_inheritance_specs`) lên arch gốc
      thật của `discuss.Call`, buộc một xpath sai phải làm bộ test đỏ.
    - `test_recording_banner_registered_in_call_components` là kiểm tra
      TĨNH trên mã nguồn (không thực thi JS thật): xác nhận `call_patch.js`
      còn gán `RecordingBanner` vào `Call.components`. Không thay được một
      lần chạy JS thật, nhưng bắt được đúng lỗi hồi quy hay gặp nhất — xoá
      hoặc sửa nhầm dòng đăng ký.
    """

    def test_recording_banner_lands_after_ptt_ad_banner(self):
        call_template = etree.parse(
            file_path('mail/static/src/discuss/call/common/call.xml')
        ).xpath("//t[@t-name='discuss.Call']")[0]

        [xpath_spec] = etree.parse(
            file_path(
                'aidt_meeting_minutes/static/src/recording_banner.xml')
        ).xpath(
            "//t[@t-name='aidt_meeting_minutes.CallBanner']/xpath")

        result = apply_inheritance_specs(call_template, xpath_spec)

        ptt_banners = result.xpath('.//PttAdBanner')
        self.assertEqual(
            len(ptt_banners), 1,
            'PttAdBanner phải còn nguyên trong template gốc sau khi ghép.')
        following = ptt_banners[0].getnext()
        self.assertIsNotNone(
            following, 'Phải có phần tử ngay sau PttAdBanner.')
        self.assertEqual(
            following.tag, 'RecordingBanner',
            'RecordingBanner phải nằm NGAY SAU PttAdBanner — xpath '
            '"//PttAdBanner" position="after" trong recording_banner.xml '
            'phải khớp đúng chỗ này trong call.xml thật.')

    def test_recording_banner_registered_in_call_components(self):
        """QWeb chỉ render được thẻ `<RecordingBanner/>` (test ở trên) nếu
        component đó có mặt trong `Call.components` — việc đó nằm ở
        `call_patch.js`, một file JS mà test Python không thực thi được.
        Đây là lưới an toàn RẺ NHẤT: đọc thẳng mã nguồn và đảm bảo dòng gán
        vẫn còn đó và vẫn nhắc tới `RecordingBanner`."""
        source = open(file_path(
            'aidt_meeting_minutes/static/src/call_patch.js'),
            encoding='utf-8').read()
        self.assertIsNotNone(
            re.search(r'Call\.components\s*=\s*\{[^}]*RecordingBanner[^}]*\}',
                       source),
            'call_patch.js phải gán RecordingBanner vào Call.components — '
            'nếu không, xpath ở test trên vẫn ghép được vào arch nhưng QWeb '
            'sẽ không biết render thẻ <RecordingBanner/> bằng component nào.')
