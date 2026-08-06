/** @odoo-module **/
import { registry } from "@web/core/registry";
import { browser } from "@web/core/browser/browser";

export class AudioStreamService {
    constructor(env, services) {
        this.env = env;
        this.rtc = services["discuss.rtc"];
        this.recorder = null;
        this.clonedTrack = null;
        this.isActive = false;
        
        this.env.bus.addEventListener("discuss.call.joined", () => this.start());
        this.env.bus.addEventListener("discuss.call.left", () => this.stop());
    }

    start() {
        if (this.isActive) return;
        const micTrack = this.rtc.state?.micAudioTrack;
        if (!micTrack) return;

        this.isActive = true;
        const clonedTrack = micTrack.clone();
        this.clonedTrack = clonedTrack;
        const stream = new MediaStream([clonedTrack]);
        try {
            this.recorder = new MediaRecorder(stream, { mimeType: "audio/webm;codecs=opus" });
        } catch (e) {
            console.warn("MediaRecorder not supported", e);
            this.isActive = false;
            if (this.clonedTrack) {
                this.clonedTrack.stop();
                this.clonedTrack = null;
            }
            return;
        }

        this.recorder.ondataavailable = async (e) => {
            if (e.data.size > 0 && this.rtc.state?.channel?.id) {
                const channelId = this.rtc.state.channel.id;
                const form = new FormData();
                form.append("audio", e.data, "chunk.webm");
                
                try {
                    await browser.fetch(`/discuss/channel/${channelId}/stream_audio`, {
                        method: "POST",
                        body: form,
                    });
                } catch (err) {
                    console.error("Failed to upload subtitle chunk", err);
                }
            }
        };

        this.recorder.start(1500); // 1.5 second chunks
    }

    stop() {
        this.isActive = false;
        if (this.recorder && this.recorder.state !== "inactive") {
            this.recorder.stop();
        }
        this.recorder = null;
        if (this.clonedTrack) {
            this.clonedTrack.stop();
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
