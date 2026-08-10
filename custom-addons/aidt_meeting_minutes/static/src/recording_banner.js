import { Component, useState, useRef } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

/**
 * Băng thông báo LUÔN HIỆN khi cuộc họp đang được ghi âm — người tham gia
 * không có cách nào tắt/ẩn nó, chỉ có thể "Từ chối" (ngừng phần thu tiếng
 * của riêng mình) hoặc "Dừng ghi âm" (dừng hẳn cho cả cuộc họp). Đây là cơ
 * chế THỰC THI của việc xin sự đồng ý ghi âm, không phải chi tiết trang trí.
 * Cùng chỗ này còn có nút BẬT ghi âm khi cuộc gọi chưa được ghi.
 */
export class RecordingBanner extends Component {
    static template = "aidt_meeting_minutes.RecordingBanner";
    static props = {
        recorder: { type: Object, optional: true },
        isActiveCall: { type: Boolean, optional: true },
        // discuss.channel id thật (Thread.id khi model === "discuss.channel"
        // CHÍNH LÀ id đó, không qua biến đổi nào — xem call.js `get channel()`
        // và các chỗ khác trong addons/mail dùng thẳng `thread.id` làm
        // channel_id khi gọi server, ví dụ channel_invitation.js).
        channelId: { type: Number, optional: true },
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
        this.mockAudioInput = useRef("mockAudioInput");
    }

    /**
     * Id bản ghi cần hiển thị. KHÔNG chỉ `state.recordingId`: sau khi từ
     * chối, `decline()` gọi thẳng `stop()` và xoá `recordingId` về null trên
     * MÁY CỦA MÌNH — nhưng cuộc họp vẫn đang được ghi trên máy người khác.
     * `declinedRecordingId` giữ lại đúng id đó cho tới khi có broadcast
     * "stopped" khớp id (xem `_onRecordingState` ở recorder_service.js).
     */
    get displayedRecordingId() {
        return this.state.recordingId || this.state.declinedRecordingId;
    }

    get isDeclined() {
        return !this.state.recordingId && Boolean(this.state.declinedRecordingId);
    }

    /**
     * Bản ghi đang theo dõi có đúng là của KÊNH đang mở hay không.
     *
     * Bus phát trạng thái ghi âm tới mọi thành viên kênh, kể cả người đang ở
     * trong một cuộc gọi ở kênh khác. Không đối chiếu id kênh thì băng trong
     * cuộc gọi B khẳng định "cuộc họp này đang được ghi âm" trong khi bản ghi
     * nằm ở kênh A, và nút "Dừng ghi âm" ở đây gửi `action_stop` cho bản ghi
     * của A.
     *
     * Thiếu một trong hai id (component được mount lẻ, hoặc bản ghi tới từ
     * broadcast cũ chưa kèm kênh) thì không lọc — `recorder_service` đã chặn
     * ở tầng dưới, và ẩn băng nhầm còn tệ hơn hiện thừa.
     */
    get isForThisChannel() {
        if (!this.props.channelId || !this.state.channelId) {
            return true;
        }
        return this.state.channelId === this.props.channelId;
    }

    get isVisible() {
        return (
            Boolean(this.displayedRecordingId) &&
            this.props.isActiveCall &&
            this.isForThisChannel
        );
    }

    /** Nút "Bật ghi âm": chỉ khi đang trong cuộc gọi và chưa có gì đang ghi. */
    get canStart() {
        return (
            !this.isVisible &&
            this.props.isActiveCall &&
            Boolean(this.props.channelId)
        );
    }

    get label() {
        return this.isDeclined
            ? _t("Bạn đã từ chối; cuộc họp vẫn đang được ghi âm.")
            : _t("Cuộc họp đang được ghi âm để tạo biên bản.");
    }

    /**
     * Bật ghi âm. `action_start_for_channel` là public wrapper của
     * `_start_for_channel` (Task 2): mọi kiểm tra phân quyền — thành viên
     * kênh, chỉ chủ trì được bật cuộc họp có lịch, ngưỡng độ mật — vẫn chạy
     * nguyên vẹn ở server và ném lỗi bình thường nếu bị chặn. KHÔNG bắt lỗi
     * ở đây: để nó rơi ra ngoài cho hộp thoại lỗi mặc định của web client
     * hiện lên, thay vì âm thầm nuốt mất một AccessError/UserError hợp lệ.
     */
    async onStart() {
        await this.orm.call(
            "aidt.meeting.recording",
            "action_start_for_channel",
            [this.props.channelId],
            {}
        );
    }

    async onDecline() {
        // Đọc recordingId TRƯỚC khi gọi decline(): decline() gọi thẳng
        // stop(), và stop() xoá state.recordingId về null ngay lập tức —
        // đọc sau sẽ gửi id sai (null/id đã cũ) lên server.
        const recordingId = this.state.recordingId;
        // Không có gì đang ghi (băng vừa biến mất giữa lúc bấm, hoặc state
        // rỗng): gọi server với `null` chỉ đổi lấy một traceback `ensure_one`
        // đập vào mặt người dùng.
        if (!recordingId) {
            return;
        }
        // Chỉ dừng upload của MÌNH; bản ghi của người khác vẫn tiếp tục.
        this.recorder.decline();
        // `action_decline` — PUBLIC, KHÔNG nhận partner từ client: server tự
        // lấy partner từ phiên đăng nhập (`_decline` gốc của Task 2 nhận
        // partner làm đối số, nhưng đối số ĐÓ không bao giờ nên tới từ JS —
        // và dù có muốn cũng không gọi được: mọi tên phương thức bắt đầu
        // bằng "_" bị `odoo/service/model.py::get_public_method` chặn thẳng
        // ở tầng RPC).
        await this.orm.call(
            "aidt.meeting.recording",
            "action_decline",
            [[recordingId]],
            {}
        );
    }

    async onStop() {
        // Bất kỳ người tham gia nào cũng dừng được toàn bộ bản ghi — xem
        // giả định ở §4 của spec. Dùng `displayedRecordingId`: người đã từ
        // chối vẫn phải dừng được cho cả cuộc họp.
        const recordingId = this.displayedRecordingId;
        if (!recordingId) {
            return;
        }
        await this.orm.call(
            "aidt.meeting.recording",
            "action_stop",
            [[recordingId]],
            {}
        );
    }

    onMockAudioClick() {
        if (this.mockAudioInput.el) {
            this.mockAudioInput.el.click();
        }
    }

    async onMockAudioChange(ev) {
        const file = ev.target.files[0];
        if (!file) return;
        if (this.recorder && typeof this.recorder.sendMockAudio === 'function') {
            await this.recorder.sendMockAudio(file);
        }
        ev.target.value = ""; // clear input
    }
}
