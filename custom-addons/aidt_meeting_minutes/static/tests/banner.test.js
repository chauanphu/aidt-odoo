import { describe, expect, test } from "@odoo/hoot";
import { animationFrame, click } from "@odoo/hoot-dom";
import { reactive } from "@odoo/owl";
import { mockService, mountWithCleanup } from "@web/../tests/web_test_helpers";
import { defineMailModels } from "@mail/../tests/mail_test_helpers";
import { RecordingBanner } from "@aidt_meeting_minutes/recording_banner";

describe.current.tags("headless");

// BẮT BUỘC, dù `RecordingBanner` không hề gọi tới `discuss.channel`: module
// này phụ thuộc `mail`, nên bộ module của hoot kéo theo các file `*.hoot.js`
// của mail, và chúng dựng store Discuss ngay khi env khởi tạo. Không khai báo
// model mail cho mock server thì mọi lần `mountWithCleanup` đều đổ
// "Cannot find a definition for model \"discuss.channel\"" trước cả assertion
// đầu tiên — đã quan sát đúng như vậy: 9/9 test của file này hỏng vì lý do
// này khi chạy thật trong Chrome (Task 12).
defineMailModels();

/**
 * Đủ hình dạng của `MeetingRecorder` để lái được `onDecline`.
 *
 * `state` PHẢI là `reactive()`, y như `MeetingRecorder` thật
 * (`recorder_service.js` dòng 95). Với object thường, `useState()` trong
 * `RecordingBanner.setup()` dựng một proxy riêng, còn `recorder.decline()`
 * ghi thẳng vào object GỐC — Owl không nhận được tín hiệu nào nên component
 * không vẽ lại, và bài test "sau khi từ chối..." hỏng dù mã sản phẩm đúng.
 * Chỉ lộ ra khi chạy trong Chrome thật (Task 12).
 */
function makeFakeRecorder(recordingId) {
    return {
        state: reactive({
            recordingId,
            declinedRecordingId: null,
            declined: false,
        }),
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

    test("không hiện khi bản ghi thuộc KÊNH KHÁC", async () => {
        // Bus phát trạng thái ghi âm tới mọi thành viên kênh. Không đối chiếu
        // id kênh thì băng trong cuộc gọi ở kênh 42 khẳng định "cuộc họp này
        // đang được ghi âm" trong khi bản ghi nằm ở kênh 99 — và nút "Dừng
        // ghi âm" ở đây sẽ gửi action_stop cho bản ghi của kênh 99.
        await mountWithCleanup(RecordingBanner, {
            props: {
                recorder: { state: { recordingId: 7, channelId: 99 } },
                channelId: 42,
            },
        });
        expect(".o-aidt-recording-banner").toHaveCount(0);
        // Và kênh này thì thật sự chưa được ghi, nên vẫn phải mời bật.
        expect("button[name='start']").toHaveCount(1);
    });

    test("hiện khi bản ghi thuộc ĐÚNG kênh đang mở", async () => {
        await mountWithCleanup(RecordingBanner, {
            props: {
                recorder: { state: { recordingId: 7, channelId: 42 } },
                channelId: 42,
            },
        });
        expect(".o-aidt-recording-banner").toHaveCount(1);
        expect("button[name='start']").toHaveCount(0);
    });

    test("không gọi server khi không có bản ghi nào để dừng/từ chối", async () => {
        // `orm.call` với `null` chỉ đổi lấy một traceback `ensure_one` đập
        // vào mặt người dùng giữa cuộc họp.
        const calls = captureOrmCalls();
        const banner = await mountWithCleanup(RecordingBanner, {
            props: { recorder: { state: { recordingId: null } } },
        });
        await banner.onStop();
        await banner.onDecline();
        expect(calls).toHaveLength(0);
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
