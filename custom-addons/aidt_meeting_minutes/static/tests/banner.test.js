import { describe, expect, test } from "@odoo/hoot";
import { animationFrame, click } from "@odoo/hoot-dom";
import { mockService, mountWithCleanup } from "@web/../tests/web_test_helpers";
import { RecordingBanner } from "@aidt_meeting_minutes/recording_banner";

describe.current.tags("headless");

/** Đủ hình dạng của `MeetingRecorder` để lái được `onDecline`. */
function makeFakeRecorder(recordingId) {
    return {
        state: { recordingId, declinedRecordingId: null, declined: false },
        decline() {
            // Cùng thứ tự với recorder_service.js thật: ghi declinedRecordingId
            // TRƯỚC khi xoá recordingId.
            this.state.declinedRecordingId = this.state.recordingId;
            this.state.declined = true;
            this.state.recordingId = null;
        },
    };
}

/** Ghi lại lời gọi `orm.call` cuối cùng thay vì đụng mạng thật. */
function captureOrmCalls() {
    const calls = [];
    mockService("orm", {
        async call(model, method, args, kwargs) {
            calls.push({ model, method, args, kwargs });
            return true;
        },
    });
    return calls;
}

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

    test("bấm Dừng ghi âm gọi đúng model/method/args", async () => {
        const calls = captureOrmCalls();
        await mountWithCleanup(RecordingBanner, {
            props: { recorder: { state: { recordingId: 7 } } },
        });
        await click("button[name='stop']");
        await animationFrame();

        expect(calls).toEqual([
            {
                model: "aidt.meeting.recording",
                method: "action_stop",
                args: [[7]],
                kwargs: {},
            },
        ]);
    });

    test("bấm Từ chối gọi action_decline (KHÔNG phải _decline) và không kèm partner", async () => {
        // CRITICAL 1 của review: `_decline` bắt đầu bằng "_" nên bị RPC
        // chặn thẳng (odoo/service/model.py::get_public_method); wrapper
        // công khai `action_decline` không nhận partner từ client.
        const calls = captureOrmCalls();
        const recorder = makeFakeRecorder(7);
        await mountWithCleanup(RecordingBanner, { props: { recorder } });
        await click("button[name='decline']");
        await animationFrame();

        expect(calls).toEqual([
            {
                model: "aidt.meeting.recording",
                method: "action_decline",
                args: [[7]],
                kwargs: {},
            },
        ]);
        // Cục bộ đã dừng, nhưng băng vẫn phải còn đó cho tới khi server báo
        // "stopped" — xem CRITICAL 2.
        expect(".o-aidt-recording-banner").toHaveCount(1);
        expect("button[name='stop']").toHaveCount(1);
    });

    test("sau khi từ chối: không còn nút Từ chối, nút Dừng vẫn gọi đúng id đã từ chối", async () => {
        const calls = captureOrmCalls();
        const recorder = makeFakeRecorder(7);
        await mountWithCleanup(RecordingBanner, { props: { recorder } });
        await click("button[name='decline']");
        await animationFrame();

        expect("button[name='decline']").toHaveCount(0);
        expect(".o-aidt-recording-banner.o-aidt-declined").toHaveCount(1);

        await click("button[name='stop']");
        await animationFrame();

        // Lời gọi thứ hai (đầu tiên là action_decline) phải dùng ĐÚNG id đã
        // từ chối, dù `state.recordingId` cục bộ đã về null từ lâu.
        expect(calls[1]).toEqual({
            model: "aidt.meeting.recording",
            method: "action_stop",
            args: [[7]],
            kwargs: {},
        });
    });

    test("hiện nút Bật ghi âm khi đang trong cuộc gọi và chưa ai ghi", async () => {
        await mountWithCleanup(RecordingBanner, {
            props: {
                recorder: { state: { recordingId: null } },
                channelId: 42,
            },
        });
        expect("button[name='start']").toHaveCount(1);
        expect(".o-aidt-recording-banner").toHaveCount(0);
    });

    test("không hiện nút Bật ghi âm khi đã có bản ghi đang chạy", async () => {
        await mountWithCleanup(RecordingBanner, {
            props: {
                recorder: { state: { recordingId: 7 } },
                channelId: 42,
            },
        });
        expect("button[name='start']").toHaveCount(0);
    });

    test("bấm Bật ghi âm gọi action_start_for_channel với đúng channel_id", async () => {
        const calls = captureOrmCalls();
        await mountWithCleanup(RecordingBanner, {
            props: {
                recorder: { state: { recordingId: null } },
                channelId: 42,
            },
        });
        await click("button[name='start']");
        await animationFrame();

        expect(calls).toEqual([
            {
                model: "aidt.meeting.recording",
                method: "action_start_for_channel",
                args: [42],
                kwargs: {},
            },
        ]);
    });
});
