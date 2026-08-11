import { describe, expect, test } from "@odoo/hoot";
import { patchWithCleanup } from "@web/../tests/web_test_helpers";
import { browser } from "@web/core/browser/browser";
import {
    CHUNK_MS,
    MeetingRecorder,
    OVERLAP_MS,
    SAMPLE_RATE,
    carriedStartAt,
    computeOffsetMs,
    retainOverlap,
    shouldRetry,
    shouldUpload,
} from "@aidt_meeting_minutes/recorder_service";

describe.current.tags("headless");

const FRAME = 128; // một lượt render của AudioWorklet

/** Một khung audio toàn giá trị `value`. */
function frame(value, length = FRAME) {
    return Float32Array.from({ length }, () => value);
}

/**
 * Recorder đã tháo rời khỏi WebAudio: encoder giả, `_send` giả, đồng hồ giả.
 * Nhờ vậy kiểm được đúng phần logic quyết định (chặn tắt tiếng, mồi chồng
 * lấn, gửi lại) mà không cần micro thật.
 */
function makeRecorder({
    isMute = false,
    channelId = 1,
    ormResult = {},
    recordingId = 7,
} = {}) {
    const clock = { now: 0 };
    patchWithCleanup(browser, { performance: { now: () => clock.now } });
    const session = { isMute };
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
    const encoded = [];
    recorder._newEncoder = () => {
        recorder.encoder = {
            encode: (data) => encoded.push(data),
            finish: () => ["MP3"],
        };
    };
    recorder._newEncoder();
    const sent = [];
    recorder._send = (chunk) => sent.push(chunk);

    recorder.state.recordingId = recordingId;
    recorder.state.channelId = recordingId === null ? null : channelId;
    recorder.elapsedAtJoinMs = 0;
    recorder.recorderStartedAt = 0;
    recorder.chunkStartedAt = 0;
    recorder.peakRms = 0;
    recorder.chunkHasAudio = false;
    return { recorder, rtc, session, clock, encoded, sent, ormCalls };
}

/** Đẩy `count` khung vào recorder, mỗi khung cách nhau `stepMs`. */
function feed(ctx, count, { value = 0.5, stepMs = 8 } = {}) {
    for (let i = 0; i < count; i++) {
        ctx.clock.now += stepMs;
        ctx.recorder._onAudio({ data: frame(value) });
    }
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

describe("mute gating", () => {
    // `shouldUpload` nhận cờ "mẩu này có tiếng micro thật hay không" do
    // `_onAudio` dựng lên, KHÔNG phải `MediaStreamTrack.enabled` — cờ đó bị
    // kích hoạt-bằng-giọng-nói bật/tắt nhiều lần mỗi giây.
    test("mẩu không thu được khung nào thì bỏ hẳn", () => {
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

    test("tắt tiếng thì KHÔNG mã hoá khung nào nữa", () => {
        // Clone giữ `enabled` riêng với track gốc nên nó vẫn nghe thấy mọi
        // thứ sau khi người dùng bấm tắt micro. Phải chặn ở chỗ mã hoá:
        // chặn ở chỗ gửi thì đoạn nói riêng vẫn nằm trong mẩu.
        const ctx = makeRecorder();
        feed(ctx, 3);
        expect(ctx.encoded).toHaveLength(3);

        ctx.session.isMute = true;
        feed(ctx, 20);
        expect(ctx.encoded).toHaveLength(3);
    });

    test("lúc tắt tiếng thì chốt ngay phần đã thu, không vứt đi", () => {
        const ctx = makeRecorder();
        feed(ctx, 3);
        ctx.session.isMute = true;
        feed(ctx, 1);
        expect(ctx.sent).toHaveLength(1);
        expect(ctx.sent[0].offsetMs).toBe(0);
    });

    test("bật tiếng lại thì mở mẩu mới, không nối vào phần trước", () => {
        const ctx = makeRecorder();
        feed(ctx, 3);
        ctx.session.isMute = true;
        feed(ctx, 5);
        ctx.session.isMute = false;
        ctx.clock.now += 8;
        ctx.recorder._onAudio({ data: frame(0.5) });
        // Mẩu mới bắt đầu từ đúng lúc bật tiếng lại: khoảng tắt tiếng ở giữa
        // không được tính vào độ dài của nó.
        expect(ctx.recorder.chunkStartedAt).toBe(ctx.clock.now);
    });
});

describe("chồng lấn", () => {
    test("chỉ giữ lại phần đuôi dài OVERLAP_MS", () => {
        const limit = (SAMPLE_RATE * OVERLAP_MS) / 1000;
        const frames = [];
        let total = 0;
        for (let i = 0; i < 400; i++) {
            total = retainOverlap(frames, frame(0.1), limit);
        }
        expect(total).toBeGreaterThan(limit - FRAME);
        expect(total).toBeLessThan(limit + FRAME);
    });

    test("mốc bắt đầu lùi đúng bằng đoạn ĐÃ mồi, không phải OVERLAP_MS trên giấy", () => {
        expect(carriedStartAt(10000, 24000, 16000)).toBe(8500);
        expect(carriedStartAt(10000, 0, 16000)).toBe(10000);
    });

    test("cắt mẩu thì mồi lại đúng số khung đã giữ và offset khớp với tiếng", () => {
        const ctx = makeRecorder();
        feed(ctx, 2, { stepMs: 10 });
        expect(ctx.encoded).toHaveLength(2);

        ctx.clock.now = CHUNK_MS;
        ctx.recorder._onAudio({ data: frame(0.5) });

        // 3 khung gốc + 3 khung được mồi lại vào encoder mới.
        expect(ctx.encoded).toHaveLength(6);
        const carriedMs = ((3 * FRAME) / SAMPLE_RATE) * 1000;
        expect(ctx.recorder.chunkStartedAt).toBe(CHUNK_MS - carriedMs);

        // Mẩu kế tiếp phải khai đúng mốc đó — offset và tiếng cùng nói một
        // chuyện thì phần khử trùng mối nối ở server mới có cái để so.
        ctx.clock.now = CHUNK_MS * 2;
        ctx.recorder._onAudio({ data: frame(0.5) });
        expect(ctx.sent).toHaveLength(2);
        expect(ctx.sent[0].offsetMs).toBe(0);
        expect(ctx.sent[1].offsetMs).toBe(Math.round(CHUNK_MS - carriedMs));
    });
});

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
        // Bus broadcast tới cả thành viên kênh: mình có thể là thành viên
        // của một kênh khác nơi một bản ghi không liên quan vừa dừng, trong
        // khi vẫn đang thu thật cho kênh hiện tại. `stopped` không khớp id
        // không được phép cắt ngang phiên đang chạy.
        const ctx = makeRecorder();
        ctx.recorder.state.recordingId = 42;

        ctx.recorder._onRecordingState({ action: "stopped", recording_id: 99 });

        expect(ctx.recorder.state.recordingId).toBe(42);

        ctx.recorder._onRecordingState({ action: "stopped", recording_id: 42 });
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
        // Và nút "Dừng ghi âm" của băng ở B không được cầm id của bản ghi A.
        expect(ctx.recorder.lastOfferedId).toBe(null);
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
