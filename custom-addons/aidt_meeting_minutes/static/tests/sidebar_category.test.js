import { describe, expect, test } from "@odoo/hoot";
import { defineMailModels, start } from "@mail/../tests/mail_test_helpers";

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
