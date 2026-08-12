import { MessagingMenu } from "@mail/core/public_web/messaging_menu";

import { patch } from "@web/core/utils/patch";

// Khay tin nhắn đếm và liệt kê theo HAI cách khác nhau, và việc tách phòng
// họp ra mục riêng làm hai cách đó lệch nhau:
//
//   * DANH SÁCH trong tab lọc theo `channel_type`: `store.menuThreads` gọi
//     `tabToThreadType(tab)` và tab "chat" nhận `['chat', 'group']`
//     (addons/mail/static/src/core/common/store_service.js:184 và :399).
//     Phòng họp vẫn là `channel_type='group'` — `_create_videocall_channel`
//     gọi `_create_group()` — nên nó VẪN nằm trong danh sách tab "Chats".
//   * BỘ ĐẾM lại đếm theo MỤC thanh bên:
//     `store.discuss.chats.threadsWithCounter.length`
//     (addons/mail/static/src/core/public_web/messaging_menu.js:160). Từ khi
//     phòng họp rời mục `chats`, nó không còn được đếm.
//
// Hậu quả là mất chỉ báo chưa đọc, không phải lỗi thẩm mỹ: người chỉ có một
// phòng họp với tin chưa đọc mở khay tin nhắn ra thấy tab "Chats" KHÔNG có
// huy hiệu, nhưng bên trong lại có một dòng in đậm chưa đọc.
//
// Sửa theo hướng làm BỘ ĐẾM khớp với DANH SÁCH (cộng thêm phòng họp), chứ
// không đổi danh sách: danh sách đang đúng như trước khi tách mục, còn thêm
// một tab mới là đổi thiết kế chứ không phải vá hồi quy.
patch(MessagingMenu.prototype, {
    /**
     * @override
     */
    get _tabs() {
        const tabs = super._tabs;
        // Không có tab "chat" thì không có gì để cộng vào — chỉ xảy ra nếu
        // upstream bỏ tab đó; im lặng nhường còn hơn ném lỗi trong một
        // getter mà cả khay tin nhắn phụ thuộc vào.
        const chatTab = tabs.find((tab) => tab.id === "chat");
        if (chatTab) {
            chatTab.counter += this.store.discuss.aidtMeetings.threadsWithCounter.length;
        }
        return tabs;
    },
});
