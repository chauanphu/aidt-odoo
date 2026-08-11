import { describe, expect, test } from "@odoo/hoot";
import { MeetingRecorder } from "@aidt_meeting_minutes/recorder_service";

describe.current.tags("headless");

function makeRecorder() {
    const services = {
        "discuss.rtc": { state: { channel: { id: 7 }, micAudioTrack: null } },
        bus_service: { subscribe: () => {} },
        notification: {},
        orm: { call: async () => ({}) },
    };
    return new MeetingRecorder({ services: {} }, services);
}

/**
 * `MediaRecorder` giả tối thiểu — chỉ đủ phần `pause()`/`stop()` thật sự
 * dùng tới (`state`, `addEventListener("stop", …)`, `ondataavailable`,
 * `stop()`). KHÔNG tự bắn `dataavailable` khi `stop()` được gọi — bài test
 * bên dưới tự quyết định lúc nào mẩu cuối "đến", để mô phỏng đúng độ trễ
 * thật của MediaRecorder giữa lúc gọi `.stop()` và lúc sự kiện thực sự bắn.
 */
function makeFakeMediaRecorder() {
    return {
        state: "recording",
        ondataavailable: null,
        addEventListener() {
            // `pause()`/`stop()` chỉ đăng ký "stop" để await; bài test dưới
            // không cần trạng thái đó nên bỏ qua, không lưu listener.
        },
        stop() {
            this.state = "inactive";
        },
    };
}

test("ghi tiếp tăng take và đếm lại seq từ 0", async () => {
    const recorder = makeRecorder();
    recorder.state.recordingId = 11;
    recorder.take = 0;
    recorder.seq = 4;

    recorder._onRecordingState({
        action: "resumed", recording_id: 11, channel_id: 7,
        take: 1, state: "recording", elapsed_ms: 60000,
    });

    expect(recorder.take).toBe(1);
    expect(recorder.seq).toBe(0);
});

test("tạm dừng KHÔNG xoá recordingId", async () => {
    const recorder = makeRecorder();
    recorder.state.recordingId = 11;

    recorder._onRecordingState({
        action: "paused", recording_id: 11, channel_id: 7,
        take: 0, state: "paused", elapsed_ms: 5000,
    });

    // Bản ghi vẫn đang hoạt động, chỉ là không thu nữa. Xoá recordingId ở
    // đây thì băng thông báo biến mất và client tưởng cuộc họp đã kết thúc.
    expect(recorder.state.recordingId).toBe(11);
    expect(recorder.state.paused).toBe(true);
});

test("kết thúc mới xoá recordingId", async () => {
    const recorder = makeRecorder();
    recorder.state.recordingId = 11;

    recorder._onRecordingState({
        action: "stopped", recording_id: 11, channel_id: 7,
        take: 0, state: "processing", elapsed_ms: 9000,
    });

    expect(recorder.state.recordingId).toBe(null);
});

test("mẩu cuối đến MUỘN sau khi resume() đã đổi take vẫn mang đúng take CŨ", () => {
    // Kịch bản đua: pause() gọi MediaRecorder.stop(), nhưng sự kiện
    // "dataavailable" của mẩu cuối không bắn ngay — nó có thể tới SAU khi
    // broadcast "resumed" đã về và resume() đã đổi this.take/this.seq sang
    // take mới. Nếu callback đọc this.take "sống" tại lúc bắn thay vì chụp
    // lại tại lúc pause(), mẩu cuối của take CŨ bị gắn nhầm take MỚI và đụng
    // khoá UNIQUE(recording_id, partner_id, take, seq) với mẩu seq=0 thật
    // của take mới — mất mẩu trong im lặng.
    const recorder = makeRecorder();
    recorder.state.recordingId = 11;
    recorder.take = 3;
    recorder.seq = 2;

    const sent = [];
    recorder._send = (chunk) => sent.push(chunk);

    const fakeMediaRecorder = makeFakeMediaRecorder();
    recorder.recorder = fakeMediaRecorder;

    recorder.pause();
    // Ngay sau pause(): callback "dataavailable" đã được gắn lại (chụp take
    // = 3), nhưng CHƯA có mẩu nào bắn ra — đúng độ trễ đang mô phỏng.

    recorder._onRecordingState({
        action: "resumed", recording_id: 11, channel_id: 7,
        take: 4, state: "recording", elapsed_ms: 120000,
    });
    // resume() đã chạy: this.take giờ là 4, this.seq giờ là 0.
    expect(recorder.take).toBe(4);

    // Mẩu cuối của take 3 giờ mới thực sự "bắn" ra.
    fakeMediaRecorder.ondataavailable({ data: { size: 100 } });

    expect(sent).toHaveLength(1);
    expect(sent[0].take).toBe(3);
    expect(sent[0].seq).toBe(2);
});

test("mẩu cuối đến MUỘN sau khi start() phiên MỚI vẫn mang đúng recordingId/take/seq của phiên CŨ", () => {
    // Cùng lớp đua với test ở trên, nhưng ở stop() thay vì pause(): bus phát
    // "started" của một cuộc họp MỚI có thể tới và kích start() TRƯỚC khi
    // mẩu cuối của phiên CŨ (do stop() gọi MediaRecorder.stop()) kịp bắn —
    // stop() xoá state.recordingId ĐỒNG BỘ nên không có gì chặn start() mới
    // chạy ngay lập tức. Nếu callback đọc this.seq/this.take "sống" thay vì
    // chụp lại tại lúc stop(), mẩu cuối của phiên CŨ mang seq=0 của phiên
    // MỚI — số chắc chắn phiên cũ đã dùng — đụng khoá
    // UNIQUE(recording_id, partner_id, take, seq) và mất mẩu chứa lời kết
    // của cuộc họp trong im lặng.
    const recorder = makeRecorder();
    recorder.state.recordingId = 11;
    recorder.take = 3;
    recorder.seq = 2;

    const sent = [];
    recorder._send = (chunk) => sent.push(chunk);

    const fakeMediaRecorder = makeFakeMediaRecorder();
    recorder.recorder = fakeMediaRecorder;

    recorder.stop();
    // Ngay sau stop(): callback "dataavailable" đã được gắn lại (chụp
    // recordingId=11, take=3, seq=2), nhưng CHƯA có mẩu nào bắn ra.

    recorder._onRecordingState({
        action: "started", recording_id: 22, channel_id: 7,
        take: 0, state: "recording", elapsed_ms: 0,
    });
    // start() của phiên MỚI đã chạy: state.recordingId/this.take/this.seq
    // giờ thuộc về phiên 22, không còn liên quan gì tới phiên 11 nữa.
    expect(recorder.state.recordingId).toBe(22);
    expect(recorder.take).toBe(0);
    expect(recorder.seq).toBe(0);

    // Mẩu cuối của phiên 11 giờ mới thực sự "bắn" ra.
    fakeMediaRecorder.ondataavailable({ data: { size: 100 } });

    expect(sent).toHaveLength(1);
    expect(sent[0].recordingId).toBe(11);
    expect(sent[0].take).toBe(3);
    expect(sent[0].seq).toBe(2);
});
