import { describe, expect, test } from "@odoo/hoot";
import { patchWithCleanup } from "@web/../tests/web_test_helpers";
import { browser } from "@web/core/browser/browser";
import {
    CHUNK_MS,
    MeetingRecorder,
    computeOffsetMs,
    shouldRetry,
} from "@aidt_meeting_minutes/recorder_service";

describe.current.tags("headless");

/**
 * Recorder đã tháo rời khỏi WebAudio: `_send` giả, đồng hồ giả. Nhờ vậy kiểm
 * được phần logic quyết định (gửi lại có trần, phạm vi kênh, đồng bộ trạng
 * thái) mà không cần micro thật.
 */
function makeRecorder({
    channelId = 1,
    ormResult = {},
    recordingId = 7,
} = {}) {
    const clock = { now: 0 };
    patchWithCleanup(browser, { performance: { now: () => clock.now } });
    const session = {};
    // `state.channel` = kênh của cuộc gọi mà máy này ĐANG ở trong. Recorder
    // đối chiếu id này với `channel_id` của mọi broadcast.
    const rtc = {
        state: { channel: channelId === null ? undefined : { id: channelId } },
        localSession: session,
    };
    const ormCalls = [];
    const recorder = new MeetingRecorder(
        {},
        {
            "discuss.rtc": rtc,
            bus_service: { subscribe: () => {} },
            notification: { add: () => {} },
            orm: {
                async call(model, method, args, kwargs) {
                    ormCalls.push({ model, method, args, kwargs });
                    return ormResult;
                },
            },
        }
    );
    const sent = [];
    recorder._send = (chunk) => sent.push(chunk);

    recorder.state.recordingId = recordingId;
    recorder.state.channelId = recordingId === null ? null : channelId;
    recorder.elapsedAtJoinMs = 0;
    recorder.recorderStartedAt = 0;
    recorder.chunkStartedAt = 0;
    return { recorder, rtc, session, clock, sent, ormCalls };
}

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

// ĐÃ GỠ: hai bộ "mute gating" và "chồng lấn".
//
// Chúng kiểm `shouldUpload`, `retainOverlap`, `carriedStartAt`, `_onAudio`,
// `SAMPLE_RATE`, `OVERLAP_MS` — API của bộ ghi âm CŨ (AudioWorklet + encoder
// MP3 + mồi chồng lấn 1.5s), bị thay hẳn ở 785bfa3a91a bằng MediaRecorder +
// AnalyserNode. Commit đó xoá đúng hai file test cùng lứa
// (`audio_stream_service.test.js`, `subtitle.test.js`) nhưng bỏ sót file này,
// nên chín test ở đây đỏ liên tục từ 08/08/2026 — và vì hoot chạy qua
// `browser_js` SKIP thay vì FAIL khi thiếu chromium, không ai thấy.
//
// ⚠️ QUAN TRỌNG — gỡ test KHÔNG có nghĩa là vấn đề đã xong: bộ "mute gating"
// kiểm việc TẮT MICRO THÌ KHÔNG MÃ HOÁ, và hành vi đó hiện KHÔNG TỒN TẠI
// trong `recorder_service.js` (grep `mute` trong static/src trả về rỗng; nó
// mở luồng getUserMedia RIÊNG nên `enabled=false` của Odoo không chạm tới).
// Đây là một khoản nợ về QUYỀN RIÊNG TƯ, ghi ở README §8.4. Khi cài lại,
// hãy viết test mới theo API hiện tại — đừng khôi phục khối này.

describe("gửi lại có trần", () => {
    test("4xx là từ chối vĩnh viễn, không gửi lại", () => {
        expect(shouldRetry(403, 1)).toBe(false);
        expect(shouldRetry(413, 1)).toBe(false);
        expect(shouldRetry(404, 1)).toBe(false);
    });

    test("hỏng mạng hoặc 5xx thì gửi lại đúng MỘT lần", () => {
        // Gửi lại vô hạn sẽ đập vào UNIQUE(recording_id, partner_id, seq)
        // khi lần gửi đầu thực ra đã tới nơi, và server phải trả 500 cho
        // một việc hoàn toàn bình thường.
        expect(shouldRetry(0, 1)).toBe(true);
        expect(shouldRetry(500, 1)).toBe(true);
        expect(shouldRetry(0, 2)).toBe(false);
        expect(shouldRetry(500, 2)).toBe(false);
    });
});

describe("dọn dẹp và từ chối", () => {
    test("mất micro thì clone cũ bị tắt trước khi thoát sớm", async () => {
        // Clone sống độc lập: `state.micAudioTrack.stop()` của RTC không
        // đụng tới nó, nên không dọn ở đây thì thiết bị vẫn mở và chunk vẫn
        // chảy lên sau khi người dùng đã rút quyền micro.
        const ctx = makeRecorder();
        let stopped = false;
        ctx.recorder.clonedTrack = { stop: () => (stopped = true) };
        ctx.rtc.state.micAudioTrack = undefined;
        await ctx.recorder._attachToMic();
        expect(stopped).toBe(true);
        expect(ctx.recorder.clonedTrack).toBe(null);
    });

    test("stopped của một bản ghi KHÁC không được dừng phiên đang ghi thật", () => {
        // Bus broadcast tới cả thành viên kênh: hai bản ghi 99 và 42 cùng ở
        // kênh này (channel_id khớp), nhưng chỉ 42 là phiên đang thu thật.
        // `stopped` không khớp RECORDING_ID — dù đã qua được vòng lọc kênh —
        // vẫn không được phép cắt ngang phiên đang chạy.
        const ctx = makeRecorder();
        ctx.recorder.state.recordingId = 42;

        ctx.recorder._onRecordingState({ action: "stopped", recording_id: 99, channel_id: 1 });

        expect(ctx.recorder.state.recordingId).toBe(42);

        ctx.recorder._onRecordingState({ action: "stopped", recording_id: 42, channel_id: 1 });
        expect(ctx.recorder.state.recordingId).toBe(null);
    });
});

describe("phạm vi kênh của lệnh bật ghi âm", () => {
    // Bus phát tới MỌI kênh mà người dùng là thành viên, không chỉ kênh đang
    // gọi (addons/mail/models/discuss/ir_websocket.py: is_member = True).
    test("started ở kênh KHÁC không được bật micro", async () => {
        // Kịch bản thật, không cần ai phá hoại: U là thành viên kênh phòng
        // ban A và đang họp riêng ở kênh B. Ai đó bật ghi âm ở A. Không đối
        // chiếu id kênh thì tab của U bật thu, `_attachToMic` tóm đúng
        // `rtc.state.micAudioTrack` — MICRO ĐANG SỐNG TRONG CUỘC GỌI B — và
        // đẩy lên bản ghi của A. Server nhận, vì U đúng là thành viên A. Nửa
        // cuộc gọi riêng của U được bóc băng, gán tên U, đăng vào chatter A.
        const ctx = makeRecorder({ channelId: 2, recordingId: null }); // đang ở trong cuộc gọi B
        await ctx.recorder._onRecordingState({
            action: "started", recording_id: 5, channel_id: 1, elapsed_ms: 0,
        });
        expect(ctx.recorder.state.recordingId).toBe(null);
        expect(ctx.recorder.state.channelId).toBe(null);
    });

    test("started ở ĐÚNG kênh đang gọi thì bật, kèm id kênh", async () => {
        const ctx = makeRecorder({ channelId: 2, recordingId: null });
        await ctx.recorder._onRecordingState({
            action: "started", recording_id: 5, channel_id: 2, elapsed_ms: 4000,
        });
        expect(ctx.recorder.state.recordingId).toBe(5);
        expect(ctx.recorder.state.channelId).toBe(2);
        expect(ctx.recorder.elapsedAtJoinMs).toBe(4000);
    });

    test("không ở trong cuộc gọi nào thì không bật gì cả", async () => {
        const ctx = makeRecorder({ channelId: null, recordingId: null });
        await ctx.recorder._onRecordingState({
            action: "started", recording_id: 5, channel_id: 1, elapsed_ms: 0,
        });
        expect(ctx.recorder.state.recordingId).toBe(null);
    });
});

describe("hỏi lại trạng thái khi vào họp / nạp lại tab", () => {
    // Broadcast "started" chỉ phát MỘT LẦN. Không hỏi lại thì người F5 giữa
    // cuộc họp có `recordingId` null vĩnh viễn: băng đồng thuận KHÔNG HIỆN
    // (cơ chế thực thi việc xin phép ghi âm biến mất đúng với người đang bị
    // ghi), tiếng của họ không được thu, và nút "Bật ghi âm" lại hiện ra.
    test("vào cuộc gọi đang được ghi thì bắt kịp bản ghi đó", async () => {
        const ctx = makeRecorder({
            channelId: 3,
            recordingId: null,
            ormResult: { recording_id: 11, channel_id: 3, elapsed_ms: 61000 },
        });
        await ctx.recorder.syncActiveRecording();

        expect(ctx.ormCalls).toEqual([
            {
                model: "aidt.meeting.recording",
                method: "action_active_recording",
                args: [3],
                kwargs: {},
            },
        ]);
        expect(ctx.recorder.state.recordingId).toBe(11);
        expect(ctx.recorder.state.channelId).toBe(3);
        // `elapsed_ms` của server là thứ đặt máy vào-muộn đúng chỗ trên trục
        // thời gian chung mà không cần đồng hồ hai máy khớp nhau.
        expect(ctx.recorder.elapsedAtJoinMs).toBe(61000);
    });

    test("kênh không được ghi âm thì không đụng gì tới trạng thái", async () => {
        const ctx = makeRecorder({ channelId: 3, recordingId: null, ormResult: {} });
        await ctx.recorder.syncActiveRecording();
        expect(ctx.recorder.state.recordingId).toBe(null);
    });

    test("không ở trong cuộc gọi thì không gọi server", async () => {
        const ctx = makeRecorder({ channelId: null, recordingId: null });
        await ctx.recorder.syncActiveRecording();
        expect(ctx.ormCalls).toHaveLength(0);
    });

    test("server lỗi thì im lặng, không ném ra ngoài", async () => {
        // Đây là đường phục hồi tự động, không phải hành động người dùng bấm
        // — một hộp thoại lỗi bật lên giữa cuộc họp là sai.
        const ctx = makeRecorder({ channelId: 3, recordingId: null });
        ctx.recorder.orm.call = async () => {
            throw new Error("mạng hỏng");
        };
        await ctx.recorder.syncActiveRecording();
        expect(ctx.recorder.state.recordingId).toBe(null);
    });

    test("rời cuộc gọi trong lúc chờ server thì không bật thu", async () => {
        const ctx = makeRecorder({ channelId: 3, recordingId: null });
        ctx.recorder.orm.call = async () => {
            // Người dùng gập máy đúng lúc RPC đang bay.
            ctx.rtc.state.channel = undefined;
            return { recording_id: 11, channel_id: 3, elapsed_ms: 0 };
        };
        await ctx.recorder.syncActiveRecording();
        expect(ctx.recorder.state.recordingId).toBe(null);
    });
});
