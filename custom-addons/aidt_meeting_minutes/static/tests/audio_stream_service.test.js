import { describe, expect, test } from "@odoo/hoot";
import { patchWithCleanup } from "@web/../tests/web_test_helpers";
import { EventBus } from "@odoo/owl";
import { browser } from "@web/core/browser/browser";
import { AudioStreamService } from "@aidt_meeting_minutes/audio_stream_service";

describe.current.tags("headless");

class MockMediaRecorder {
    constructor(stream, options) {
        this.stream = stream;
        this.options = options;
        this.state = "inactive";
        this.ondataavailable = null;
        MockMediaRecorder.lastInstance = this;
    }
    start(interval) {
        this.state = "recording";
        this.interval = interval;
    }
    stop() {
        this.state = "inactive";
    }
}

class MockMediaStream {
    constructor(tracks) {
        this.tracks = tracks;
    }
}

function makeTrack() {
    return {
        clone() {
            return makeTrack();
        },
        stop() {},
    };
}

describe("AudioStreamService", () => {
    test("starts recorder on discuss.call.joined and stops on discuss.call.left", async () => {
        const origMediaRecorder = window.MediaRecorder;
        const origMediaStream = window.MediaStream;
        window.MediaRecorder = MockMediaRecorder;
        window.MediaStream = MockMediaStream;

        const fetched = [];
        patchWithCleanup(browser, {
            fetch: async (url, opts) => {
                fetched.push({ url, opts });
                return { ok: true };
            },
        });

        const bus = new EventBus();
        const micTrack = makeTrack();
        const rtc = {
            state: {
                micAudioTrack: micTrack,
                channel: { id: 42 },
            },
        };

        const env = { bus };
        const service = new AudioStreamService(env, { "discuss.rtc": rtc });

        expect(service.isActive).toBe(false);

        // Trigger discuss.call.joined
        bus.trigger("discuss.call.joined");
        expect(service.isActive).toBe(true);
        expect(MockMediaRecorder.lastInstance).not.toBe(undefined);
        expect(MockMediaRecorder.lastInstance.state).toBe("recording");
        expect(MockMediaRecorder.lastInstance.interval).toBe(1500);

        // Simulate ondataavailable
        const fakeBlob = new Blob(["fake audio data"], { type: "audio/webm" });
        await MockMediaRecorder.lastInstance.ondataavailable({ data: fakeBlob });

        expect(fetched.length).toBe(1);
        expect(fetched[0].url).toBe("/discuss/channel/42/stream_audio");
        expect(fetched[0].opts.method).toBe("POST");

        // Trigger discuss.call.left
        bus.trigger("discuss.call.left");
        expect(service.isActive).toBe(false);
        expect(MockMediaRecorder.lastInstance.state).toBe("inactive");

        window.MediaRecorder = origMediaRecorder;
        window.MediaStream = origMediaStream;
    });

    test("does not start recorder if micAudioTrack is missing", () => {
        const bus = new EventBus();
        const rtc = { state: {} };
        const env = { bus };
        const service = new AudioStreamService(env, { "discuss.rtc": rtc });

        bus.trigger("discuss.call.joined");
        expect(service.isActive).toBe(false);
    });
});
