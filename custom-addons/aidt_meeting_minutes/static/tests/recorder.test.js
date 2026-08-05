import { describe, expect, test } from "@odoo/hoot";
import { computeOffsetMs, shouldUpload } from "@aidt_meeting_minutes/recorder_service";

describe.current.tags("headless");

describe("recorder timing", () => {
    test("offset đo theo thời gian trôi cục bộ, không theo đồng hồ tường", () => {
        // Máy vào giữa chừng: elapsedAtJoin do server cấp, phần còn lại là
        // performance.now() của chính máy đó. Lệch đồng hồ giữa các máy
        // không được ảnh hưởng tới kết quả.
        const offset = computeOffsetMs({
            elapsedAtJoinMs: 30000,
            recorderStartedAt: 1000,
            now: 4500,
        });
        expect(offset).toBe(33500);
    });

    test("vào ngay từ đầu thì offset bắt đầu từ 0", () => {
        const offset = computeOffsetMs({
            elapsedAtJoinMs: 0,
            recorderStartedAt: 500,
            now: 500,
        });
        expect(offset).toBe(0);
    });
});

describe("mute gating", () => {
    test("tắt tiếng thì bỏ hẳn chunk", () => {
        // Whisper bịa ra chữ từ khoảng lặng số, nên cách xử lý đúng là
        // không đưa khoảng lặng vào chứ không phải lọc kết quả về sau.
        expect(shouldUpload({ enabled: false }, 0.5)).toBe(false);
    });

    test("dưới ngưỡng năng lượng thì bỏ chunk", () => {
        expect(shouldUpload({ enabled: true }, 0.0001)).toBe(false);
    });

    test("đang nói thì gửi", () => {
        expect(shouldUpload({ enabled: true }, 0.05)).toBe(true);
    });
});
