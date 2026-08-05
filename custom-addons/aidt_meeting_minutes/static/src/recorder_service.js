import { registry } from "@web/core/registry";
import { browser } from "@web/core/browser/browser";
import { reactive } from "@odoo/owl";
import { Mp3Encoder } from "@mail/discuss/voice_message/common/mp3_encoder";
import { loadLamejs } from "@mail/discuss/voice_message/common/voice_message_service";

// PhoWhisper resample về 16 kHz; làm sẵn ở trình duyệt bỏ được một bước
// resample phía server và cho phép hạ bitrate mà giọng nói vẫn rõ.
const SAMPLE_RATE = 16000;
const CHUNK_MS = 15000;
// Chồng lấn để câu chữ không bị cắt đôi ở mối nối; phần trùng được khử ở
// server khi ghép segment (xem transcript_builder._dedupe_seam).
const OVERLAP_MS = 1500;
const OVERLAP_SAMPLES = Math.round((SAMPLE_RATE * OVERLAP_MS) / 1000);
// Dưới ngưỡng này coi như im lặng. Whisper bịa chữ từ khoảng lặng số.
const RMS_FLOOR = 0.005;
const MAX_BUFFERED_CHUNKS = 8;
// Mỗi mẩu chỉ gửi lại MỘT lần. Gửi lại vô hạn là cách chắc chắn nhất để
// đập vào UNIQUE(recording_id, partner_id, seq) khi lần gửi đầu thực ra đã
// tới nơi (mạng đứt sau khi server đã commit), và mỗi lần như vậy server
// phải trả 500 cho một việc hoàn toàn bình thường.
const MAX_ATTEMPTS = 2;

/**
 * Vị trí tuyệt đối của chunk trong cuộc họp.
 * Chỉ dùng thời gian trôi CỤC BỘ (performance.now()) cộng với phần đã trôi
 * lúc máy này vào họp — không bao giờ dùng đồng hồ tường, nên lệch đồng hồ
 * giữa các máy không thể làm rối thứ tự khi server trộn.
 */
export function computeOffsetMs({ elapsedAtJoinMs, recorderStartedAt, now }) {
    return Math.max(0, Math.round(elapsedAtJoinMs + (now - recorderStartedAt)));
}

/** Tắt tiếng hoặc quá nhỏ thì không gửi. */
export function shouldUpload(track, rms) {
    if (!track || !track.enabled) {
        return false;
    }
    return rms >= RMS_FLOOR;
}

export class MeetingRecorder {
    constructor(env, services) {
        this.env = env;
        this.rtc = services["discuss.rtc"];
        this.bus = services.bus_service;
        this.notification = services.notification;
        this.state = reactive({ recordingId: null, declined: false });

        this.seq = 0;
        this.pending = [];
        this.audioContext = null;
        this.encoder = null;
        this.clonedTrack = null;
        this.sourceTrack = null;
        this.overlapFrames = [];
        this.overlapSamples = 0;

        this.bus.subscribe("aidt_meeting_minutes/recording_state", (payload) =>
            this._onRecordingState(payload)
        );
    }

    _onRecordingState(payload) {
        if (payload.action === "started") {
            this.start(payload.recording_id, payload.elapsed_ms || 0);
        } else {
            this.stop();
        }
    }

    async start(recordingId, elapsedAtJoinMs) {
        if (this.state.recordingId || this.state.declined) {
            return;
        }
        this.state.recordingId = recordingId;
        this.elapsedAtJoinMs = elapsedAtJoinMs;
        this.recorderStartedAt = browser.performance.now();
        this.seq = 0;
        await this._attachToMic();
    }

    async _attachToMic() {
        // micAudioTrack là micro CỦA CHÍNH MÁY NÀY. `audioTrack` có thể đã bị
        // trộn thêm tiếng của màn hình chia sẻ, không dùng để bóc băng lời
        // của một người.
        const micTrack = this.rtc.state?.micAudioTrack;
        if (!micTrack || !this.state.recordingId) {
            return;
        }
        this._teardownGraph();
        // CLONE: recorder không bao giờ được làm nhiễu thứ mà người khác
        // đang nghe. Cùng cách media_monitoring.js làm.
        this.clonedTrack = micTrack.clone();
        this.sourceTrack = micTrack;

        this.audioContext = new browser.AudioContext({ sampleRate: SAMPLE_RATE });
        await this.audioContext.audioWorklet.addModule("/discuss/voice/worklet_processor");
        // lamejs nằm trong một bundle nạp trễ; `new Mp3Encoder()` sẽ ném
        // ReferenceError nếu gọi trước khi bundle về.
        await loadLamejs();
        const stream = new MediaStream([this.clonedTrack]);
        const source = this.audioContext.createMediaStreamSource(stream);
        this.processor = new browser.AudioWorkletNode(this.audioContext, "processor");
        this.encoder = new Mp3Encoder({ bitRate: 32, sampleRate: SAMPLE_RATE });
        this.chunkStartedAt = browser.performance.now();
        this.peakRms = 0;
        this.chunkEnabled = false;
        this.overlapFrames = [];
        this.overlapSamples = 0;

        this.processor.port.onmessage = (event) => this._onAudio(event);
        source.connect(this.processor);
        this.processor.connect(this.audioContext.destination);
    }

    _onAudio(event) {
        if (!this.state.recordingId || !this.encoder || !event.data) {
            return;
        }
        // Clone giữ `enabled` RIÊNG với track gốc, nên nó vẫn thu tiếng thật
        // cả khi người dùng đã tắt micro. Phải hỏi track GỐC, và hỏi ở từng
        // khung: kích hoạt bằng giọng nói bật/tắt `enabled` liên tục, đọc
        // đúng một lần lúc cắt chunk sẽ vứt nhầm cả đoạn đang nói.
        if (this.sourceTrack?.enabled) {
            this.chunkEnabled = true;
            this.peakRms = Math.max(this.peakRms, this._rms(event.data));
        }
        this.encoder.encode(event.data);
        this._retainOverlap(event.data);
        const now = browser.performance.now();
        if (now - this.chunkStartedAt >= CHUNK_MS) {
            this._flushChunk(now);
        }
    }

    /** Giữ lại OVERLAP_MS cuối cùng để mồi cho chunk kế tiếp. */
    _retainOverlap(samples) {
        this.overlapFrames.push(samples);
        this.overlapSamples += samples.length;
        while (this.overlapFrames.length > 1 &&
               this.overlapSamples - this.overlapFrames[0].length >= OVERLAP_SAMPLES) {
            this.overlapSamples -= this.overlapFrames.shift().length;
        }
    }

    _rms(samples) {
        let total = 0;
        for (let i = 0; i < samples.length; i++) {
            total += samples[i] * samples[i];
        }
        return Math.sqrt(total / (samples.length || 1));
    }

    _flushChunk(now) {
        const buffer = this.encoder.finish();
        const offsetMs = computeOffsetMs({
            elapsedAtJoinMs: this.elapsedAtJoinMs,
            recorderStartedAt: this.recorderStartedAt,
            now: this.chunkStartedAt,
        });
        const durationMs = Math.round(now - this.chunkStartedAt);
        const upload = shouldUpload({ enabled: this.chunkEnabled }, this.peakRms);

        // Mồi chunk kế tiếp bằng đúng đoạn audio vừa giữ lại, rồi lùi mốc bắt
        // đầu đúng bằng độ dài đoạn đó — hai chunk chồng nhau THẬT chứ không
        // chỉ chồng nhau trên giấy tờ, nếu không phần khử trùng ở server
        // không có gì để so.
        const carried = this.overlapFrames;
        this.overlapFrames = [];
        this.overlapSamples = 0;
        this.encoder = new Mp3Encoder({ bitRate: 32, sampleRate: SAMPLE_RATE });
        let carriedSamples = 0;
        for (const frame of carried) {
            this.encoder.encode(frame);
            this._retainOverlap(frame);
            carriedSamples += frame.length;
        }
        this.chunkStartedAt = now - (carriedSamples / SAMPLE_RATE) * 1000;
        this.peakRms = 0;
        this.chunkEnabled = false;

        if (!upload || !buffer || !buffer.length) {
            return;
        }
        const blob = new Blob(buffer, { type: "audio/mpeg" });
        this._send({ blob, seq: this.seq++, offsetMs, durationMs, attempts: 0 });
    }

    async _send(chunk) {
        chunk.attempts++;
        const form = new FormData();
        form.append("recording_id", this.state.recordingId);
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
        if ((status >= 400 && status < 500) || chunk.attempts >= MAX_ATTEMPTS) {
            // 4xx là từ chối vĩnh viễn (không thuộc cuộc gọi, bản ghi đã
            // dừng, mẩu quá lớn): gửi lại cũng chỉ nhận đúng câu trả lời đó.
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
            this._flushChunk(browser.performance.now());
        }
        this._flushPending();
        this._teardownGraph();
        this.state.recordingId = null;
    }

    decline() {
        this.state.declined = true;
        this.stop();
    }

    _teardownGraph() {
        this.processor?.disconnect();
        this.clonedTrack?.stop();
        if (this.audioContext && this.audioContext.state !== "closed") {
            this.audioContext.close();
        }
        this.processor = null;
        this.clonedTrack = null;
        this.sourceTrack = null;
        this.audioContext = null;
        this.encoder = null;
        this.overlapFrames = [];
        this.overlapSamples = 0;
    }
}

export const meetingRecorderService = {
    dependencies: ["discuss.rtc", "bus_service", "notification"],
    start(env, services) {
        return new MeetingRecorder(env, services);
    },
};

registry.category("services").add("aidt_meeting.recorder", meetingRecorderService);
