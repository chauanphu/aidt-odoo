import { registry } from "@web/core/registry";
import { browser } from "@web/core/browser/browser";
import { reactive } from "@odoo/owl";

export const CHUNK_MS = 30000;
const MAX_BUFFERED_CHUNKS = 8;
export const MAX_ATTEMPTS = 2;

export function computeOffsetMs({ elapsedAtJoinMs, recorderStartedAt, now }) {
    return Math.max(0, Math.round(elapsedAtJoinMs + (now - recorderStartedAt)));
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
        // Chủ phòng của CUỘC GỌI (không phải của một bản ghi) — server LUÔN
        // trả khoá này, kể cả khi chưa có bản ghi nào, để nút "Bật ghi âm"
        // chỉ hiện cho đúng người được phép bấm (RecordingBanner.canStart).
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

    stop() {
        if (!this.state.recordingId || this.isStopping) {
            return;
        }
        this.isStopping = true;
        
        const recordingId = this.state.recordingId;
        const take = this.take;
        // Chụp `seq` NGAY TẠI ĐÂY — cùng lý do với `take`: mẩu cuối có thể
        // bắn ra SAU khi một `start()` phiên mới đã đặt lại `this.seq = 0`
        // (bus "started" có thể kích `start()` ngay khi `state.recordingId`
        // vừa được xoá đồng bộ ở dưới). Đọc `this.seq` sống thì mẩu cuối của
        // phiên CŨ mang `seq = 0` — số chắc chắn phiên cũ đã dùng — đụng khoá
        // UNIQUE(recording_id, partner_id, take, seq) và mất mẩu trong im
        // lặng. Bộ đếm sống (`this.seq`) không được đụng tới ở đây để không
        // ảnh hưởng tới phiên mới.
        let seq = this.seq;
        const sessionPending = this.pending;
        const sessionActive = this.activeUploads;
        const sessionRecorder = this.recorder;
        const sessionClonedTrack = this.clonedTrack;
        // Chụp nốt ba mốc thời gian NGAY TẠI ĐÂY — cùng lý do với take/seq ở
        // trên: mẩu cuối bắn ra SAU khi ba trường `this.*` dưới đây đã bị đặt
        // lại (để phiên họp SAU không thừa hưởng mốc của phiên này). Đọc
        // "sống" trong callback thì offset của mẩu cuối tính trên giá trị đã
        // reset (null/0) thay vì mốc thật của phiên đang dừng.
        const elapsedAtJoinMs = this.elapsedAtJoinMs;
        const recorderStartedAt = this.recorderStartedAt;
        const chunkStartedAt = this.chunkStartedAt;

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
            if (sessionRecorder && sessionRecorder.state !== 'inactive') {
                const stopPromise = new Promise(resolve => {
                    sessionRecorder.addEventListener('stop', resolve, { once: true });
                });

                // We must inject recordingId into final chunk's ondataavailable
                sessionRecorder.ondataavailable = (event) => {
                    // Override state.recordingId lookup for final chunk
                    if (event.data && event.data.size > 0) {
                        const now = browser.performance.now();
                        const offsetMs = computeOffsetMs({
                            elapsedAtJoinMs,
                            recorderStartedAt,
                            now: chunkStartedAt,
                        });
                        const durationMs = Math.round(now - chunkStartedAt);

                        this._send({
                            blob: event.data,
                            seq: seq++,
                            offsetMs,
                            durationMs,
                            attempts: 0,
                            recordingId: recordingId,
                            take: take
                        }, sessionPending, sessionActive);
                    }
                };

                sessionRecorder.stop();
                await stopPromise;
            }
            
            while (sessionPending.length > 0 || sessionActive.size > 0) {
                this._flushPending(sessionPending, sessionActive);
                if (sessionActive.size > 0) {
                    await Promise.all(Array.from(sessionActive));
                }
                if (sessionPending.length > 0) {
                    await new Promise(r => browser.setTimeout(r, 2000));
                }
            }

            sessionClonedTrack?.stop();
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
        const recordingId = this.state.recordingId;
        // Chụp take/seq NGAY TẠI ĐÂY — không đọc `this.take`/`this.seq` trong
        // callback `ondataavailable` bên dưới, vì `resume()` có thể đã đổi cả
        // hai TRƯỚC KHI sự kiện `dataavailable` của mẩu cuối này thực sự bắn
        // (độ trễ của MediaRecorder). Đọc "sống" thì mẩu cuối của take CŨ bị
        // gắn nhầm sang take MỚI, đụng khoá UNIQUE(recording_id, partner_id,
        // take, seq) với mẩu seq=0 thật của take mới.
        const take = this.take;
        let seq = this.seq;
        const sessionRecorder = this.recorder;
        // Chụp hai hàng đợi SỐNG ngay tại đây, đối xứng với take/seq ở trên:
        // nếu `stop()` chen vào giữa (chủ phòng bấm Kết thúc ngay sau Tạm
        // dừng), `stop()` đã thay `this.pending`/`this.activeUploads` bằng
        // cặp MỚI của phiên rỗng và chỉ rút cạn cặp đó — đọc `this.pending`
        // "sống" trong closure bên dưới thì mẩu cuối của `pause()` bị đẩy
        // vào một hàng đợi không còn ai rút cạn.
        const sessionPending = this.pending;
        const sessionActive = this.activeUploads;
        // Chụp nốt ba mốc thời gian NGAY TẠI ĐÂY — cùng lý do với take/seq:
        // mẩu cuối có thể bắn ra SAU khi `resume()` đã đổi (hoặc `stop()` đã
        // đặt lại, xem I2) các trường `this.*` tương ứng.
        const elapsedAtJoinMs = this.elapsedAtJoinMs;
        const recorderStartedAt = this.recorderStartedAt;
        const chunkStartedAt = this.chunkStartedAt;
        this.recorder = null;
        (async () => {
            if (sessionRecorder && sessionRecorder.state !== "inactive") {
                const stopped = new Promise((resolve) =>
                    sessionRecorder.addEventListener("stop", resolve, { once: true }));

                sessionRecorder.ondataavailable = (event) => {
                    if (event.data && event.data.size > 0) {
                        const now = browser.performance.now();
                        const offsetMs = computeOffsetMs({
                            elapsedAtJoinMs,
                            recorderStartedAt,
                            now: chunkStartedAt,
                        });
                        const durationMs = Math.round(now - chunkStartedAt);

                        this._send({
                            blob: event.data,
                            seq: seq++,
                            offsetMs,
                            durationMs,
                            attempts: 0,
                            recordingId,
                            take,
                        }, sessionPending, sessionActive);
                    }
                };

                sessionRecorder.stop();
                await stopped;
            }
            this._flushPending(sessionPending, sessionActive);
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
