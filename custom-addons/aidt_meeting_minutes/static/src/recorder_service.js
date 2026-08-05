import { registry } from "@web/core/registry";
import { browser } from "@web/core/browser/browser";
import { reactive } from "@odoo/owl";
import { Mp3Encoder } from "@mail/discuss/voice_message/common/mp3_encoder";
import { loadLamejs } from "@mail/discuss/voice_message/common/voice_message_service";

// PhoWhisper resample về 16 kHz; làm sẵn ở trình duyệt bỏ được một bước
// resample phía server và cho phép hạ bitrate mà giọng nói vẫn rõ.
export const SAMPLE_RATE = 16000;
export const CHUNK_MS = 15000;
// Chồng lấn để câu chữ không bị cắt đôi ở mối nối; phần trùng được khử ở
// server khi ghép segment (transcript_builder).
export const OVERLAP_MS = 1500;
// Dưới ngưỡng này coi như im lặng. Whisper bịa chữ từ khoảng lặng số.
export const RMS_FLOOR = 0.005;
const MAX_BUFFERED_CHUNKS = 8;
// Mỗi mẩu chỉ gửi lại MỘT lần. Gửi lại vô hạn là cách chắc chắn nhất để đập
// vào UNIQUE(recording_id, partner_id, seq) khi lần gửi đầu thực ra đã tới
// nơi (mạng đứt sau khi server đã commit), và mỗi lần như vậy server phải
// trả 500 cho một việc hoàn toàn bình thường.
export const MAX_ATTEMPTS = 2;

/**
 * Vị trí tuyệt đối của chunk trong cuộc họp.
 * Chỉ dùng thời gian trôi CỤC BỘ (performance.now()) cộng với phần đã trôi
 * lúc máy này vào họp — không bao giờ dùng đồng hồ tường, nên lệch đồng hồ
 * giữa các máy không thể làm rối thứ tự khi server trộn.
 */
export function computeOffsetMs({ elapsedAtJoinMs, recorderStartedAt, now }) {
    return Math.max(0, Math.round(elapsedAtJoinMs + (now - recorderStartedAt)));
}

/**
 * Có gửi mẩu này lên không.
 *
 * `track.enabled` ở đây KHÔNG phải `MediaStreamTrack.enabled` của micro: cờ
 * đó bị kích hoạt-bằng-giọng-nói bật/tắt nhiều lần mỗi giây
 * (rtc_service.js:1905), đọc nó lúc cắt mẩu là đọc trúng một khoảnh khắc
 * ngẫu nhiên. Nó là "mẩu này có chứa tiếng micro thật hay không", do
 * `_onAudio` dựng lên: trong lúc tắt tiếng không khung nào được mã hoá, nên
 * mẩu rỗng bị chặn ở đây.
 */
export function shouldUpload(track, rms) {
    if (!track || !track.enabled) {
        return false;
    }
    return rms >= RMS_FLOOR;
}

/**
 * Giữ lại đúng phần đuôi dài `maxSamples` mẫu để mồi cho mẩu kế tiếp.
 * Cắt bớt `frames` tại chỗ, trả về số mẫu còn giữ.
 */
export function retainOverlap(frames, frame, maxSamples) {
    frames.push(frame);
    let total = frames.reduce((sum, f) => sum + f.length, 0);
    while (frames.length > 1 && total - frames[0].length >= maxSamples) {
        total -= frames.shift().length;
    }
    return total;
}

/**
 * Mốc bắt đầu của mẩu kế tiếp khi nó được mồi bằng `carriedSamples` mẫu.
 * Phải lùi đúng bằng độ dài đoạn ĐÃ mồi, không phải bằng OVERLAP_MS trên
 * giấy: lùi mà không mồi audio thật thì offset nói một đằng, tiếng nằm một
 * nẻo, và phần khử trùng mối nối ở server không có gì để so.
 */
export function carriedStartAt(now, carriedSamples, sampleRate) {
    return now - (carriedSamples / sampleRate) * 1000;
}

/**
 * Có gửi lại mẩu này không sau một lần gửi hỏng.
 * 4xx là từ chối vĩnh viễn (không thuộc cuộc gọi, bản ghi đã chốt, mẩu quá
 * lớn): gửi lại cũng chỉ nhận đúng câu trả lời đó. `status === 0` nghĩa là
 * hỏng mạng, chưa biết server đã nhận được hay chưa.
 */
export function shouldRetry(status, attempts) {
    if (status >= 400 && status < 500) {
        return false;
    }
    return attempts < MAX_ATTEMPTS;
}

export class MeetingRecorder {
    constructor(env, services) {
        this.env = env;
        this.rtc = services["discuss.rtc"];
        this.bus = services.bus_service;
        this.notification = services.notification;
        // `declinedRecordingId` chứ không phải một cờ boolean: từ chối một
        // cuộc họp không được câm luôn mọi cuộc họp sau đó trong cùng tab,
        // vì không có nút nào để bật lại.
        this.state = reactive({
            recordingId: null,
            declined: false,
            declinedRecordingId: null,
        });

        this.seq = 0;
        this.pending = [];
        this.audioContext = null;
        this.encoder = null;
        this.clonedTrack = null;
        this.sampleRate = SAMPLE_RATE;
        this.overlapFrames = [];
        this.overlapSamples = 0;
        this.chunkHasAudio = false;
        this.mutedNow = false;
        this.lastOfferedId = null;

        this.bus.subscribe("aidt_meeting_minutes/recording_state", (payload) =>
            this._onRecordingState(payload)
        );
    }

    _onRecordingState(payload) {
        if (payload.action === "started") {
            this.lastOfferedId = payload.recording_id;
            this.start(payload.recording_id, payload.elapsed_ms || 0);
        } else {
            // Bản ghi mà mình đã TỪ CHỐI giờ mới thực sự dừng (do người khác
            // bấm "Dừng ghi âm", hoặc cron phát hiện phòng trống): xoá đúng
            // lúc này, không sớm hơn — băng thông báo (Task 10) còn phải
            // hiện "bạn đã từ chối; cuộc họp vẫn đang ghi" cho tới tận đây.
            // Chỉ xoá khi khớp ĐÚNG id vừa dừng: một `stopped` của cuộc họp
            // KHÁC không được xoá dấu từ chối của cuộc họp mình đang xem dở.
            if (this.state.declinedRecordingId === payload.recording_id) {
                this.state.declinedRecordingId = null;
                this.state.declined = false;
            }
            // Bus broadcast tới CẢ THÀNH VIÊN KÊNH: mình có thể là thành
            // viên của một kênh KHÁC (không phải kênh đang gọi) mà một bản
            // ghi ở đó vừa dừng. Chỉ dừng phiên thu THẬT của mình khi payload
            // khớp đúng bản ghi mình đang thu — nếu không, một `stopped`
            // không liên quan sẽ cắt ngang phiên ghi đang chạy thật.
            if (this.state.recordingId === payload.recording_id) {
                this.stop();
            }
        }
    }

    async start(recordingId, elapsedAtJoinMs) {
        if (this.state.recordingId || this.state.declinedRecordingId === recordingId) {
            return;
        }
        // Một bản ghi MỚI, khác hẳn cái đã từ chối, đang bắt đầu — dấu từ
        // chối cũ hết hạn dùng NGAY TẠI ĐÂY, không đợi "stopped" của bản ghi
        // cũ tới: bản ghi đó có thể đã dừng ở một kênh mình không còn theo
        // dõi nữa (đã rời cuộc gọi cũ), nên "stopped" khớp id có thể không
        // bao giờ tới máy này. Không xoá sớm hơn thì băng thông báo sẽ kẹt ở
        // trạng thái "bạn đã từ chối; cuộc họp vẫn đang ghi" vĩnh viễn ngay
        // cả khi bản ghi MỚI này đã dừng từ lâu.
        this.state.declinedRecordingId = null;
        this.state.declined = false;
        this.state.recordingId = recordingId;
        this.lastOfferedId = recordingId;
        this.elapsedAtJoinMs = elapsedAtJoinMs;
        this.recorderStartedAt = browser.performance.now();
        this.seq = 0;
        await this.reattach();
    }

    /** Bám lại vào micro hiện tại — gọi khi RTC thay track. */
    async reattach() {
        return this._attachToMic();
    }

    async _attachToMic() {
        // DỌN TRƯỚC, kiểm tra sau. Clone sống độc lập với track gốc, nên nếu
        // thoát sớm mà chưa dọn thì đúng lúc micro biến mất (người dùng rút
        // quyền: rtc_service.js:2104) clone cũ vẫn mở thiết bị và vẫn đẩy
        // chunk lên — `state.micAudioTrack.stop()` của RTC không đụng tới nó.
        this._teardownGraph();
        // micAudioTrack là micro CỦA CHÍNH MÁY NÀY. `audioTrack` có thể đã bị
        // trộn thêm tiếng của màn hình chia sẻ, không dùng để bóc băng lời
        // của một người.
        const micTrack = this.rtc.state?.micAudioTrack;
        if (!micTrack || !this.state.recordingId) {
            return;
        }
        // CLONE: recorder không bao giờ được làm nhiễu thứ mà người khác
        // đang nghe. Cùng cách media_monitoring.js làm.
        this.clonedTrack = micTrack.clone();

        this.audioContext = new browser.AudioContext({ sampleRate: SAMPLE_RATE });
        // Đọc LẠI tần số thật: `sampleRate` chỉ là gợi ý, trình duyệt có
        // quyền bỏ qua. Sai tần số thì cả header MP3 lẫn phép tính độ dài
        // đoạn chồng lấn đều lệch.
        this.sampleRate = this.audioContext.sampleRate || SAMPLE_RATE;
        await this.audioContext.audioWorklet.addModule("/discuss/voice/worklet_processor");
        // lamejs nằm trong một bundle nạp trễ; `new Mp3Encoder()` sẽ ném
        // ReferenceError nếu gọi trước khi bundle về.
        await loadLamejs();
        const stream = new MediaStream([this.clonedTrack]);
        const source = this.audioContext.createMediaStreamSource(stream);
        this.processor = new browser.AudioWorkletNode(this.audioContext, "processor");
        this._newEncoder();
        this.chunkStartedAt = browser.performance.now();
        this.peakRms = 0;
        this.chunkHasAudio = false;
        this.mutedNow = this._isMuted();
        this.overlapFrames = [];
        this.overlapSamples = 0;

        this.processor.port.onmessage = (event) => this._onAudio(event);
        source.connect(this.processor);
        this.processor.connect(this.audioContext.destination);
    }

    _newEncoder() {
        this.encoder = new Mp3Encoder({ bitRate: 32, sampleRate: this.sampleRate });
    }

    /** Tắt tiếng THẬT (nút tắt micro), không phải trạng thái đang-nói. */
    _isMuted() {
        return Boolean(this.rtc.localSession?.isMute);
    }

    get overlapSampleLimit() {
        return Math.round((this.sampleRate * OVERLAP_MS) / 1000);
    }

    _onAudio(event) {
        if (!this.state.recordingId || !this.encoder || !event.data) {
            return;
        }
        const now = browser.performance.now();
        if (this._isMuted()) {
            if (!this.mutedNow) {
                // Vừa tắt tiếng: chốt phần đã thu rồi NGỪNG HẲN việc mã hoá.
                // Clone giữ `enabled` riêng với track gốc nên nó vẫn nghe
                // thấy mọi thứ sau khi người dùng bấm tắt micro; cứ mã hoá
                // tiếp là cả đoạn nói riêng đó lên thẳng biên bản dưới tên
                // họ. Không thay bằng khung im lặng: nhét khoảng lặng số vào
                // MP3 đúng là kiểu đầu vào làm Whisper bịa chữ, tức là thứ
                // mà RMS_FLOOR sinh ra để tránh.
                this.mutedNow = true;
                this._flushChunk(now, { carryOverlap: false });
            }
            return;
        }
        if (this.mutedNow) {
            // Bật tiếng lại: mở mẩu mới từ đây, không nối vào phần trước.
            this.mutedNow = false;
            this.chunkStartedAt = now;
            this.peakRms = 0;
            this.chunkHasAudio = false;
        }
        this.chunkHasAudio = true;
        this.peakRms = Math.max(this.peakRms, this._rms(event.data));
        this.encoder.encode(event.data);
        this.overlapSamples = retainOverlap(
            this.overlapFrames, event.data, this.overlapSampleLimit
        );
        if (now - this.chunkStartedAt >= CHUNK_MS) {
            this._flushChunk(now);
        }
    }

    _rms(samples) {
        let total = 0;
        for (let i = 0; i < samples.length; i++) {
            total += samples[i] * samples[i];
        }
        return Math.sqrt(total / (samples.length || 1));
    }

    _flushChunk(now, { carryOverlap = true } = {}) {
        const buffer = this.encoder.finish();
        const offsetMs = computeOffsetMs({
            elapsedAtJoinMs: this.elapsedAtJoinMs,
            recorderStartedAt: this.recorderStartedAt,
            now: this.chunkStartedAt,
        });
        const durationMs = Math.round(now - this.chunkStartedAt);
        const upload = shouldUpload({ enabled: this.chunkHasAudio }, this.peakRms);

        // Mồi mẩu kế tiếp bằng đúng đoạn audio vừa giữ lại, rồi lùi mốc bắt
        // đầu đúng bằng độ dài đoạn đó.
        const carried = carryOverlap ? this.overlapFrames : [];
        this.overlapFrames = [];
        this.overlapSamples = 0;
        this._newEncoder();
        let carriedSamples = 0;
        for (const frame of carried) {
            this.encoder.encode(frame);
            this.overlapSamples = retainOverlap(
                this.overlapFrames, frame, this.overlapSampleLimit
            );
            carriedSamples += frame.length;
        }
        this.chunkStartedAt = carriedStartAt(now, carriedSamples, this.sampleRate);
        this.peakRms = 0;
        this.chunkHasAudio = carriedSamples > 0;

        if (!upload || !buffer || !buffer.length) {
            return;
        }
        const blob = new Blob(buffer, { type: "audio/mpeg" });
        this._send({ blob, seq: this.seq++, offsetMs, durationMs, attempts: 0 });
    }

    async _send(chunk) {
        chunk.attempts++;
        // Ghim recordingId vào mẩu: mẩu tồn đọng được gửi lại trong `stop()`,
        // lúc đó `state.recordingId` đã bị xoá.
        chunk.recordingId = chunk.recordingId ?? this.state.recordingId;
        const form = new FormData();
        form.append("recording_id", chunk.recordingId);
        form.append("seq", chunk.seq);
        form.append("offset_ms", chunk.offsetMs);
        form.append("duration_ms", chunk.durationMs);
        form.append("audio", chunk.blob, `chunk-${chunk.seq}.mp3`);
        let status = 0;
        try {
            const response = await browser.fetch("/aidt_meeting/chunk", {
                method: "POST",
                body: form,
            });
            if (response.ok) {
                return;
            }
            status = response.status;
        } catch {
            status = 0;
        }
        if (!shouldRetry(status, chunk.attempts)) {
            return;
        }
        // Buffer có trần: giữ vô hạn sẽ ăn hết RAM của tab trong một cuộc
        // họp dài khi mạng hỏng lâu. Bỏ mẩu cũ nhất và để server đánh dấu
        // khoảng khuyết — thà thiếu một đoạn còn hơn sập cả tab.
        this.pending.push(chunk);
        while (this.pending.length > MAX_BUFFERED_CHUNKS) {
            this.pending.shift();
        }
    }

    _flushPending() {
        const queued = this.pending.splice(0, this.pending.length);
        for (const chunk of queued) {
            this._send(chunk);
        }
    }

    stop() {
        if (!this.state.recordingId) {
            return;
        }
        if (this.encoder) {
            this._flushChunk(browser.performance.now(), { carryOverlap: false });
        }
        this._flushPending();
        this._teardownGraph();
        this.state.recordingId = null;
    }

    /** Từ chối ghi âm cuộc họp NÀY (nút trên băng thông báo của Task 10). */
    decline() {
        this.state.declinedRecordingId = this.state.recordingId ?? this.lastOfferedId;
        this.state.declined = true;
        this.stop();
    }

    /**
     * Rời cuộc gọi (gọi từ patch `clear()` của `rtc_service_patch.js` — mọi
     * đường rời cuộc gọi đều đi qua đó). Dọn NHIỀU HƠN `stop()`: xoá cả dấu
     * từ chối, vì nó chỉ có ý nghĩa TRONG đúng cuộc gọi vừa rời.
     *
     * Không có bước này, dấu từ chối của cuộc họp A rò rỉ sang cuộc gọi B
     * hoàn toàn không liên quan mà mình join sau đó: `stop()` một mình
     * không đụng tới `declinedRecordingId` (đúng ý — nó cần sống sót qua
     * chính `stop()` nội bộ của `decline()` để băng thông báo còn hiện được
     * "bạn đã từ chối; cuộc họp vẫn đang ghi"), và nếu A vẫn đang ghi lúc
     * mình rời thì "stopped" khớp id của A có thể KHÔNG BAO GIỜ tới máy này
     * nữa (đã rời kênh A). Kết quả nếu không dọn ở đây: băng ở B hiện nhầm
     * "cuộc họp vẫn đang ghi" dù B không hề được ghi, ẩn mất nút "Bật ghi
     * âm" (vì `canStart` coi B là đang có bản ghi), và nút "Dừng ghi âm" ở B
     * gửi `action_stop` cho ĐÚNG bản ghi của A — server chấp nhận vì mình
     * vẫn còn là thành viên kênh A.
     */
    leaveCall() {
        this.stop();
        this.state.declinedRecordingId = null;
        this.state.declined = false;
        this.lastOfferedId = null;
    }

    _teardownGraph() {
        this.processor?.disconnect();
        this.clonedTrack?.stop();
        if (this.audioContext && this.audioContext.state !== "closed") {
            this.audioContext.close();
        }
        this.processor = null;
        this.clonedTrack = null;
        this.audioContext = null;
        this.encoder = null;
        this.overlapFrames = [];
        this.overlapSamples = 0;
        this.chunkHasAudio = false;
    }
}

export const meetingRecorderService = {
    dependencies: ["discuss.rtc", "bus_service", "notification"],
    start(env, services) {
        return new MeetingRecorder(env, services);
    },
};

registry.category("services").add("aidt_meeting.recorder", meetingRecorderService);
