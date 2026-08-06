import { describe, expect, test, destroy } from "@odoo/hoot";
import { animationFrame } from "@odoo/hoot-dom";
import { mountWithCleanup } from "@web/../tests/web_test_helpers";
import { defineMailModels } from "@mail/../tests/mail_test_helpers";
import { RecordingSubtitle } from "@aidt_meeting_minutes/recording_subtitle";

describe.current.tags("headless");

defineMailModels();

class MockSpeechRecognition {
    constructor() {
        this.continuous = false;
        this.interimResults = false;
        this.lang = "";
        this.started = false;
        this.stopped = false;
        this.onresult = null;
        this.onend = null;
        this.onerror = null;
        MockSpeechRecognition.instance = this;
    }
    start() {
        this.started = true;
    }
    stop() {
        this.stopped = true;
    }
}

describe("recording subtitle", () => {
    test("không hiển thị subtitle khi text rỗng", async () => {
        const originalSpeech = window.SpeechRecognition;
        window.SpeechRecognition = MockSpeechRecognition;
        try {
            await mountWithCleanup(RecordingSubtitle, {
                props: { isActiveCall: true },
            });
            expect(".o-aidt-recording-subtitle").toHaveCount(0);
        } finally {
            window.SpeechRecognition = originalSpeech;
        }
    });

    test("khởi tạo SpeechRecognition và hiển thị text khi onresult được gọi", async () => {
        const originalSpeech = window.SpeechRecognition;
        window.SpeechRecognition = MockSpeechRecognition;
        try {
            await mountWithCleanup(RecordingSubtitle, {
                props: { isActiveCall: true },
            });
            expect(MockSpeechRecognition.instance).not.toBe(undefined);
            expect(MockSpeechRecognition.instance.started).toBe(true);

            // Giả lập sự kiện onresult
            const fakeEvent = {
                resultIndex: 0,
                results: [
                    [{ transcript: "Xin chào mọi người" }]
                ]
            };
            fakeEvent.results[0].isFinal = true;

            MockSpeechRecognition.instance.onresult(fakeEvent);
            await animationFrame();

            expect(".o-aidt-recording-subtitle").toHaveCount(1);
            expect(".o-aidt-recording-subtitle").toHaveText("Xin chào mọi người");
        } finally {
            window.SpeechRecognition = originalSpeech;
        }
    });

    test("dừng SpeechRecognition khi destroy component", async () => {
        const originalSpeech = window.SpeechRecognition;
        window.SpeechRecognition = MockSpeechRecognition;
        try {
            const target = await mountWithCleanup(RecordingSubtitle, {
                props: { isActiveCall: true },
            });
            expect(MockSpeechRecognition.instance.stopped).toBe(false);
            destroy(target);
            expect(MockSpeechRecognition.instance.stopped).toBe(true);
        } finally {
            window.SpeechRecognition = originalSpeech;
        }
    });

    test("không khởi tạo SpeechRecognition khi isActiveCall là false", async () => {
        const originalSpeech = window.SpeechRecognition;
        MockSpeechRecognition.instance = null;
        window.SpeechRecognition = MockSpeechRecognition;
        try {
            await mountWithCleanup(RecordingSubtitle, {
                props: { isActiveCall: false },
            });
            expect(MockSpeechRecognition.instance).toBe(null);
        } finally {
            window.SpeechRecognition = originalSpeech;
        }
    });

    test("tự động restart SpeechRecognition khi onend kích hoạt", async () => {
        const originalSpeech = window.SpeechRecognition;
        window.SpeechRecognition = MockSpeechRecognition;
        try {
            await mountWithCleanup(RecordingSubtitle, {
                props: { isActiveCall: true },
            });
            expect(MockSpeechRecognition.instance.started).toBe(true);
            MockSpeechRecognition.instance.started = false;

            // Trigger onend event handler
            MockSpeechRecognition.instance.onend();
            expect(MockSpeechRecognition.instance.started).toBe(true);
        } finally {
            window.SpeechRecognition = originalSpeech;
        }
    });

    test("không restart SpeechRecognition khi onend kích hoạt sau khi destroy", async () => {
        const originalSpeech = window.SpeechRecognition;
        window.SpeechRecognition = MockSpeechRecognition;
        try {
            const target = await mountWithCleanup(RecordingSubtitle, {
                props: { isActiveCall: true },
            });
            const instance = MockSpeechRecognition.instance;
            destroy(target);

            instance.started = false;
            instance.onend();
            expect(instance.started).toBe(false);
        } finally {
            window.SpeechRecognition = originalSpeech;
        }
    });
});

