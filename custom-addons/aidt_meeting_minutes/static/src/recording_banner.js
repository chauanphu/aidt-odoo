import { Component, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

/**
 * Băng thông báo LUÔN HIỆN khi cuộc họp đang được ghi âm — người tham gia
 * không có cách nào tắt/ẩn nó, chỉ có thể "Từ chối" (ngừng phần thu tiếng
 * của riêng mình) hoặc "Dừng ghi âm" (dừng hẳn cho cả cuộc họp). Đây là cơ
 * chế THỰC THI của việc xin sự đồng ý ghi âm, không phải chi tiết trang trí.
 */
export class RecordingBanner extends Component {
    static template = "aidt_meeting_minutes.RecordingBanner";
    static props = {
        recorder: { type: Object, optional: true },
        isActiveCall: { type: Boolean, optional: true },
    };
    // Mặc định `true` để component vẫn hiện đúng khi được mount/test riêng lẻ
    // (không đi qua template `discuss.Call`, nơi luôn truyền giá trị thật).
    // Trong `call.xml`, prop này luôn được truyền = `isActiveCall` thật của
    // Call — băng KHÔNG được hiện chỉ vì `recordingId` có giá trị, vì bus
    // broadcast tới CẢ THÀNH VIÊN KÊNH không có mặt trong cuộc gọi.
    static defaultProps = { isActiveCall: true };

    setup() {
        this.orm = useService("orm");
        this.recorder = this.props.recorder || useService("aidt_meeting.recorder");
        this.state = useState(this.recorder.state);
    }

    get label() {
        return _t("Cuộc họp đang được ghi âm để tạo biên bản.");
    }

    get isVisible() {
        return Boolean(this.state.recordingId) && this.props.isActiveCall;
    }

    async onDecline() {
        // Đọc recordingId TRƯỚC khi gọi decline(): decline() gọi thẳng
        // stop(), và stop() xoá state.recordingId về null ngay lập tức —
        // đọc sau sẽ gửi `[[null]]` lên _decline.
        const recordingId = this.state.recordingId;
        // Chỉ dừng upload của MÌNH; bản ghi của người khác vẫn tiếp tục.
        this.recorder.decline();
        await this.orm.call(
            "aidt.meeting.recording",
            "_decline",
            [[recordingId]],
            {}
        );
    }

    async onStop() {
        // Bất kỳ người tham gia nào cũng dừng được toàn bộ bản ghi — xem
        // giả định ở §4 của spec.
        await this.orm.call(
            "aidt.meeting.recording",
            "action_stop",
            [[this.state.recordingId]],
            {}
        );
    }
}
