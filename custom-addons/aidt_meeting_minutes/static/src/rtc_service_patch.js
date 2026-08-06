import { patch } from "@web/core/utils/patch";
import { Rtc } from "@mail/discuss/call/common/rtc_service";

/**
 * Micro bị thay track khi người dùng đổi thiết bị hoặc cấp lại quyền. Nếu
 * recorder vẫn giữ clone của track cũ thì nó ghi tiếp một nguồn đã chết và
 * phần còn lại của cuộc họp mất tiếng mà không có lỗi nào lộ ra.
 */
patch(Rtc.prototype, {
    /**
     * Vào một cuộc gọi: hỏi lại server xem kênh này có đang được ghi âm không.
     *
     * Broadcast `started` chỉ phát MỘT LẦN, lúc người bật bấm nút. Ai vào họp
     * sau thời điểm đó không nhận được gì cả — và nếu không hỏi lại ở đây thì
     * với họ, băng đồng thuận không tồn tại và tiếng của họ không được thu.
     * Không `await`: việc vào cuộc gọi không được phụ thuộc vào một lượt RPC.
     */
    async joinCall(...args) {
        const result = await super.joinCall(...args);
        const recorder = this.store.env.services["aidt_meeting.recorder"];
        recorder?.syncActiveRecording();
        return result;
    },

    async resetMicAudioTrack(...args) {
        const result = await super.resetMicAudioTrack(...args);
        const recorder = this.store.env.services["aidt_meeting.recorder"];
        if (recorder?.state.recordingId) {
            await recorder.reattach();
        }
        return result;
    },

    /**
     * Rời cuộc họp KHÔNG đi qua `resetMicAudioTrack`: `clear()` (gọi từ
     * `endCall()`, tức mọi đường rời cuộc gọi — rời chủ động, rớt mạng, bị
     * host kết thúc...) dừng thẳng `state.micAudioTrack` ở dưới đây, patch
     * trên không bao giờ chạy tới. Server duyệt chunk theo THÀNH VIÊN KÊNH,
     * không phải thành viên cuộc gọi (`models/meeting_recording.py:101-103`),
     * nên nếu không chặn ở đây, người đã rời cuộc gọi vẫn tiếp tục đẩy được
     * chunk audio lên cho tới khi tab bị đóng.
     *
     * Gọi `leaveCall()`, KHÔNG PHẢI `stop()` trơn: `stop()` chỉ dọn phiên
     * thu đang chạy, còn nguyên dấu "đã từ chối" — đúng ý khi gọi từ
     * `decline()`, nhưng SAI khi rời hẳn cuộc gọi, vì dấu đó sẽ rò rỉ sang
     * cuộc gọi khác hoàn toàn không liên quan mà mình join sau đó.
     */
    clear() {
        const recorder = this.store.env.services["aidt_meeting.recorder"];
        recorder?.leaveCall();
        return super.clear();
    },
});
