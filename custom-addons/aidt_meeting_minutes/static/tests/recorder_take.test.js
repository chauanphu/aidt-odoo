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
