import { Thread } from "@mail/core/common/thread_model";

import { patch } from "@web/core/utils/patch";

// Không import gì từ discuss_app_model_patch.js: chỉ cần trường
// `aidtMeetings` mà patch kia gắn lên DiscussApp, không cần hằng số id.
patch(Thread.prototype, {
    _computeDiscussAppCategory() {
        // Phòng họp trước đây rơi vào "Tin nhắn trực tiếp", vì
        // `_create_group()` đặt channel_type='group' và upstream gom cả
        // `group` lẫn `chat` vào đó
        // (addons/mail/.../thread_model_patch.js:58-68).
        //
        // `parent_channel_id` phải nhường cho super(): kênh con không bao
        // giờ hiện thành mục riêng trong thanh bên.
        if (!this.parent_channel_id && this.aidt_is_meeting_room) {
            return this.store.discuss.aidtMeetings;
        }
        return super._computeDiscussAppCategory(...arguments);
    },
});
