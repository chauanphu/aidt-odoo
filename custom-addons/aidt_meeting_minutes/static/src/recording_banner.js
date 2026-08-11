import { Component, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

/**
 * Băng thông báo LUÔN HIỆN khi cuộc họp đang được ghi âm — người tham gia
 * không có cách nào tắt/ẩn nó. Đây là cơ chế THỰC THI của việc thông báo bắt
 * buộc cho mọi người dự, không phải chi tiết trang trí. Chỉ CHỦ PHÒNG mới có
 * nút điều khiển (Tạm dừng/Ghi tiếp/Kết thúc) — người dự chỉ được xem trạng
 * thái. Cùng chỗ này còn có nút BẬT ghi âm khi cuộc gọi chưa được ghi.
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
        selfPartnerId: { type: Number, optional: true },
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
        this.store = this.env.services["mail.store"];
    }

    /** Partner của chính máy này. Bus phát một payload chung cho mọi người,
     *  nên việc phân vai (chủ phòng / người dự) phải làm ở client. */
    get selfPartnerId() {
        return this.props.selfPartnerId ?? this.store?.self?.id ?? null;
    }

    /** Có phải người đang bật ghi âm (chủ phòng) hay không. */
    get isHost() {
        return (
            Boolean(this.state.hostPartnerId) &&
            this.state.hostPartnerId === this.selfPartnerId
        );
    }

    get isPaused() {
        return Boolean(this.state.paused);
    }

    /**
     * Bản ghi đang theo dõi có đúng là của KÊNH đang mở hay không.
     *
     * Bus phát trạng thái ghi âm tới mọi thành viên kênh, kể cả người đang ở
     * trong một cuộc gọi ở kênh khác. Không đối chiếu id kênh thì băng trong
     * cuộc gọi B khẳng định "cuộc họp này đang được ghi âm" trong khi bản ghi
     * nằm ở kênh A, và nút "Kết thúc" ở đây gửi `action_stop` cho bản ghi
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
            Boolean(this.state.recordingId) &&
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
        if (this.isPaused) {
            return this.isHost
                ? _t("Ghi âm đang tạm dừng.")
                : _t("Ghi âm đang tạm dừng. Cuộc họp vẫn tiếp tục.");
        }
        return this.isHost
            ? _t("Đang ghi âm biên bản.")
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

    /** Chỉ chủ phòng thấy nút này (Task 8) — server cũng chặn bằng
     *  AccessError nếu người dự cố gọi thẳng qua RPC. */
    async onPause() {
        await this.orm.call(
            "aidt.meeting.recording",
            "action_pause",
            [[this.state.recordingId]],
            {}
        );
    }

    async onResume() {
        await this.orm.call(
            "aidt.meeting.recording",
            "action_resume",
            [[this.state.recordingId]],
            {}
        );
    }

    async onStop() {
        const recordingId = this.state.recordingId;
        // Không có gì đang ghi (băng vừa biến mất giữa lúc bấm, hoặc state
        // rỗng): gọi server với `null` chỉ đổi lấy một traceback `ensure_one`
        // đập vào mặt người dùng.
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
}
