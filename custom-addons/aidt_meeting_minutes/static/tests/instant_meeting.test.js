import { describe, expect, freezeTime, mockDate, mockTimeZone, test } from "@odoo/hoot";
import {
    click,
    contains,
    defineMailModels,
    openDiscuss,
    start,
} from "@mail/../tests/mail_test_helpers";
import { mockService } from "@web/../tests/web_test_helpers";

import { deserializeDateTime } from "@web/core/l10n/dates";

import "@aidt_meeting_minutes/discuss_app_model_patch";
import "@aidt_meeting_minutes/discuss_app_category_model_patch";
import "@aidt_meeting_minutes/thread_model_patch";
import "@aidt_meeting_minutes/discuss_sidebar_category_patch";

// "desktop" chứ không phải "headless" như các file khác của module: bộ này
// DỰNG THẬT thanh bên Thảo luận rồi bấm vào nút, nên nó cần khung nhìn của
// preset desktop (1366x768) — thanh bên ở khổ mobile là một cây khác.
// `tests/test_js.py` chạy hoot với `preset=desktop`, và preset đó chỉ loại
// thẻ "mobile", nên cả hai loại file vẫn chạy chung một lượt.
describe.current.tags("desktop");
defineMailModels();

/** Bắt lời gọi mở form cuộc họp, để mọi hành động khác đi tiếp như thường.
 *
 * KHÔNG được nuốt hết `doAction`: `openDiscuss()` của bộ trợ giúp mail mở
 * Thảo luận bằng chính dịch vụ này, chặn nó là không có thanh bên nào để bấm.
 */
function captureMeetingActions() {
    const actions = [];
    mockService("action", {
        async doAction(action, options) {
            if (action?.res_model === "calendar.event") {
                actions.push(action);
                return true;
            }
            return super.doAction(action, options);
        },
    });
    return actions;
}

test("mục Họp hiện trong thanh bên cả khi chưa có phòng họp nào", async () => {
    // Bài toán con gà–quả trứng: nút "+" nằm BÊN TRONG mục "Họp", mà mục chỉ
    // được vẽ khi `cat.isVisible` (discuss_sidebar_categories.xml:5). Đặt
    // `hideWhenEmpty: true` là giấu mục khỏi đúng người cần lối tạo nhanh
    // nhất — người chưa từng có phòng họp nào. Hai mục anh em ("Kênh",
    // "Tin nhắn trực tiếp") cũng không đặt cờ đó.
    await start();
    await openDiscuss();
    await contains(".o-aidt-DiscussSidebarCategory-meeting");
});

test("nút Họp ngay nằm trong mục Họp và không nằm ở mục nào khác", async () => {
    await start();
    await openDiscuss();
    await contains(".o-aidt-DiscussSidebarCategory-meeting .o-aidt-add-meeting");
    // Đếm trên TOÀN thanh bên: `actions` là getter chung của mọi
    // `DiscussSidebarCategory`, quên chốt theo id là nút mọc ở cả "Kênh" lẫn
    // "Tin nhắn trực tiếp".
    await contains(".o-aidt-add-meeting", { count: 1 });
});

test("bấm nút mở form cuộc họp với giờ hiện tại và ô phòng đã tích", async () => {
    // Múi giờ LỆCH HẲN so với UTC. Đây là điểm sống còn của bài test: container
    // chạy test có TZ=UTC, nên nếu không ép lệch thì giờ địa phương và giờ UTC
    // trùng nhau và mọi khẳng định về giờ đều vô nghĩa. Server chờ giờ UTC còn
    // người dùng sống ở +7, nên chỉ khẳng định ĐỊNH DẠNG chuỗi là bỏ lọt đúng
    // cái hỏng đáng sợ nhất — cuộc họp đặt lệch 7 tiếng mà không có lỗi nào.
    // Đổi `serializeDateTime(now)` thành `now.toFormat("yyyy-MM-dd HH:mm:ss")`
    // là đúng định dạng nhưng sai mốc, và bài test này phải ĐỎ vì nó.
    mockTimeZone(+7);
    const actions = captureMeetingActions();
    await start();
    await openDiscuss();
    // Chốt đồng hồ SAU khi dựng xong giao diện: `freezeTime()` biến
    // setTimeout/rAF thành no-op nên đóng băng sớm là `start()` treo. Chốt ở
    // đây thì `luxon.DateTime.now()` trong tay nút trả về đúng mốc dưới đây,
    // không cộng thêm mili-giây trôi qua, nên so sánh được TỪNG KÝ TỰ thay
    // vì phải nới một biên độ.
    mockDate("2026-08-12 09:30:00"); // 09:30 UTC, tức 16:30 giờ địa phương
    freezeTime();
    await click(".o-aidt-add-meeting");
    expect(actions).toHaveLength(1);
    const action = actions[0];
    expect(action.type).toBe("ir.actions.act_window");
    expect(action.target).toBe("new");
    expect(action.context.default_aidt_has_room).toBe(true);
    // `calendar.event.name` là trường BẮT BUỘC. Không điền sẵn thì bấm "Họp
    // ngay" rồi bấm Lưu ngay là ăn lỗi kiểm tra ràng buộc.
    expect(String(action.context.default_name)).toBe("Họp ngay");
    // GIỜ UTC, không phải giờ địa phương. 16:30 ở đây là chuỗi mà phép đột
    // biến sinh ra; 09:30 là chuỗi đúng.
    expect(action.context.default_start).toBe("2026-08-12 09:30:00");
    expect(action.context.default_stop).toBe("2026-08-12 10:30:00");
    // Khoảng cách đúng một giờ, đo bằng thời điểm THẬT sau khi đọc ngược hai
    // chuỗi. So sánh chuỗi (`stop > start`) không đo gì cả: nó đúng nhờ may
    // mắn thứ tự từ điển và vẫn xanh khi CẢ HAI cùng lệch múi giờ.
    const start_ = deserializeDateTime(action.context.default_start);
    const stop_ = deserializeDateTime(action.context.default_stop);
    expect(stop_.diff(start_).as("hours")).toBe(1);
});
