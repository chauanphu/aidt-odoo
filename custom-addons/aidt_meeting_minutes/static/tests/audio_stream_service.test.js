import { describe, expect, test, afterEach } from "@odoo/hoot";
import { EventBus } from "@odoo/owl";
import { browser } from "@web/core/browser/browser";
import { AudioStreamService } from "@aidt_meeting_minutes/audio_stream_service";

describe.current.tags("headless");

class MockWebSocket {
    static OPEN = 1;
    static CLOSED = 3;
    constructor(url) {
        this.url = url;
        this.readyState = MockWebSocket.OPEN;
        this.sentData = [];
        this.onmessage = null;
        this.onclose = null;
        this.onerror = null;
        MockWebSocket.instances.push(this);
    }
    send(data) {
        this.sentData.push(data);
    }
    close() {
        this.readyState = MockWebSocket.CLOSED;
        if (this.onclose) this.onclose();
    }
}
MockWebSocket.instances = [];

class MockScriptProcessor {
    constructor(bufferSize, inputChannels, outputChannels) {
        this.bufferSize = bufferSize;
        this.inputChannels = inputChannels;
        this.outputChannels = outputChannels;
        this.onaudioprocess = null;
        this.connectedTo = null;
    }
    connect(destination) {
        this.connectedTo = destination;
    }
    disconnect() {
        this.connectedTo = null;
    }
}

class MockAudioContext {
    constructor(options) {
        if (MockAudioContext.shouldThrow) {
            throw new Error("AudioContext not supported");
        }
        this.sampleRate = options?.sampleRate || 16000;
        this.state = "running";
        this.destination = {};
        MockAudioContext.lastInstance = this;
    }
    createMediaStreamSource(stream) {
        this.sourceStream = stream;
        return {
            connect: (processor) => {
                this.processor = processor;
            },
            disconnect: () => {},
        };
    }
    createScriptProcessor(bufferSize, inputChannels, outputChannels) {
        this.processor = new MockScriptProcessor(bufferSize, inputChannels, outputChannels);
        return this.processor;
    }
    async close() {
        this.state = "closed";
    }
}
MockAudioContext.shouldThrow = false;
MockAudioContext.lastInstance = null;

class MockMediaStream {
    constructor(tracks) {
        this.tracks = tracks;
    }
}

function makeTrack(applyConstraintsFn) {
    const track = {
        stopped: false,
        appliedConstraints: null,
        clone() {
            return makeTrack(applyConstraintsFn);
        },
        stop() {
            this.stopped = true;
        },
        applyConstraints(constraints) {
            this.appliedConstraints = constraints;
            if (applyConstraintsFn) {
                return applyConstraintsFn(constraints);
            }
            return Promise.resolve();
        },
    };
    return track;
}

describe("AudioStreamService", () => {
    afterEach(() => {
        MockWebSocket.instances = [];
        MockAudioContext.lastInstance = null;
        MockAudioContext.shouldThrow = false;
    });

    test("starts WebSocket stream and processes PCM audio on discuss.call.joined, stops on discuss.call.left", async () => {
        const origWebSocket = browser.WebSocket;
        const origAudioContext = browser.AudioContext;
        const origMediaStream = window.MediaStream;

        browser.WebSocket = MockWebSocket;
        browser.AudioContext = MockAudioContext;
        window.WebSocket = MockWebSocket;
        window.AudioContext = MockAudioContext;
        window.MediaStream = MockMediaStream;

        try {
            const bus = new EventBus();
            const micTrack = makeTrack();
            const rtc = {
                state: {
                    micAudioTrack: micTrack,
                    channel: { id: 42 },
                    selfSession: { partnerId: 10, partnerName: "Alice" },
                },
            };

            let receivedSubtitle = null;
            bus.addEventListener("aidt_meeting_minutes/subtitle_update", (ev) => {
                receivedSubtitle = ev.detail;
            });

            const env = { bus };
            const service = new AudioStreamService(env, { "discuss.rtc": rtc });

            expect(service.isActive).toBe(false);

            // Trigger discuss.call.joined via bus event
            bus.trigger("discuss.call.joined");
            await Promise.resolve(); // allow async start() microtask to complete
            expect(service.isActive).toBe(true);

            // Verify WebSocket connection
            expect(MockWebSocket.instances.length).toBe(1);
            const ws = MockWebSocket.instances[0];
            expect(ws.url).toContain("ws://");
            expect(ws.url).toContain(":8002/ws/stream/sess_42?channel_id=42&speaker_id=10");

            // Verify noise suppression constraints were applied to cloned track
            const clonedTrack = service.clonedTrack;
            expect(clonedTrack).not.toBe(null);
            expect(clonedTrack.stopped).toBe(false);
            expect(clonedTrack.appliedConstraints).toEqual({
                noiseSuppression: true,
                autoGainControl: true,
                echoCancellation: true,
            });

            // Simulate incoming subtitle message over WebSocket
            ws.onmessage({
                data: JSON.stringify({
                    type: "subtitle",
                    text: "Xin chào các bạn",
                }),
            });
            expect(receivedSubtitle).not.toBe(null);
            expect(receivedSubtitle.text).toBe("Xin chào các bạn");
            expect(receivedSubtitle.speaker_name).toBe("Alice");

            // Simulate audio process event (Float32 to Int16 PCM conversion)
            const float32Data = new Float32Array([0.5, -0.5, 0.0, 1.0, -1.0]);
            const fakeBuffer = {
                getChannelData: () => float32Data,
            };
            service.processor.onaudioprocess({ inputBuffer: fakeBuffer });

            expect(ws.sentData.length).toBe(1);
            const sentBuffer = ws.sentData[0];
            const sentInt16 = new Int16Array(sentBuffer);
            expect(sentInt16[0]).toBe(16384); // 0.5 * 32768
            expect(sentInt16[1]).toBe(-16384); // -0.5 * 32768
            expect(sentInt16[2]).toBe(0);
            expect(sentInt16[3]).toBe(32767); // Math.min(32767, 32768)
            expect(sentInt16[4]).toBe(-32768); // Math.max(-32768, -32768)

            // Trigger discuss.call.left via bus event
            bus.trigger("discuss.call.left");
            expect(service.isActive).toBe(false);
            expect(ws.readyState).toBe(MockWebSocket.CLOSED);
            expect(clonedTrack.stopped).toBe(true);
            expect(service.clonedTrack).toBe(null);
            expect(service.ws).toBe(null);
        } finally {
            browser.WebSocket = origWebSocket;
            browser.AudioContext = origAudioContext;
            window.WebSocket = origWebSocket;
            window.AudioContext = origAudioContext;
            window.MediaStream = origMediaStream;
        }
    });

    test("does not start stream if micAudioTrack is missing", async () => {
        const bus = new EventBus();
        const rtc = { state: {} };
        const env = { bus };
        const service = new AudioStreamService(env, { "discuss.rtc": rtc });

        bus.trigger("discuss.call.joined");
        await Promise.resolve();
        expect(service.isActive).toBe(false);
    });

    test("aborts start cleanly if call is left while applyConstraints is pending", async () => {
        const origWebSocket = browser.WebSocket;
        const origAudioContext = browser.AudioContext;
        const origMediaStream = window.MediaStream;

        browser.WebSocket = MockWebSocket;
        browser.AudioContext = MockAudioContext;
        window.WebSocket = MockWebSocket;
        window.AudioContext = MockAudioContext;
        window.MediaStream = MockMediaStream;

        try {
            let resolveConstraints;
            const constraintsPromise = new Promise((resolve) => {
                resolveConstraints = resolve;
            });

            const bus = new EventBus();
            const micTrack = makeTrack(() => constraintsPromise);
            const rtc = {
                state: {
                    micAudioTrack: micTrack,
                    channel: { id: 42 },
                },
            };

            const env = { bus };
            const service = new AudioStreamService(env, { "discuss.rtc": rtc });

            // Trigger call joined (start begins and awaits applyConstraints)
            bus.trigger("discuss.call.joined");
            expect(service.isActive).toBe(true);

            // User leaves call while applyConstraints is pending
            bus.trigger("discuss.call.left");
            expect(service.isActive).toBe(false);

            // Resolve constraints after call was left
            resolveConstraints();
            await Promise.resolve();
            await Promise.resolve();

            // Verify no WebSocket was created and service remains inactive
            expect(service.isActive).toBe(false);
            expect(MockWebSocket.instances.length).toBe(0);
            expect(service.ws).toBe(null);
        } finally {
            browser.WebSocket = origWebSocket;
            browser.AudioContext = origAudioContext;
            window.WebSocket = origWebSocket;
            window.AudioContext = origAudioContext;
            window.MediaStream = origMediaStream;
        }
    });

    test("resets isActive and cleans clonedTrack if AudioContext throws", async () => {
        const origWebSocket = browser.WebSocket;
        const origAudioContext = browser.AudioContext;
        const origMediaStream = window.MediaStream;

        browser.WebSocket = MockWebSocket;
        browser.AudioContext = MockAudioContext;
        window.WebSocket = MockWebSocket;
        window.AudioContext = MockAudioContext;
        window.MediaStream = MockMediaStream;
        MockAudioContext.shouldThrow = true;

        try {
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

            bus.trigger("discuss.call.joined");
            await Promise.resolve();
            expect(service.isActive).toBe(false);
            expect(service.clonedTrack).toBe(null);
        } finally {
            MockAudioContext.shouldThrow = false;
            browser.WebSocket = origWebSocket;
            browser.AudioContext = origAudioContext;
            window.WebSocket = origWebSocket;
            window.AudioContext = origAudioContext;
            window.MediaStream = origMediaStream;
        }
    });
});
