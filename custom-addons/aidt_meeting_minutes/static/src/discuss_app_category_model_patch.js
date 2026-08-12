import { DiscussAppCategory } from "@mail/discuss/core/public_web/discuss_app_category_model";
import { compareDatetime } from "@mail/utils/common/misc";

import { patch } from "@web/core/utils/patch";

import { MEETINGS_CATEGORY_ID } from "@aidt_meeting_minutes/discuss_app_model_patch";

// `DiscussAppCategory.sortThreads` chỉ rẽ nhánh cho hai id có sẵn: "channels"
// (theo tên) và "chats" (theo `lastInterestDt`); id nào khác thì hàm trả về
// `undefined`, `Array.sort` hiểu là 0 và mọi phòng đứng yên theo thứ tự chèn
// (addons/mail/static/src/discuss/core/public_web/discuss_app_category_model.js:12-19).
//
// Trước khi có mục "Họp", phòng họp nằm trong `chats` nên được sắp theo
// `lastInterestDt`; tách mục ra mà không khai luật sắp xếp là làm mất luật đó
// — phòng có tin mới không nổi lên đầu nữa, và thứ tự còn đổi sau mỗi lần tải
// lại trang theo thứ tự dữ liệu về. Giữ nguyên luật cũ của `chats`, kể cả
// mốc phụ `t2.id - t1.id` (hai phòng cùng `lastInterestDt` vẫn phải có thứ tự
// ổn định), và dùng đúng `compareDatetime` của upstream.
patch(DiscussAppCategory.prototype, {
    /**
     * @override
     * @param {import("models").Thread} t1
     * @param {import("models").Thread} t2
     */
    sortThreads(t1, t2) {
        if (this.id === MEETINGS_CATEGORY_ID) {
            return compareDatetime(t2.lastInterestDt, t1.lastInterestDt) || t2.id - t1.id;
        }
        return super.sortThreads(...arguments);
    },
});
