import odoo.tests
from odoo.addons.web.tests.test_js import unit_test_error_checker


@odoo.tests.tagged('post_install', '-at_install', 'aidt_meeting_js')
class AidtMeetingJsSuite(odoo.tests.HttpCase):
    """Chạy bộ test hoot của module trong Chrome thật.

    `browser_js` tự SKIP (không FAIL) khi thiếu Chrome hoặc thiếu
    `websocket-client` — đã kiểm chứng: `odoo/tests/common.py` ném
    `unittest.SkipTest` ở cả hai đường. Vì vậy file này an toàn ở môi
    trường không có trình duyệt, và ở môi trường có thì nó là cách duy
    nhất khiến `static/tests/*.test.js` thực sự chạy (qua runner hoot,
    trình biên dịch QWeb của Owl và DOM thật) thay vì chỉ được đọc.

    Yêu cầu trong container odoo: `chromium` và `pip install
    websocket-client`. Xem README.md, mục "Chạy test".
    """

    @odoo.tests.no_retry
    def test_unit_aidt_meeting(self):
        # `id` là hash tất định của tên suite gốc '@aidt_meeting_minutes'
        # (thuật toán ở web/tests/test_js.py::HOOTCommon._generate_hash).
        # Lọc như vậy để không kéo theo cả bộ test của web.
        self.browser_js(
            '/web/tests?headless&loglevel=2&preset=desktop&timeout=15000'
            '&id=c2929794',
            "", "", login='admin', timeout=900,
            success_signal="[HOOT] Test suite succeeded",
            error_checker=unit_test_error_checker)
