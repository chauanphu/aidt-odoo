import { registry } from "@web/core/registry";
import { browser } from "@web/core/browser/browser";
import { reactive } from "@odoo/owl";

export const CHUNK_MS = 30000;
const MAX_BUFFERED_CHUNKS = 8;
export const MAX_ATTEMPTS = 2;

export function computeOffsetMs({ elapsedAtJoinMs, recorderStartedAt, now }) {
    return Math.max(0, Math.round(elapsedAtJoinMs + (now - recorderStartedAt)));
}

// Dùng khi không đọc nổi độ dài thật của tệp nạp tay (xem `sendMockAudio`).
const MOCK_FALLBACK_DURATION_MS = 30000;

/**
 * Độ dài thật của một blob audio, tính bằng ms.
 *
 * Đọc qua `<audio>` chứ không đoán theo kích thước tệp: `duration_ms` đi
 * thẳng vào `aidt.meeting.chunk` và là thứ worker dùng để dựng trục thời
 * gian của bản bóc băng. Tệp webm do MediaRecorder sinh ra thường báo
 * `duration = Infinity` (không có Cues), nên phải có đường lui.
 */
function readAudioDurationMs(blob) {
    return new Promise((resolve) => {
        const url = URL.createObjectURL(blob);
        const audio = new Audio();
        const done = (ms) => {
            URL.revokeObjectURL(url);
            resolve(ms);
        };
        audio.addEventListener("loadedmetadata", () => {
            const seconds = audio.duration;
            done(Number.isFinite(seconds) && seconds > 0
                ? Math.round(seconds * 1000)
                : MOCK_FALLBACK_DURATION_MS);
        }, { once: true });
        audio.addEventListener(
            "error", () => done(MOCK_FALLBACK_DURATION_MS), { once: true });
        audio.src = url;
    });
}

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
        this.orm = services.orm;
        this.state = reactive({
            recordingId: null,
            channelId: null,
            paused: false,
            hostPartnerId: null,
        });

        this.take = 0;
        this.seq = 0;
        this.pending = [];
        this.activeUploads = new Set();
        this.isStopping = false;
        this.clonedTrack = null;
        this.recorder = null;
        this.lastOfferedId = null;
        
        // VAD (Voice Activity Detection)
        this.audioContext = null;
        this.analyser = null;
        this.vadInterval = null;
        this.hasVoiceActivity = false;

        this.bus.subscribe("aidt_meeting_minutes/recording_state", (payload) =>
            this._onRecordingState(payload)
        );
    }

    get currentChannelId() {
        return this.rtc.state?.channel?.id ?? null;
    }

    async syncActiveRecording() {
        const channelId = this.currentChannelId;
        if (!channelId || this.state.recordingId) {
            return;
        }
        let info;
        try {
            info = await this.orm.call(
                "aidt.meeting.recording",
                "action_active_recording",
                [channelId],
                {}
            );
        } catch {
            return;
        }
        if (this.currentChannelId !== channelId) {
            return;
        }
        // Chủ phòng của CUỘC GỌI (không phải của một bản ghi). Server trả
        // khoá này cho PHÒNG HỌP kể cả khi chưa có bản ghi nào, để nút "Bật
        // ghi âm" chỉ hiện cho đúng người được phép bấm
        // (RecordingBanner.canStart). Kênh THƯỜNG thì KHÔNG: từ 19.0.1.4.0
        // `action_active_recording` trả `{}` tuyệt đối cho kênh không có
        // cuộc họp và không có bản ghi đang mở — ghi âm chỉ tồn tại trong
        // phòng họp, nên trả chủ phòng ở đó chỉ làm mọi thành viên thấy một
        // nút bấm vào để ăn AccessError. Vì vậy `?? null` là nhánh CHẠY
        // THẬT, không phải phòng thủ thừa.
        // Không đặt trong nhánh `if (info.recording_id)` bên dưới: đó chính
        // là lúc CHƯA có bản ghi, tức là lúc cần giá trị này nhất.
        this.state.hostPartnerId = info?.host_partner_id ?? null;
        if (!info?.recording_id) {
            return;
        }
        if (info.state === "paused") {
            // Hiện băng nhưng KHÔNG thu: chờ broadcast `resumed`.
            this.state.recordingId = info.recording_id;
            this.state.channelId = channelId;
            this.state.paused = true;
            this.take = info.take || 0;
            return;
        }
        await this.start(info.recording_id, info.elapsed_ms || 0, channelId,
                         info.take || 0);
    }

    _onRecordingState(payload) {
        if (payload.action === "summary_done" || payload.action === "summary_failed") {
            const hash = window.location.hash || "";
            if (hash.includes("model=aidt.meeting.recording") &&
                hash.includes("id=" + payload.recording_id)) {
                this.env.services.action.doAction({
                    type: "ir.actions.client", tag: "soft_reload" });
            }
            return;
        }

        const channelId = this.currentChannelId;
        if (!channelId || payload.channel_id !== channelId) {
            return;
        }

        if (payload.action === "started") {
            this.state.hostPartnerId = payload.host_partner_id;
            this.start(payload.recording_id, payload.elapsed_ms || 0, channelId,
                       payload.take || 0);
            return;
        }

        if (this.state.recordingId !== payload.recording_id) {
            return;
        }

        if (payload.action === "paused") {
            // KHÔNG xoá recordingId: bản ghi vẫn đang hoạt động, chỉ là
            // không thu nữa. Xoá ở đây thì băng thông báo biến mất và người
            // dự tưởng cuộc họp đã kết thúc.
            this.state.paused = true;
            this.pause();
        } else if (payload.action === "resumed") {
            this.state.paused = false;
            this.resume(payload.take || 0, payload.elapsed_ms || 0);
        } else {
            this.stop();
        }
    }

    async start(recordingId, elapsedAtJoinMs, channelId = null, take = 0) {
        if (this.state.recordingId || this.isStopping) {
            return;
        }
        this.state.recordingId = recordingId;
        this.state.channelId = channelId ?? this.currentChannelId;
        this.state.paused = false;
        this.lastOfferedId = recordingId;
        this.elapsedAtJoinMs = elapsedAtJoinMs;
        this.recorderStartedAt = browser.performance.now();
        this.take = take;
        this.seq = 0;
        await this.reattach();
    }

    async reattach() {
        return this._attachToMic();
    }

    async _attachToMic() {
        this._teardownGraph();
        const micTrack = this.rtc.state?.micAudioTrack;
        // `state.paused` PHẢI chặn ở đây, không chỉ `state.recordingId`:
        // `pause()` CỐ Ý giữ nguyên `recordingId` để băng thông báo không
        // biến mất, nên `recordingId` một mình không còn phân biệt được
        // "đang ghi" với "đang tạm dừng". Thiếu vế này thì bất cứ thứ gì gọi
        // `reattach()`/`_attachToMic()` trong lúc tạm dừng (đổi mic, mất rồi
        // cấp lại quyền micro...) dựng một `MediaRecorder` mới và THU SUỐT
        // quãng tạm dừng trong khi băng vẫn ghi "đang tạm dừng".
        if (!micTrack || !this.state.recordingId || this.state.paused) {
            return;
        }

        let stream;
        try {
            const deviceId = micTrack.getSettings()?.deviceId;
            const constraints = deviceId ? { audio: { deviceId: { exact: deviceId } } } : { audio: true };
            // Get an independent mic stream to avoid Chrome WebRTC silent track bugs
            stream = await navigator.mediaDevices.getUserMedia(constraints);
            this.clonedTrack = stream.getAudioTracks()[0];
        } catch (e) {
            console.warn("Failed to get independent mic stream, recording may fail", e);
            return;
        }

        // Kiểm lại SAU `getUserMedia`: `pause()` có thể đã xen vào trong lúc
        // hộp thoại xin quyền micro còn treo (promise resolve sau khi đã
        // dừng). Không kiểm lại ở đây thì luồng mic vừa mở ra bị bỏ lại sống
        // và ghi lậu suốt quãng tạm dừng dù `_attachToMic()` được gọi TRƯỚC
        // lúc tạm dừng.
        if (!this.state.recordingId || this.state.paused) {
            this._teardownGraph();
            return;
        }
        
        // Setup Web Audio API VAD (Volume Threshold)
        try {
            this.audioContext = new (window.AudioContext || window.webkitAudioContext)();
            const source = this.audioContext.createMediaStreamSource(stream);
            this.analyser = this.audioContext.createAnalyser();
            this.analyser.fftSize = 512;
            source.connect(this.analyser);
            
            const pcmData = new Uint8Array(this.analyser.fftSize);
            this.hasVoiceActivity = false;
            
            this.vadInterval = browser.setInterval(() => {
                if (!this.analyser) return;
                this.analyser.getByteTimeDomainData(pcmData);
                let sumSquares = 0;
                for (let i = 0; i < pcmData.length; i++) {
                    const diff = pcmData[i] - 128;
                    sumSquares += diff * diff;
                }
                const rms = Math.sqrt(sumSquares / pcmData.length);
                // rms > 1.5 corresponds to approx -38dB, safe threshold to ignore pure silence
                if (rms > 1.5) {
                    this.hasVoiceActivity = true;
                }
            }, 100);
        } catch (e) {
            console.warn("Failed to setup AudioContext VAD", e);
            this.hasVoiceActivity = true; // fallback
        }
        
        try {
            this.recorder = new MediaRecorder(stream, { mimeType: 'audio/webm' });
        } catch (e) {
            this.recorder = new MediaRecorder(stream);
        }
        
        this.chunkStartedAt = browser.performance.now();
        
        this.recorder.ondataavailable = (event) => {
            // Need to allow final chunk even if state.recordingId is cleared (but matched to the session)
            if (event.data && event.data.size > 0) {
                const now = browser.performance.now();
                const offsetMs = computeOffsetMs({
                    elapsedAtJoinMs: this.elapsedAtJoinMs,
                    recorderStartedAt: this.recorderStartedAt,
                    now: this.chunkStartedAt,
                });
                const durationMs = Math.round(now - this.chunkStartedAt);
                
                const shouldUpload = this.hasVoiceActivity || !this.analyser;
                
                if (shouldUpload) {
                    this._send({
                        blob: event.data,
                        seq: this.seq++,
                        offsetMs,
                        durationMs,
                        attempts: 0,
                        recordingId: this.state.recordingId,
                        take: this.take
                    }, this.pending, this.activeUploads);
                } else {
                    console.log(`[VAD] Dropped silent chunk ${this.seq} (offset: ${offsetMs}ms)`);
                }
                
                this.chunkStartedAt = now;
                this.hasVoiceActivity = false;
                
                // Retry pending chunks for active session
                if (this.pending.length > 0) {
                    this._flushPending(this.pending, this.activeUploads);
                }
            }
        };

        this.recorder.start(CHUNK_MS);
    }

    async _send(chunk, pendingQueue, activeSet) {
        chunk.attempts++;
        const recordingId = chunk.recordingId;
        if (!recordingId) return; // Should not happen if set during generation
        
        const form = new FormData();
        form.append("recording_id", recordingId);
        form.append("seq", chunk.seq);
        form.append("take", chunk.take);
        form.append("offset_ms", chunk.offsetMs);
        form.append("duration_ms", chunk.durationMs);
        form.append("audio", chunk.blob, `chunk-${chunk.seq}.webm`);
        
        let status = 0;
        const uploadPromise = browser.fetch("/aidt_meeting/chunk", {
            method: "POST",
            body: form,
        }).then(response => {
            if (response.ok) return true;
            status = response.status;
            return false;
        }).catch(() => {
            status = 0;
            return false;
        });

        activeSet.add(uploadPromise);
        const success = await uploadPromise;
        activeSet.delete(uploadPromise);

        if (success) return;
        
        if (!shouldRetry(status, chunk.attempts)) {
            return;
        }
        
        pendingQueue.push(chunk);
        while (pendingQueue.length > MAX_BUFFERED_CHUNKS) {
            pendingQueue.shift();
        }
    }

    _flushPending(pendingQueue, activeSet) {
        const queued = pendingQueue.splice(0, pendingQueue.length);
        for (const chunk of queued) {
            this._send(chunk, pendingQueue, activeSet);
        }
    }

    /**
     * CHỈ ĐỂ THỬ (chế độ nhà phát triển): nạp thẳng một tệp audio có sẵn vào
     * bản ghi đang chạy, như thể máy này vừa thu được nó từ micro.
     *
     * Mẩu giả đi ĐÚNG con đường của mẩu thật — cùng `_send`, cùng
     * `recording_id`/`take`/`seq`, cùng endpoint `/aidt_meeting/chunk` — nên
     * nó thử được trọn chặng phía sau: lưu chunk, export ra
     * `/var/lib/odoo/meetings/<id>/`, giao cho worker, bóc băng, tóm tắt.
     * Thứ DUY NHẤT nó không chạm tới là chặng MediaRecorder/VAD ở phía trước.
     *
     * `seq` lấy từ bộ đếm sống của phiên chứ không phải một số cố định: nạp
     * tệp giữa lúc đang thu thật thì mẩu giả xen vào đúng chỗ, không đụng
     * khoá UNIQUE(recording_id, partner_id, take, seq) và không làm mẩu thật
     * kế tiếp bị bỏ trong im lặng.
     */
    async sendMockAudio(blob) {
        if (!this.state.recordingId) {
            return;
        }
        const now = browser.performance.now();
        await this._send({
            blob,
            seq: this.seq++,
            // `recorderStartedAt` có thể chưa được neo — máy vừa vào họp giữa
            // lúc đang tạm dừng thì chưa có phiên thu nào. Khi đó offset chính
            // là phần đã trôi tính tới lúc vào.
            offsetMs: computeOffsetMs({
                elapsedAtJoinMs: this.elapsedAtJoinMs || 0,
                recorderStartedAt: this.recorderStartedAt ?? now,
                now,
            }),
            durationMs: await readAudioDurationMs(blob),
            attempts: 0,
            recordingId: this.state.recordingId,
            take: this.take,
        }, this.pending, this.activeUploads);
    }

    /**
     * Chụp lại toàn bộ trạng thái của phiên thu đang chạy, NGAY TẠI THỜI
     * ĐIỂM GỌI.
     *
     * Mẩu cuối của một phiên bắn ra SAU khi `MediaRecorder.stop()` được gọi,
     * và trong khoảng trễ đó `resume()` hoặc `start()` của phiên kế tiếp có
     * thể đã đổi hết `this.take`/`this.seq`/ba mốc thời gian/hai hàng đợi.
     * Đọc `this.*` "sống" trong callback thì mẩu cuối của phiên CŨ mang số
     * liệu của phiên MỚI: `seq` quay về 0 (số phiên cũ chắc chắn đã dùng) nên
     * đụng khoá UNIQUE(recording_id, partner_id, take, seq) và mất mẩu trong
     * im lặng; offset tính trên mốc đã reset; mẩu bị đẩy vào hàng đợi không
     * còn ai rút cạn.
     *
     * Bộ đếm sống `this.seq` KHÔNG bị đụng tới ở đây — bản chụp mang bản sao
     * riêng của nó, nên phiên mới không bị ảnh hưởng.
     */
    _captureSession() {
        return {
            recordingId: this.state.recordingId,
            take: this.take,
            seq: this.seq,
            recorder: this.recorder,
            clonedTrack: this.clonedTrack,
            pending: this.pending,
            active: this.activeUploads,
            elapsedAtJoinMs: this.elapsedAtJoinMs,
            recorderStartedAt: this.recorderStartedAt,
            chunkStartedAt: this.chunkStartedAt,
        };
    }

    /**
     * Dừng bộ ghi của một phiên ĐÃ CHỤP và gửi nốt mẩu cuối của nó.
     *
     * Dùng chung cho `stop()` và `pause()`: hai đường đó khác nhau ở phần
     * dọn dẹp phía sau, nhưng phần "chốt an toàn phiên hiện tại" thì giống
     * hệt — và đây đúng là chỗ tập trung nhiều lỗi đua nhất của file, nên
     * giữ nó một bản duy nhất để một lần vá là vá cho cả hai.
     *
     * Mọi số liệu đều lấy từ `session`, không đọc `this.*` nào ngoài `_send`.
     */
    async _drainRecorder(session) {
        const recorder = session.recorder;
        if (!recorder || recorder.state === "inactive") {
            return;
        }
        const stopped = new Promise((resolve) =>
            recorder.addEventListener("stop", resolve, { once: true }));

        recorder.ondataavailable = (event) => {
            if (event.data && event.data.size > 0) {
                const now = browser.performance.now();
                this._send({
                    blob: event.data,
                    seq: session.seq++,
                    offsetMs: computeOffsetMs({
                        elapsedAtJoinMs: session.elapsedAtJoinMs,
                        recorderStartedAt: session.recorderStartedAt,
                        now: session.chunkStartedAt,
                    }),
                    durationMs: Math.round(now - session.chunkStartedAt),
                    attempts: 0,
                    recordingId: session.recordingId,
                    take: session.take,
                }, session.pending, session.active);
            }
        };

        recorder.stop();
        await stopped;
    }

    stop() {
        if (!this.state.recordingId || this.isStopping) {
            return;
        }
        this.isStopping = true;

        const session = this._captureSession();

        // Reset state for new recordings immediately
        this.pending = [];
        this.activeUploads = new Set();
        this.recorder = null;
        this.clonedTrack = null;

        this.state.recordingId = null;
        this.state.channelId = null;
        this.state.paused = false;
        this.isStopping = false;
        // Đặt lại mốc thời gian gốc: cùng một tab dự cuộc họp A (được ghi),
        // A kết thúc, rồi vào cuộc họp B sau đó — B không được thừa hưởng
        // mốc của A. `resume()` chỉ neo mốc mới khi `!this.recorderStartedAt`
        // (máy vào giữa lúc B đang tạm dừng), nên bỏ sót reset ở đây làm mọi
        // mẩu của B mang `offset_ms` cộng dồn luôn cả khoảng cách giữa hai
        // cuộc họp. Rời rồi vào lại CÙNG một bản ghi vẫn đúng: `resume()`/
        // `start()` luôn neo lại bằng `elapsed_ms` server gửi kèm.
        this.recorderStartedAt = null;
        this.elapsedAtJoinMs = 0;
        this.chunkStartedAt = null;

        // Perform async shutdown in background
        (async () => {
            await this._drainRecorder(session);

            while (session.pending.length > 0 || session.active.size > 0) {
                this._flushPending(session.pending, session.active);
                if (session.active.size > 0) {
                    await Promise.all(Array.from(session.active));
                }
                if (session.pending.length > 0) {
                    await new Promise(r => browser.setTimeout(r, 2000));
                }
            }

            session.clonedTrack?.stop();
        })();
    }

    /**
     * Tạm dừng THU BIÊN BẢN. Cuộc gọi không bị đụng tới — track WebRTC
     * (`rtc.state.micAudioTrack`) vẫn chạy, mọi người vẫn nghe và nói bình
     * thường. Chỉ luồng `getUserMedia` RIÊNG của bộ ghi âm bị đóng.
     *
     * KHÔNG đặt lại `recorderStartedAt`: trục thời gian phải đi xuyên qua
     * khoảng dừng để `offset_ms` vẫn là giờ tường kể từ lúc bắt đầu ghi.
     */
    pause() {
        if (!this.state.recordingId) {
            return;
        }
        // Bản chụp phải lấy TRƯỚC khi nhả `this.recorder`: `resume()` có thể
        // đổi take/seq/mốc thời gian, và `stop()` chen vào có thể thay hai
        // hàng đợi bằng cặp mới của phiên rỗng — xem `_captureSession()`.
        const session = this._captureSession();
        this.recorder = null;
        (async () => {
            await this._drainRecorder(session);
            this._flushPending(session.pending, session.active);
        })();
        this._teardownGraph();
    }

    /** Ghi tiếp sau khi tạm dừng. `seq` đếm lại từ 0 trong take mới. */
    async resume(take, elapsedAtJoinMs) {
        if (!this.state.recordingId) {
            return;
        }
        this.take = take;
        this.seq = 0;
        if (elapsedAtJoinMs != null && !this.recorderStartedAt) {
            // Máy vào họp GIỮA lúc đang tạm dừng: chưa có mốc gốc nào.
            this.elapsedAtJoinMs = elapsedAtJoinMs;
            this.recorderStartedAt = browser.performance.now();
        }
        await this.reattach();
    }

    leaveCall() {
        this.stop();
        this.lastOfferedId = null;
    }

    _teardownGraph() {
        if (this.recorder && this.recorder.state !== 'inactive') {
            this.recorder.stop();
        }
        this.clonedTrack?.stop();
        
        if (this.vadInterval) {
            browser.clearInterval(this.vadInterval);
            this.vadInterval = null;
        }
        if (this.audioContext) {
            this.audioContext.close().catch(() => {});
            this.audioContext = null;
            this.analyser = null;
        }
        
        this.recorder = null;
        this.clonedTrack = null;
    }
}

export const meetingRecorderService = {
    dependencies: ["discuss.rtc", "bus_service", "notification", "orm"],
    start(env, services) {
        const recorder = new MeetingRecorder(env, services);
        recorder.syncActiveRecording();
        return recorder;
    },
};

registry.category("services").add("aidt_meeting.recorder", meetingRecorderService);
