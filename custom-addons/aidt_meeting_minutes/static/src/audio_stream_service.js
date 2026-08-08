/** @odoo-module **/
import { registry } from "@web/core/registry";
import { browser } from "@web/core/browser/browser";

export class AudioStreamService {
    constructor(env, services) {
        this.env = env;
        this.rtc = services["discuss.rtc"];
        this.ws = null;
        this.audioContext = null;
        this.processor = null;
        this.source = null;
        this.clonedTrack = null;
        this.isActive = false;

        this.env.bus.addEventListener("discuss.call.joined", () => this.start());
        this.env.bus.addEventListener("discuss.call.left", () => this.stop());
    }

    async start() {
        if (this.isActive) return;
        const micTrack = this.rtc.state?.micAudioTrack;
        if (!micTrack) return;

        this.isActive = true;
        const clonedTrack = micTrack.clone();
        this.clonedTrack = clonedTrack;

        // Apply WebRTC Noise Suppression & Auto Gain Control constraints
        if (clonedTrack.applyConstraints) {
            try {
                await clonedTrack.applyConstraints({
                    noiseSuppression: true,
                    autoGainControl: true,
                    echoCancellation: true,
                });
            } catch (e) {
                console.warn("Failed to apply noise suppression constraints", e);
            }
        }

        if (!this.isActive) {
            this.stop();
            return;
        }

        const channelId = this.rtc.state?.channel?.id || 0;
        const speakerId = this.rtc.state?.selfSession?.partnerId || this.env.services?.["mail.store"]?.user?.id || 0;
        const speakerName = this.rtc.state?.selfSession?.partnerName || this.env.services?.["mail.store"]?.user?.name || "Me";

        const protocol = browser.location.protocol === "https:" ? "wss:" : "ws:";
        const hostname = browser.location.hostname || "localhost";
        const asrHost = `${hostname}:8002`;
        const wsUrl = `${protocol}//${asrHost}/ws/stream/sess_${channelId}?channel_id=${channelId}&speaker_id=${speakerId}`;

        try {
            const WebSocketClass = (typeof window !== "undefined" && window.WebSocket) || browser.WebSocket;
            this.ws = new WebSocketClass(wsUrl);

            this.ws.onmessage = (event) => {
                try {
                    const data = JSON.parse(event.data);
                    if (data.type === "subtitle" && data.text) {
                        this.env.bus.trigger("aidt_meeting_minutes/subtitle_update", {
                            text: data.text,
                            speaker_name: speakerName,
                        });
                    }
                } catch (err) {
                    console.error("Error parsing WebSocket subtitle message", err);
                }
            };

            const AudioContextClass = (typeof window !== "undefined" && window.AudioContext) || (typeof window !== "undefined" && window.webkitAudioContext) || browser.AudioContext;
            this.audioContext = new AudioContextClass({ sampleRate: 16000 });
            const stream = new MediaStream([clonedTrack]);
            this.source = this.audioContext.createMediaStreamSource(stream);
            this.processor = this.audioContext.createScriptProcessor(4096, 1, 1);

            this.processor.onaudioprocess = (e) => {
                if (this.ws && this.ws.readyState === (WebSocketClass.OPEN || 1)) {
                    const float32Array = e.inputBuffer.getChannelData(0);
                    const int16Array = new Int16Array(float32Array.length);
                    for (let i = 0; i < float32Array.length; i++) {
                        int16Array[i] = Math.max(-32768, Math.min(32767, float32Array[i] * 32768));
                    }
                    this.ws.send(int16Array.buffer);
                }
            };

            this.source.connect(this.processor);
            this.processor.connect(this.audioContext.destination);
        } catch (e) {
            this.stop();
        }
    }

    stop() {
        this.isActive = false;
        if (this.ws) {
            try {
                this.ws.close();
            } catch (e) {
                console.warn("Failed to close WebSocket", e);
            }
            this.ws = null;
        }
        if (this.processor) {
            try {
                this.processor.disconnect();
            } catch (e) {}
            this.processor.onaudioprocess = null;
            this.processor = null;
        }
        if (this.source) {
            try {
                this.source.disconnect();
            } catch (e) {}
            this.source = null;
        }
        if (this.audioContext) {
            try {
                if (this.audioContext.state !== "closed" && this.audioContext.close) {
                    this.audioContext.close();
                }
            } catch (e) {}
            this.audioContext = null;
        }
        if (this.clonedTrack) {
            try {
                this.clonedTrack.stop();
            } catch (e) {}
            this.clonedTrack = null;
        }
    }
}

export const audioStreamService = {
    dependencies: ["discuss.rtc"],
    start(env, services) {
        return new AudioStreamService(env, services);
    },
};

registry.category("services").add("aidt_meeting.audio_stream", audioStreamService);
