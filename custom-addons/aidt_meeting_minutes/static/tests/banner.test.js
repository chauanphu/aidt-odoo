import { describe, expect, test } from "@odoo/hoot";
import { mountWithCleanup } from "@web/../tests/web_test_helpers";
import { RecordingBanner } from "@aidt_meeting_minutes/recording_banner";

describe.current.tags("headless");

describe("recording banner", () => {
    test("không hiện khi không ghi âm", async () => {
        await mountWithCleanup(RecordingBanner, {
            props: { recorder: { state: { recordingId: null } } },
        });
        expect(".o-aidt-recording-banner").toHaveCount(0);
    });

    test("hiện banner và cả hai nút khi đang ghi âm", async () => {
        // Banner là CƠ CHẾ THỰC THI của giả định "người dùng tự tắt khi nội
        // dung là Mật", không phải chi tiết giao diện — nên nó không được ẩn
        // và nút dừng phải luôn có mặt. `isActiveCall` mặc định true khi
        // không truyền — chỉ template `discuss.Call` mới truyền giá trị
        // thật.
        await mountWithCleanup(RecordingBanner, {
            props: { recorder: { state: { recordingId: 7 } } },
        });
        expect(".o-aidt-recording-banner").toHaveCount(1);
        expect("button[name='decline']").toHaveCount(1);
        expect("button[name='stop']").toHaveCount(1);
    });

    test("không hiện khi đã rời cuộc gọi dù bản ghi vẫn đang chạy", async () => {
        // Bus broadcast trạng thái ghi âm tới CẢ THÀNH VIÊN KÊNH, không chỉ
        // người đang trong cuộc gọi — người đã rời không được thấy banner
        // (và do đó không có nút để bấm) chỉ vì `recordingId` vẫn còn set.
        await mountWithCleanup(RecordingBanner, {
            props: {
                recorder: { state: { recordingId: 7 } },
                isActiveCall: false,
            },
        });
        expect(".o-aidt-recording-banner").toHaveCount(0);
    });
});
