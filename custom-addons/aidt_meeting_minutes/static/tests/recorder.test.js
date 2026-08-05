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
function makeRecorder({ isMute = false } = {}) {
    const clock = { now: 0 };
    patchWithCleanup(browser, { performance: { now: () => clock.now } });
    const session = { isMute };
    const rtc = { state: {}, localSession: session };
    const recorder = new MeetingRecorder(
        {},
        {
            "discuss.rtc": rtc,
            bus_service: { subscribe: () => {} },
            notification: { add: () => {} },
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

    recorder.state.recordingId = 7;
    recorder.elapsedAtJoinMs = 0;
    recorder.recorderStartedAt = 0;
    recorder.chunkStartedAt = 0;
    recorder.peakRms = 0;
    recorder.chunkHasAudio = false;
    return { recorder, rtc, session, clock, encoded, sent };
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

    test("từ chối một cuộc họp không câm luôn các cuộc họp sau", async () => {
        const ctx = makeRecorder();
        ctx.recorder.decline();
        expect(ctx.recorder.state.recordingId).toBe(null);

        await ctx.recorder.start(7, 0);
        expect(ctx.recorder.state.recordingId).toBe(null);

        await ctx.recorder.start(8, 0);
        expect(ctx.recorder.state.recordingId).toBe(8);
        expect(ctx.recorder.state.declined).toBe(false);
    });

    test("declinedRecordingId chỉ xoá khi ĐÚNG bản ghi đó báo dừng", () => {
        // Băng thông báo (Task 10) phải hiện "bạn đã từ chối; cuộc họp vẫn
        // đang ghi" cho tới khi cuộc họp 7 thực sự dừng — không sớm hơn,
        // không bị một `stopped` của cuộc họp KHÁC xoá nhầm.
        const ctx = makeRecorder();
        ctx.recorder.decline();
        expect(ctx.recorder.state.declinedRecordingId).toBe(7);

        ctx.recorder._onRecordingState({ action: "stopped", recording_id: 9 });
        expect(ctx.recorder.state.declinedRecordingId).toBe(7);

        ctx.recorder._onRecordingState({ action: "stopped", recording_id: 7 });
        expect(ctx.recorder.state.declinedRecordingId).toBe(null);
        expect(ctx.recorder.state.declined).toBe(false);
    });
});
