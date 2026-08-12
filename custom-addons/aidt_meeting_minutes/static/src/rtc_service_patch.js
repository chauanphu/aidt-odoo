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
        // KHÔNG `reattach()` khi đang tạm dừng: `state.recordingId` một
        // mình không còn phân biệt được "đang ghi" với "đang tạm dừng" —
        // `pause()` cố ý giữ nguyên nó để băng thông báo không biến mất.
        // Đổi micro (hoặc cấp lại quyền micro) trong lúc tạm dừng không được
        // phép dựng lại `MediaRecorder`, nếu không phần lời nói trong quãng
        // "không được ghi" lọt thẳng vào biên bản.
        if (recorder?.state.recordingId && !recorder.state.paused) {
            await recorder.reattach();
        }
        return result;
    },

    /**
     * Rời cuộc họp KHÔNG đi qua `resetMicAudioTrack`: `clear()` (gọi từ
     * `endCall()`, tức mọi đường rời cuộc gọi — rời chủ động, rớt mạng, bị
     * host kết thúc...) dừng thẳng `state.micAudioTrack` ở dưới đây, patch
     * trên không bao giờ chạy tới. Server duyệt chunk theo người ĐÃ TỪNG có
     * mặt trong CUỘC GỌI (`participant_partner_ids`, xem `_is_participant`
     * trong `models/meeting_recording.py`) và KHÔNG tự rút quyền đó chỉ vì
     * phiên RTC vừa bị xoá — cố ý, để mẩu cuối cùng (gửi sau khi đã rời) vẫn
     * được nhận. Nên nếu không chặn ở CLIENT bằng `leaveCall()`, người đã
     * rời cuộc gọi vẫn tiếp tục đẩy được chunk audio lên cho tới khi tab bị
     * đóng.
     *
     * Gọi `leaveCall()`, KHÔNG PHẢI `stop()` trơn: `leaveCall()` dọn thêm
     * `lastOfferedId`, để id của bản ghi vừa rời không rò rỉ sang một cuộc
     * gọi khác hoàn toàn không liên quan mà mình join sau đó.
     */
    clear() {
        const recorder = this.store.env.services["aidt_meeting.recorder"];
        recorder?.leaveCall();
        return super.clear();
    },
});
