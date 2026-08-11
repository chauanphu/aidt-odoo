import { describe, expect, test } from "@odoo/hoot";
import { animationFrame, click } from "@odoo/hoot-dom";
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

    test("bấm Kết thúc gọi đúng model/method/args", async () => {
        const calls = captureOrmCalls();
        await mountWithCleanup(RecordingBanner, {
            props: {
                recorder: { state: { recordingId: 7, hostPartnerId: 42 } },
                selfPartnerId: 42,
            },
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
        // đang được ghi âm" trong khi bản ghi nằm ở kênh 99 — và nút "Kết
        // thúc" ở đây sẽ gửi action_stop cho bản ghi của kênh 99.
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

    test("không gọi server khi không có bản ghi nào để dừng", async () => {
        // `orm.call` với `null` chỉ đổi lấy một traceback `ensure_one` đập
        // vào mặt người dùng giữa cuộc họp.
        const calls = captureOrmCalls();
        const banner = await mountWithCleanup(RecordingBanner, {
            props: { recorder: { state: { recordingId: null } } },
        });
        await banner.onStop();
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

    // --- Task 8: hai vai (chủ phòng / người dự) × ba trạng thái ---

    test("người dự không thấy nút nào", async () => {
        const recorder = {
            state: { recordingId: 5, channelId: 7, paused: false, hostPartnerId: 99 },
        };
        await mountWithCleanup(RecordingBanner, {
            props: { recorder, isActiveCall: true, channelId: 7, selfPartnerId: 42 },
        });
        expect(".o-aidt-recording-banner").toHaveCount(1);
        expect("button[name='pause']").toHaveCount(0);
        expect("button[name='stop']").toHaveCount(0);
    });

    test("chủ phòng thấy Tạm dừng và Kết thúc", async () => {
        const recorder = {
            state: { recordingId: 5, channelId: 7, paused: false, hostPartnerId: 42 },
        };
        await mountWithCleanup(RecordingBanner, {
            props: { recorder, isActiveCall: true, channelId: 7, selfPartnerId: 42 },
        });
        expect("button[name='pause']").toHaveCount(1);
        expect("button[name='stop']").toHaveCount(1);
    });

    test("đang tạm dừng thì chủ phòng thấy Ghi tiếp", async () => {
        const recorder = {
            state: { recordingId: 5, channelId: 7, paused: true, hostPartnerId: 42 },
        };
        await mountWithCleanup(RecordingBanner, {
            props: { recorder, isActiveCall: true, channelId: 7, selfPartnerId: 42 },
        });
        expect("button[name='resume']").toHaveCount(1);
        expect("button[name='pause']").toHaveCount(0);
    });

    test("người dự vẫn thấy băng khi đang tạm dừng", async () => {
        const recorder = {
            state: { recordingId: 5, channelId: 7, paused: true, hostPartnerId: 99 },
        };
        await mountWithCleanup(RecordingBanner, {
            props: { recorder, isActiveCall: true, channelId: 7, selfPartnerId: 42 },
        });
        // Giấu trạng thái tạm dừng còn tệ hơn không hiện gì: người ta sẽ giữ ý
        // trong khi thực ra không bị ghi, hoặc nói thoải mái vì tưởng đang dừng.
        expect(".o-aidt-recording-banner").toHaveCount(1);
    });
});
