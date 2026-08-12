import { describe, expect, test } from "@odoo/hoot";
import { defineMailModels, start } from "@mail/../tests/mail_test_helpers";
import { MessagingMenu } from "@mail/core/public_web/messaging_menu";

import "@aidt_meeting_minutes/discuss_app_model_patch";
import "@aidt_meeting_minutes/discuss_app_category_model_patch";
import "@aidt_meeting_minutes/thread_model_patch";
import "@aidt_meeting_minutes/messaging_menu_patch";

describe.current.tags("headless");
defineMailModels();

/** Chèn thẳng một Thread vào store, không đi qua mock server.
 *
 * Cố ý: `aidt_is_meeting_room` do server tính, và việc nó tới được client đã
 * có test Python riêng (TestMeetingRoomFlag). Ở đây ta chỉ kiểm ĐÚNG phần
 * mình viết — luật xếp mục — nên đặt thẳng giá trị vào là cách gọn nhất và
 * không phụ thuộc vào việc mock server có khai trường đó hay không.
 */
function insertThread(env, id, extra) {
    return env.services["mail.store"].Thread.insert({
        model: "discuss.channel",
        id,
        channel_type: "group",
        ...extra,
    });
}

test("phòng họp rơi vào mục Họp", async () => {
    const env = await start();
    const thread = insertThread(env, 101, { aidt_is_meeting_room: true });
    expect(thread.discussAppCategory.id).toBe(
        "aidt_meeting_minutes.category_meetings"
    );
});

test("kênh group thường vẫn ở Tin nhắn trực tiếp", async () => {
    const env = await start();
    const thread = insertThread(env, 102, { aidt_is_meeting_room: false });
    expect(thread.discussAppCategory.id).toBe("chats");
});

test("kênh channel thường vẫn ở Kênh", async () => {
    const env = await start();
    const thread = insertThread(env, 103, {
        channel_type: "channel",
        aidt_is_meeting_room: false,
    });
    expect(thread.discussAppCategory.id).toBe("channels");
});

test("kênh con của phòng họp không thành mục riêng trong thanh bên", async () => {
    // Kênh con (`parent_channel_id`) không bao giờ đứng riêng trong thanh
    // bên: upstream `_computeDiscussAppCategory` trả về `undefined` ngay ở
    // dòng đầu cho chúng, và bản patch phải nhường cho `super()` TRƯỚC khi
    // xét `aidt_is_meeting_room`. Kênh con của một phòng họp thừa hưởng
    // `calendar_event_ids` qua chính phòng cha nên nó thật sự mang cờ này —
    // bỏ chốt `!this.parent_channel_id` là kênh con hiện thành dòng riêng
    // trong mục "Họp", còn phòng cha thì không gom được chúng lại.
    const env = await start();
    const parent = insertThread(env, 104, { aidt_is_meeting_room: true });
    const sub = insertThread(env, 105, {
        aidt_is_meeting_room: true,
        parent_channel_id: parent,
    });
    expect(parent.discussAppCategory.id).toBe("aidt_meeting_minutes.category_meetings");
    expect(sub.discussAppCategory).toBe(undefined);
});

test("mục Họp sắp phòng theo hoạt động gần nhất", async () => {
    // Trước khi tách mục, phòng họp nằm trong `chats` và được sắp theo
    // `lastInterestDt` — phòng vừa có tin nhắn mới nổi lên đầu.
    // `DiscussAppCategory.sortThreads` chỉ biết hai id "channels"/"chats",
    // nên mục mới mà không khai luật thì trả `undefined` và danh sách đứng
    // im theo thứ tự chèn (ở đây: 201, 202, 203).
    const env = await start();
    const store = env.services["mail.store"];
    insertThread(env, 201, {
        aidt_is_meeting_room: true,
        last_interest_dt: "2026-08-01 08:00:00",
    });
    insertThread(env, 202, {
        aidt_is_meeting_room: true,
        last_interest_dt: "2026-08-03 08:00:00",
    });
    insertThread(env, 203, {
        aidt_is_meeting_room: true,
        last_interest_dt: "2026-08-02 08:00:00",
    });
    const ids = [...store.discuss.aidtMeetings.threads].map((thread) => thread.id);
    expect(ids).toEqual([202, 203, 201]);
});

test("phòng họp chưa đọc vẫn được đếm vào tab Chats của khay tin nhắn", async () => {
    // Bộ đếm tab đếm theo MỤC thanh bên, còn danh sách trong tab lọc theo
    // `channel_type` (`tabToThreadType("chat")` = ['chat','group']). Phòng
    // họp vẫn là 'group' nên nó ở lại DANH SÁCH tab "Chats"; nếu bộ đếm
    // không cộng thêm mục "Họp" thì tab không có huy hiệu trong khi bên
    // trong có dòng chưa đọc — mất chỉ báo, không phải lỗi thẩm mỹ.
    const env = await start();
    const store = env.services["mail.store"];
    const thread = insertThread(env, 301, {
        aidt_is_meeting_room: true,
        message_needaction_counter: 3,
    });
    // Đủ để `displayInSidebar` bật mà không phải dựng dữ liệu thành viên:
    // `categoryAsThreadWithCounter` đòi `displayInSidebar && importantCounter > 0`.
    thread.isLocallyPinned = true;

    // Phòng họp vẫn thuộc danh sách của tab "Chats"...
    expect(store.tabToThreadType("chat")).toInclude(thread.channel_type);
    // ...nhưng đã rời mục `chats`, nên chỉ mục "Họp" đếm nó.
    expect(store.discuss.chats.threadsWithCounter.length).toBe(0);
    expect(store.discuss.aidtMeetings.threadsWithCounter.length).toBe(1);

    // Gọi thẳng getter `_tabs` trên prototype: nó chỉ đọc `this.store`, nên
    // không cần dựng cả component chỉ để đọc một con số.
    const menu = Object.create(MessagingMenu.prototype);
    menu.store = store;
    const chatTab = menu._tabs.find((tab) => tab.id === "chat");
    expect(chatTab.counter).toBe(1);
});
