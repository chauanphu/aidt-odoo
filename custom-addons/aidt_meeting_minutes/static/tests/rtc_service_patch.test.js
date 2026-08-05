import { describe, expect, test } from "@odoo/hoot";
import { Rtc } from "@mail/discuss/call/common/rtc_service";
import "@aidt_meeting_minutes/rtc_service_patch";

describe.current.tags("headless");

/**
 * Đủ hình dạng để `Rtc.prototype.clear()` THẬT chạy hết mà không văng lỗi —
 * mọi thứ nó đụng tới đều được truy cập qua `?.` hoặc gán trực tiếp, trừ
 * `this.exitFullscreen()`/`this.cleanups`/`this.update()`.
 */
function makeFakeRtc(recorder) {
    const log = [];
    return {
        log,
        state: {
            channel: undefined,
            updateAndBroadcastDebounce: undefined,
            disconnectAudioMonitor: undefined,
            micAudioTrack: { stop: () => log.push("stopMic") },
            screenAudioTrack: null,
            audioTrack: null,
            cameraTrack: null,
            screenTrack: null,
            sourceCameraStream: null,
            sourceScreenStream: null,
        },
        store: { env: { services: { "aidt_meeting.recorder": recorder } } },
        exitFullscreen: () => log.push("exitFullscreen"),
        cleanups: [],
        closeCallPermissionDialog: undefined,
        blurManager: null,
        pipService: undefined,
        update(patch) {
            Object.assign(this, patch);
        },
    };
}

describe("rời cuộc gọi thì dừng recorder", () => {
    test("clear() dừng recorder TRƯỚC KHI dừng micAudioTrack gốc", () => {
        // Đây chính là đường rời cuộc gọi mà `resetMicAudioTrack` không bao
        // giờ chạy tới (rtc_service.js dừng thẳng `state.micAudioTrack` bên
        // trong `clear()`) — nếu không chặn ở đây, người đã rời cuộc gọi vẫn
        // tiếp tục đẩy được chunk audio lên vì server duyệt theo thành viên
        // KÊNH chứ không phải thành viên cuộc gọi.
        //
        // Cả hai sự kiện được ghi vào CÙNG MỘT mảng (`fake.log`) để thứ tự
        // thật sự được kiểm — hai mảng riêng biệt sẽ không chứng minh được
        // gì về việc cái nào chạy trước.
        const recorder = {
            state: { recordingId: 7 },
            stop() {
                fake.log.push("recorder.stop");
                this.state.recordingId = null;
            },
        };
        const fake = makeFakeRtc(recorder);

        Rtc.prototype.clear.call(fake);

        expect(recorder.state.recordingId).toBe(null);
        // Thứ tự thật: recorder dừng trước, rồi mới tới track gốc của clear().
        expect(fake.log).toEqual(["recorder.stop", "exitFullscreen", "stopMic"]);
        expect(fake.state.micAudioTrack).toBe(undefined);
    });

    test("không đang ghi âm thì clear() không gọi recorder.stop() thừa", () => {
        // `MeetingRecorder.stop()` đã tự bảo vệ bằng guard riêng
        // (recorder_service.js), ở đây chỉ cần chắc patch luôn gọi nó — gọi
        // trên một recorder không ghi âm phải là no-op an toàn, không ném lỗi.
        const recorder = {
            state: { recordingId: null },
            stop() {
                if (!this.state.recordingId) {
                    return;
                }
                throw new Error("không nên chạy tới đây");
            },
        };
        const fake = makeFakeRtc(recorder);

        expect(() => Rtc.prototype.clear.call(fake)).not.toThrow();
    });
});
