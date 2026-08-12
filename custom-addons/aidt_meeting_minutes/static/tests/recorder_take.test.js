import { describe, expect, test } from "@odoo/hoot";
import { patchWithCleanup } from "@web/../tests/web_test_helpers";
import { browser } from "@web/core/browser/browser";
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

describe("C1: tạm dừng không bị vô hiệu hoá bởi việc dựng lại MediaRecorder", () => {
    // `pause()` CỐ Ý giữ nguyên `state.recordingId` để băng thông báo không
    // biến mất — nhưng `recordingId` một mình không còn phân biệt được
    // "đang ghi" với "đang tạm dừng". Hai bài test dưới đây kiểm cả hai cửa
    // ngõ duy nhất tạo lại `MediaRecorder`
    // (`_attachToMic`/`reattach()`), phải cùng xét thêm `state.paused`.

    test("reattach() trong lúc đang tạm dừng KHÔNG dựng MediaRecorder mới", async () => {
        // Chèn ngược lỗi để xác nhận test này không phải luôn-xanh: bỏ vế
        // `|| this.state.paused` ở gác đầu tiên của `_attachToMic()`
        // (recorder_service.js) làm `getUserMediaCalled` thành `true` và
        // test ĐỎ — đã tự kiểm tay trước khi thêm bài test này vào bộ.
        const recorder = makeRecorder();
        recorder.state.recordingId = 11;
        recorder.state.paused = true;
        recorder.rtc.state.micAudioTrack = { getSettings: () => ({}) };

        let getUserMediaCalled = false;
        patchWithCleanup(browser.navigator.mediaDevices, {
            getUserMedia: () => {
                getUserMediaCalled = true;
                return Promise.resolve({ getAudioTracks: () => [] });
            },
        });

        await recorder.reattach();

        expect(getUserMediaCalled).toBe(false);
        expect(recorder.recorder).toBe(null);
    });

    test("tạm dừng xen vào lúc _attachToMic() đang chờ quyền micro thì không để lại recorder chạy lậu", async () => {
        // Kịch bản thứ hai của C1: `pause()` xảy ra trong lúc `getUserMedia()`
        // của một `start()`/`resume()` trước đó còn treo (người dùng đang ở
        // hộp thoại xin quyền micro). Promise resolve SAU khi đã tạm dừng —
        // nếu `_attachToMic()` không kiểm lại `state.paused` SAU khi tỉnh
        // dậy, nó dựng `MediaRecorder` mới và ghi lậu suốt quãng tạm dừng dù
        // băng thông báo vẫn ghi "đang tạm dừng".
        //
        // Chèn ngược lỗi để xác nhận không phải luôn-xanh: bỏ vế
        // `|| this.state.paused` ở gác THỨ HAI (ngay sau `getUserMedia`)
        // làm `recorder.recorder` khác `null` sau khi await, và
        // `trackStopped` vẫn `false` — đã tự kiểm tay trước khi thêm bài
        // test này vào bộ.
        const recorder = makeRecorder();
        recorder.state.recordingId = 11;
        recorder.rtc.state.micAudioTrack = { getSettings: () => ({}) };

        let resolveGetUserMedia;
        const pendingGetUserMedia = new Promise((resolve) => {
            resolveGetUserMedia = resolve;
        });
        let trackStopped = false;
        const fakeStream = {
            getAudioTracks: () => [{ stop: () => (trackStopped = true) }],
        };
        patchWithCleanup(browser.navigator.mediaDevices, {
            getUserMedia: () => pendingGetUserMedia,
        });

        const attaching = recorder._attachToMic();

        // Tạm dừng ĐÚNG đường thật: broadcast "paused" → `_onRecordingState`
        // đặt `state.paused = true` rồi gọi `pause()`.
        recorder._onRecordingState({
            action: "paused", recording_id: 11, channel_id: 7,
            take: 0, state: "paused", elapsed_ms: 5000,
        });
        expect(recorder.state.paused).toBe(true);

        // Hộp thoại xin quyền micro giờ mới đóng lại (resolve trễ).
        resolveGetUserMedia(fakeStream);
        await attaching;

        expect(recorder.recorder).toBe(null);
        expect(trackStopped).toBe(true);
    });
});

describe("I2: stop() không để mốc thời gian gốc sống dai qua hai cuộc họp", () => {
    test("stop() đặt lại recorderStartedAt/elapsedAtJoinMs/chunkStartedAt", async () => {
        // Chèn ngược lỗi để xác nhận không luôn-xanh: bỏ ba dòng reset ở
        // cuối phần đồng bộ của `stop()` (recorder_service.js) làm
        // `recorder.recorderStartedAt` vẫn giữ giá trị cũ (khác `null`) sau
        // khi gọi `stop()` — đã tự kiểm tay trước khi thêm bài test này.
        const recorder = makeRecorder();
        // 2.400.000 ms = 40 phút: mô phỏng cuộc họp A đã chạy lâu trước khi
        // máy này vào.
        await recorder.start(11, 2400000, 7, 0);
        expect(recorder.recorderStartedAt).not.toBe(null);
        expect(recorder.elapsedAtJoinMs).toBe(2400000);

        recorder.stop();

        expect(recorder.recorderStartedAt).toBe(null);
        expect(recorder.elapsedAtJoinMs).toBe(0);
        expect(recorder.chunkStartedAt).toBe(null);
    });

    test("cuộc họp SAU trong CÙNG một tab neo mốc MỚI, không thừa hưởng mốc cuộc họp TRƯỚC", async () => {
        // Kịch bản I2: dự cuộc họp A (được ghi) → neo mốc T_A lớn → A kết
        // thúc → 40 phút sau vào cuộc họp B đúng lúc B đang tạm dừng (nhánh
        // `paused` của `syncActiveRecording` không neo mốc) → chủ phòng B
        // bấm "Ghi tiếp". Nếu `stop()` không đặt lại `recorderStartedAt`,
        // `resume()` (chỉ neo mốc mới khi `!this.recorderStartedAt`) sẽ GIỮ
        // NGUYÊN mốc của A, và mọi mẩu của B mang `offset_ms` cộng dồn cả
        // khoảng cách giữa hai cuộc họp.
        const recorder = makeRecorder();
        await recorder.start(11, 2400000, 7, 0);
        recorder.stop();

        // Vào cuộc họp B, đang tạm dừng — đúng những gì
        // `syncActiveRecording()` đặt ở nhánh `info.state === "paused"`,
        // KHÔNG đụng tới mốc thời gian.
        recorder.state.recordingId = 22;
        recorder.state.channelId = 7;
        recorder.state.paused = true;
        recorder.take = 0;

        // Chủ phòng B bấm "Ghi tiếp": server gửi `elapsed_ms` thật của B.
        await recorder.resume(1, 30000);

        expect(recorder.elapsedAtJoinMs).toBe(30000);
        expect(recorder.recorderStartedAt).not.toBe(null);
    });
});
