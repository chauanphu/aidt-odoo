import { fields } from "@mail/core/common/record";
import { DiscussApp } from "@mail/core/public_web/discuss_app_model";

import { _t } from "@web/core/l10n/translation";
import { patch } from "@web/core/utils/patch";

/** Id của mục, dùng chung với thread_model_patch.js và test. */
export const MEETINGS_CATEGORY_ID = "aidt_meeting_minutes.category_meetings";

// Danh sách mục trong thanh bên KHÔNG phải mảng cứng — nó là
// `store.discuss.allCategories`, tập record phía client. Thêm một mục là
// patch `DiscussApp`, đúng cách `im_livechat` đã làm cho hai mục của nó
// (addons/im_livechat/static/src/core/public_web/discuss_app_model_patch.js).
patch(DiscussApp.prototype, {
    setup() {
        super.setup(...arguments);
        this.aidtMeetings = fields.One("DiscussAppCategory", {
            compute() {
                return {
                    canView: false,
                    extraClass: "o-aidt-DiscussSidebarCategory-meeting",
                    // Người chưa có phòng họp nào thì không thấy mục này.
                    hideWhenEmpty: true,
                    icon: "fa fa-video-camera",
                    id: MEETINGS_CATEGORY_ID,
                    name: _t("Họp"),
                    // Giữa "Kênh" (10) và "Tin nhắn trực tiếp" (30).
                    sequence: 20,
                    // KHÔNG có `serverStateKey`: nó là tuỳ chọn (im_livechat
                    // bỏ nó ở `defaultLivechatCategory`), và dùng nó đòi một
                    // trường mới trên `res.users.settings`. Đổi lại, trạng
                    // thái đóng/mở của mục không được nhớ giữa các phiên —
                    // chấp nhận được, xem spec §5.3.
                };
            },
            eager: true,
        });
    },
});
