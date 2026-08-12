import { describe, expect, test } from "@odoo/hoot";
import {
    click,
    contains,
    defineMailModels,
    openDiscuss,
    start,
} from "@mail/../tests/mail_test_helpers";
import { mockService } from "@web/../tests/web_test_helpers";

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
    const actions = captureMeetingActions();
    await start();
    await openDiscuss();
    await click(".o-aidt-add-meeting");
    expect(actions).toHaveLength(1);
    const action = actions[0];
    expect(action.type).toBe("ir.actions.act_window");
    expect(action.target).toBe("new");
    expect(action.context.default_aidt_has_room).toBe(true);
    // Định dạng server chờ đợi: "YYYY-MM-DD HH:MM:SS", KHÔNG phải ISO có
    // hậu tố múi giờ. Sai định dạng thì Odoo đọc lệch giờ mà không báo lỗi.
    expect(action.context.default_start).toMatch(
        /^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$/
    );
    expect(action.context.default_stop).toMatch(
        /^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$/
    );
    expect(action.context.default_stop > action.context.default_start).toBe(true);
});
