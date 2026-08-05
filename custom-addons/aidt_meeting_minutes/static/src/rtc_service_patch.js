import { patch } from "@web/core/utils/patch";
import { Rtc } from "@mail/discuss/call/common/rtc_service";

/**
 * Micro bị thay track khi người dùng đổi thiết bị hoặc cấp lại quyền. Nếu
 * recorder vẫn giữ clone của track cũ thì nó ghi tiếp một nguồn đã chết và
 * phần còn lại của cuộc họp mất tiếng mà không có lỗi nào lộ ra.
 */
patch(Rtc.prototype, {
    async resetMicAudioTrack(...args) {
        const result = await super.resetMicAudioTrack(...args);
        const recorder = this.store.env.services["aidt_meeting.recorder"];
        if (recorder?.state.recordingId) {
            await recorder._attachToMic();
        }
        return result;
    },
});
