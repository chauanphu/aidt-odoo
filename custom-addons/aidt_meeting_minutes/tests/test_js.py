import logging
import re

import odoo.tests
from odoo.addons.web.tests.test_js import unit_test_error_checker

# Tên suite gốc mà hoot sinh ra từ đường dẫn module của các file
# `static/tests/*.test.js` (xem `module_set.hoot.js::getSuitePath`).
SUITE = '@aidt_meeting_minutes'

# Số test JS phải chạy. Đây KHÔNG phải số trang trí: hoot vẫn in
# "[HOOT] Test suite succeeded" khi bộ lọc `id` không khớp suite nào và
# KHÔNG có test nào chạy. Nghĩa là một bộ lọc hỏng sẽ xanh trong khi không
# khẳng định gì cả — đúng loại thành-công-giả mà cả Task 12 sinh ra để dọn.
# Vì vậy phải chốt lại con số và so sánh với dòng tổng kết thật.
EXPECTED_TESTS = 47


_ENDED_RE = re.compile(
    r'\[HOOT\] "' + re.escape(SUITE) + r'" ended \(passed: (\d+)')


class _PassCollector(logging.Handler):
    """Nhặt số test đã chạy từ dòng tổng kết suite trong log trình duyệt."""

    def __init__(self):
        super().__init__(level=logging.NOTSET)
        self.passed = []

    def emit(self, record):
        try:
            message = record.getMessage()
        except Exception:                            # noqa: BLE001
            return
        match = _ENDED_RE.search(message)
        if match:
            self.passed.append(int(match.group(1)))


@odoo.tests.tagged('post_install', '-at_install', 'aidt_meeting_js')
class AidtMeetingJsSuite(odoo.tests.HttpCase):
    """Chạy bộ test hoot của module trong Chrome thật.

    `browser_js` tự SKIP (không FAIL) khi thiếu Chrome hoặc thiếu
    `websocket-client` — đã kiểm chứng: `odoo/tests/common.py` ném
    `unittest.SkipTest` ở cả hai đường. Vì vậy file này an toàn ở môi
    trường không có trình duyệt, và ở môi trường có thì nó là cách duy
    nhất khiến `static/tests/*.test.js` thực sự chạy (qua runner hoot,
    trình biên dịch QWeb của Owl và DOM thật) thay vì chỉ được đọc.

    Ảnh `dev` của Dockerfile đã cài sẵn `chromium` và `websocket-client`.

    Kế thừa `HttpCase`, KHÔNG kế thừa `HOOTCommon` (`addons/web/tests/test_js.py`):
    `HOOTCommon` mang theo BA phương thức test THẬT của chính nó
    (`test_generate_hoot_hash`, `test_get_hoot_filter`, `test_canonical_tags`).
    Kế thừa nó nghĩa là ba bài test của lõi `web` chạy lại dưới tên module
    NÀY — một thay đổi trong thuật toán hash của lõi sẽ được báo cáo như
    aidt_meeting_minutes hỏng, và số test của module bị thổi lên ba đơn vị.
    Thứ duy nhất file này dùng từ đó là `_generate_hash`, 5 dòng, chép lại
    bên dưới.
    """

    def _generate_hash(self, test_string):
        """Bản sao nguyên văn của `HOOTCommon._generate_hash`.

        Phải khớp TỪNG BIT với `hashCode` phía JS (`hoot/core/url.js`), vì
        đây là thứ sinh ra tham số `?id=` lọc suite. Sai một chút thì bộ lọc
        không khớp suite nào, không test JS nào chạy, và hoot vẫn in
        "Test suite succeeded" — xem ghi chú ở `EXPECTED_TESTS`.
        """
        hash = 0
        for char in test_string:
            hash = (hash << 5) - hash + ord(char)
            hash = hash & 0xFFFFFFFF
        return f'{hash:08x}'

    @odoo.tests.no_retry
    def test_unit_aidt_meeting(self):
        # Tính hash Ở THỜI ĐIỂM CHẠY bằng đúng thuật toán của Odoo lõi
        # (`HOOTCommon._generate_hash`), KHÔNG chép cứng chuỗi hash. Chép
        # cứng thì đổi tên suite là bộ lọc trỏ vào hư không, và bài test
        # vẫn xanh — xem ghi chú ở `EXPECTED_TESTS`.
        suite_id = self._generate_hash(SUITE)

        # Bắt dòng tổng kết của hoot bằng một handler logging, KHÔNG bằng
        # `error_checker`: Odoo chỉ gọi `error_checker` cho thông điệp mức
        # LỖI, còn dòng '... ended (passed: N)' là mức INFO nên không bao
        # giờ đi qua đó. (Đã thử cách sai đó trước và bài test này bắt được
        # — đúng việc nó sinh ra để làm.) Log của trình duyệt đi qua logger
        # con '<test>.browser', lan lên logger của module này.
        collector = _PassCollector()
        logger = logging.getLogger(__name__)
        logger.addHandler(collector)
        try:
            self.browser_js(
                '/web/tests?headless&loglevel=2&preset=desktop&timeout=15000'
                f'&id={suite_id}',
                "", "", login='admin', timeout=900,
                success_signal="[HOOT] Test suite succeeded",
                error_checker=unit_test_error_checker)
        finally:
            logger.removeHandler(collector)
        passed = collector.passed

        # Chốt hai điều mà "Test suite succeeded" một mình KHÔNG chốt: suite
        # có tồn tại, và nó chạy đúng số test mong đợi.
        self.assertTrue(
            passed,
            f'Không thấy dòng tổng kết của suite {SUITE!r} — bộ lọc '
            f'id={suite_id} nhiều khả năng không khớp suite nào, nghĩa là '
            f'KHÔNG test JS nào được chạy.')
        self.assertEqual(
            passed[-1], EXPECTED_TESTS,
            f'{SUITE} chạy {passed[-1]} test, mong đợi {EXPECTED_TESTS}. '
            f'Thêm/bớt test JS thì cập nhật EXPECTED_TESTS.')
