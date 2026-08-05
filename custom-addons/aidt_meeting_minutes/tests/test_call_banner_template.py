from lxml import etree

from odoo.tests.common import TransactionCase
from odoo.tools import file_path
from odoo.tools.template_inheritance import apply_inheritance_specs


class TestCallBannerTemplate(TransactionCase):
    """`recording_banner.xml` mở rộng `discuss.Call` bằng `t-inherit` — QWeb
    của Owl không chạy qua ir.ui.view nên không có gì kiểm tra xpath này lúc
    build; một `//PttAdBanner` sai, hoặc `RecordingBanner` chưa đăng ký vào
    `Call.components`, đều là lỗi ÂM THẦM lúc chạy thật (không crash, chỉ
    đơn giản là không có gì được chèn). Test này áp đúng cơ chế xpath mà
    Odoo dùng để ghép view (`apply_inheritance_specs`) lên arch gốc thật của
    `discuss.Call`, và buộc một xpath sai phải làm bộ test đỏ thay vì im
    lặng."""

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
