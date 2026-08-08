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
            declined: false,
            declinedRecordingId: null,
        });

        this.seq = 0;
        this.pending = [];
        this.clonedTrack = null;
        this.recorder = null;
        this.lastOfferedId = null;

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
        if (!info?.recording_id || this.currentChannelId !== channelId) {
            return;
        }
        await this.start(info.recording_id, info.elapsed_ms || 0, channelId);
    }

    _onRecordingState(payload) {
        if (payload.action === "started") {
            const channelId = this.currentChannelId;
            if (!channelId || payload.channel_id !== channelId) {
                return;
            }
            this.lastOfferedId = payload.recording_id;
            this.start(payload.recording_id, payload.elapsed_ms || 0, channelId);
        } else {
            if (this.state.declinedRecordingId === payload.recording_id) {
                this.state.declinedRecordingId = null;
                this.state.declined = false;
            }
            if (this.state.recordingId === payload.recording_id) {
                this.stop();
            }
        }
    }

    async start(recordingId, elapsedAtJoinMs, channelId = null) {
        if (this.state.recordingId || this.state.declinedRecordingId === recordingId) {
            return;
        }
        this.state.declinedRecordingId = null;
        this.state.declined = false;
        this.state.recordingId = recordingId;
        this.state.channelId = channelId ?? this.currentChannelId;
        this.lastOfferedId = recordingId;
        this.elapsedAtJoinMs = elapsedAtJoinMs;
        this.recorderStartedAt = browser.performance.now();
        this.seq = 0;
        await this.reattach();
    }

    async reattach() {
        return this._attachToMic();
    }

    async _attachToMic() {
        this._teardownGraph();
        const micTrack = this.rtc.state?.micAudioTrack;
        if (!micTrack || !this.state.recordingId) {
            return;
        }
        this.clonedTrack = micTrack.clone();
        
        if (!this.state.recordingId) {
            this._teardownGraph();
            return;
        }
        
        const stream = new MediaStream([this.clonedTrack]);
        
        try {
            this.recorder = new MediaRecorder(stream, { mimeType: 'audio/webm' });
        } catch (e) {
            this.recorder = new MediaRecorder(stream);
        }
        
        this.chunkStartedAt = browser.performance.now();
        
        this.recorder.ondataavailable = (event) => {
            if (event.data && event.data.size > 0 && this.state.recordingId) {
                const now = browser.performance.now();
                const offsetMs = computeOffsetMs({
                    elapsedAtJoinMs: this.elapsedAtJoinMs,
                    recorderStartedAt: this.recorderStartedAt,
                    now: this.chunkStartedAt,
                });
                const durationMs = Math.round(now - this.chunkStartedAt);
                
                this._send({
                    blob: event.data,
                    seq: this.seq++,
                    offsetMs,
                    durationMs,
                    attempts: 0
                });
                
                this.chunkStartedAt = now;
                
                // Retry pending chunks
                if (this.pending.length > 0) {
                    this._flushPending();
                }
            }
        };

        this.recorder.start(CHUNK_MS);
    }

    async _send(chunk) {
        chunk.attempts++;
        chunk.recordingId = chunk.recordingId ?? this.state.recordingId;
        const form = new FormData();
        form.append("recording_id", chunk.recordingId);
        form.append("seq", chunk.seq);
        form.append("offset_ms", chunk.offsetMs);
        form.append("duration_ms", chunk.durationMs);
        form.append("audio", chunk.blob, `chunk-${chunk.seq}.webm`);
        
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
        
        if (this.recorder && this.recorder.state !== 'inactive') {
            this.recorder.stop();
        }
        
        this._flushPending();
        
        // Finalize recording (as mandated by task brief)
        const recordingId = this.state.recordingId;
        this.orm.call("aidt.meeting.recording", "action_stop", [[recordingId]]).catch(() => {});
        
        this._teardownGraph();
        this.state.recordingId = null;
        this.state.channelId = null;
    }

    decline() {
        this.state.declinedRecordingId = this.state.recordingId ?? this.lastOfferedId;
        this.state.declined = true;
        this.stop();
    }

    leaveCall() {
        this.stop();
        this.state.declinedRecordingId = null;
        this.state.declined = false;
        this.lastOfferedId = null;
    }

    _teardownGraph() {
        if (this.recorder && this.recorder.state !== 'inactive') {
            this.recorder.stop();
        }
        this.clonedTrack?.stop();
        
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
