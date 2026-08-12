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
                    // Không tô vẽ gì — là chỗ bám của test và của người soi
                    // giao diện, đúng lối `o-mail-DiscussSidebarCategory-chat`
                    // của upstream và `-livechat` của im_livechat.
                    extraClass: "o-aidt-DiscussSidebarCategory-meeting",
                    // KHÔNG đặt `hideWhenEmpty`. Mục rỗng vẫn phải hiện, vì
                    // nút "Họp ngay" nằm BÊN TRONG nó: `isVisible` đòi ít
                    // nhất một thread `displayToSelf || isLocallyPinned`
                    // (discuss_app_category_model.js:21-27), nên giấu mục khi
                    // rỗng là giấu lối tạo phòng khỏi đúng người chưa có
                    // phòng nào — người cần nó nhất. Hai mục anh em "Kênh" và
                    // "Tin nhắn trực tiếp" cũng không đặt cờ này; chỉ
                    // im_livechat dùng, và ở đó có lý do khác (không phải ai
                    // cũng có quyền live chat). Quyền tạo họp là mọi người
                    // dùng nội bộ.
                    icon: "fa fa-video-camera",
                    id: MEETINGS_CATEGORY_ID,
                    name: _t("Họp"),
                    // Giữa "Kênh" (10) và "Tin nhắn trực tiếp" (30).
                    sequence: 20,
                    // KHÔNG có `serverStateKey`: nó là tuỳ chọn (im_livechat
                    // bỏ nó ở `defaultLivechatCategory`), và dùng nó đòi một
                    // trường mới trên `res.users.settings`.
                    //
                    // Trạng thái đóng/mở VẪN được nhớ — thiếu
                    // `serverStateKey` thì `saveStateToServer` là false và
                    // `DiscussAppCategory` rơi về `localStateKey` =
                    // `discuss_sidebar_category_<id>_open` trong
                    // localStorage; getter/setter `open` đọc/ghi chính khoá
                    // đó (addons/mail/static/src/discuss/core/public_web/
                    // discuss_app_category_model.js:58-104).
                    //
                    // Cái mất thật sự là ĐỒNG BỘ: nhớ theo trình duyệt chứ
                    // không theo tài khoản, nên người dùng thu mục này lại
                    // rồi đổi máy (hoặc mở cửa sổ ẩn danh) sẽ thấy nó mở lại.
                    // Chấp nhận được, xem spec §5.3.
                };
            },
            eager: true,
        });
    },
});
