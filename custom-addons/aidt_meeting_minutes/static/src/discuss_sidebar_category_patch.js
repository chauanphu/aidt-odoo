import { DiscussSidebarCategory } from "@mail/discuss/core/public_web/discuss_sidebar_categories";

import { serializeDateTime } from "@web/core/l10n/dates";
import { _t } from "@web/core/l10n/translation";
import { patch } from "@web/core/utils/patch";

import { MEETINGS_CATEGORY_ID } from "@aidt_meeting_minutes/discuss_app_model_patch";

// Nút "+" đi qua `actions` — ĐIỂM MỞ RỘNG CHÍNH THỨC của tiêu đề mục, không
// phải qua `t-inherit` vào `mail.DiscussSidebarCategory.main`.
//
// Lý do: upstream đã dành sẵn `get actions()` trên `DiscussSidebarCategory`
// (addons/mail/.../discuss_sidebar_categories.js:224, trả về mảng rỗng) và
// template vẽ chúng ở CẢ HAI chế độ thanh bên — hàng ngang trong tiêu đề khi
// bình thường (discuss_sidebar_categories.xml:51) và danh sách dọc trong
// dropdown nổi khi thu gọn (:26). Chèn tay một `<button class="... ms-auto">`
// vào `div[@name='header']` chỉ hợp bố cục thứ nhất: ở chế độ thu gọn tiêu đề
// đổi class và nút sẽ nằm sai chỗ, chưa kể phải tự lo title/hotkey/icon mà
// upstream đã lo. Hai module lõi mở rộng đúng chỗ này theo cách y hệt:
// `mail/discuss/core/web/discuss_sidebar_categories_patch.js:30` (nút "xem/
// tham gia kênh") và `im_livechat/core/web/discuss_sidebar_category_patch.js:9`.
//
// PHẢI là `DiscussSidebarCategory` (SỐ ÍT, :191) — component mang
// `static template = "mail.DiscussSidebarCategory"` và getter `category` mà
// template đọc. `DiscussSidebarCategories` (SỐ NHIỀU, :241) là component cha
// bọc danh sách; patch vào nó thì template không bao giờ thấy phương thức.
/** @type {import("@mail/discuss/core/public_web/discuss_sidebar_categories").DiscussSidebarCategory} */
patch(DiscussSidebarCategory.prototype, {
    get actions() {
        const actions = super.actions;
        if (this.category.id === MEETINGS_CATEGORY_ID) {
            actions.push({
                onSelect: () => this.onAidtAddMeeting(),
                label: _t("Họp ngay"),
                icon: "fa fa-plus",
                // Lớp CSS này không tô vẽ gì — nó là chỗ bám của test và của
                // người soi giao diện. Đừng đổi tên mà không sửa
                // static/tests/instant_meeting.test.js.
                class: "o-aidt-add-meeting",
            });
        }
        return actions;
    },

    /** Mở form cuộc họp dạng hộp thoại, đã điền sẵn "bắt đầu từ bây giờ".
     *
     * `luxon.DateTime` chứ không phải `Date` thuần: `serializeDateTime` chỉ
     * nhận luxon, và context của Odoo cần chuỗi UTC đúng định dạng
     * "YYYY-MM-DD HH:MM:SS" — truyền `Date` vào sẽ ra chuỗi ISO có hậu tố múi
     * giờ mà server đọc lệch giờ chứ không báo lỗi.
     *
     * `default_aidt_has_room` là trường tính-có-nghịch-đảo của Task 3: đặt nó
     * trong context nghĩa là phòng trong Thảo luận được tạo ngay lúc lưu cuộc
     * họp, không phải một bước riêng.
     */
    onAidtAddMeeting() {
        const now = luxon.DateTime.now();
        this.env.services.action.doAction({
            type: "ir.actions.act_window",
            res_model: "calendar.event",
            views: [[false, "form"]],
            target: "new",
            name: _t("Họp ngay"),
            context: {
                default_start: serializeDateTime(now),
                default_stop: serializeDateTime(now.plus({ hours: 1 })),
                default_aidt_has_room: true,
            },
        });
    },
});
