import { describe, expect, test, destroy } from "@odoo/hoot";
import { animationFrame } from "@odoo/hoot-dom";
import { advanceTime } from "@odoo/hoot-mock";
import { mockService, mountWithCleanup } from "@web/../tests/web_test_helpers";
import { defineMailModels } from "@mail/../tests/mail_test_helpers";
import { RecordingSubtitle } from "@aidt_meeting_minutes/recording_subtitle";

describe.current.tags("headless");

defineMailModels();

describe("recording subtitle", () => {
    test("không hiển thị subtitle khi mới khởi tạo", async () => {
        mockService("bus_service", {
            subscribe() {},
        });
        await mountWithCleanup(RecordingSubtitle, {
            props: { isActiveCall: true },
        });
        expect(".o-aidt-recording-subtitle").toHaveCount(0);
    });

    test("hiển thị speakerName và text khi nhận sự kiện subtitle_update qua bus_service", async () => {
        let busCallback;
        mockService("bus_service", {
            subscribe(eventName, callback) {
                if (eventName === "aidt_meeting_minutes/subtitle_update") {
                    busCallback = callback;
                }
            },
        });

        await mountWithCleanup(RecordingSubtitle, {
            props: { isActiveCall: true },
        });

        expect(busCallback).not.toBe(undefined);

        busCallback({ text: "Xin chào mọi người", speaker_name: "Nguyen Van A" });
        await animationFrame();

        expect(".o-aidt-recording-subtitle").toHaveCount(1);
        expect(".o-aidt-recording-subtitle strong").toHaveText("Nguyen Van A:");
        expect(".o-aidt-recording-subtitle span").toHaveText("Xin chào mọi người");
    });

    test("không hiển thị subtitle khi isActiveCall là false", async () => {
        let busCallback;
        mockService("bus_service", {
            subscribe(eventName, callback) {
                if (eventName === "aidt_meeting_minutes/subtitle_update") {
                    busCallback = callback;
                }
            },
        });

        await mountWithCleanup(RecordingSubtitle, {
            props: { isActiveCall: false },
        });

        busCallback({ text: "Xin chào", speaker_name: "Nguyen Van A" });
        await animationFrame();

        expect(".o-aidt-recording-subtitle").toHaveCount(0);
    });

    test("tự động ẩn subtitle sau 4 giây", async () => {
        let busCallback;
        mockService("bus_service", {
            subscribe(eventName, callback) {
                if (eventName === "aidt_meeting_minutes/subtitle_update") {
                    busCallback = callback;
                }
            },
        });

        await mountWithCleanup(RecordingSubtitle, {
            props: { isActiveCall: true },
        });

        busCallback({ text: "Xin chào", speaker_name: "Nguyen Van A" });
        await animationFrame();
        expect(".o-aidt-recording-subtitle").toHaveCount(1);

        await advanceTime(4000);
        await animationFrame();
        expect(".o-aidt-recording-subtitle").toHaveCount(0);
    });

    test("reset timeout nếu nhận sự kiện mới trước 4 giây", async () => {
        let busCallback;
        mockService("bus_service", {
            subscribe(eventName, callback) {
                if (eventName === "aidt_meeting_minutes/subtitle_update") {
                    busCallback = callback;
                }
            },
        });

        await mountWithCleanup(RecordingSubtitle, {
            props: { isActiveCall: true },
        });

        busCallback({ text: "Câu thứ nhất", speaker_name: "Nguyen Van A" });
        await animationFrame();
        expect(".o-aidt-recording-subtitle span").toHaveText("Câu thứ nhất");

        await advanceTime(2000);
        busCallback({ text: "Câu thứ hai", speaker_name: "Nguyen Van B" });
        await animationFrame();

        expect(".o-aidt-recording-subtitle strong").toHaveText("Nguyen Van B:");
        expect(".o-aidt-recording-subtitle span").toHaveText("Câu thứ hai");

        await advanceTime(3000);
        await animationFrame();
        expect(".o-aidt-recording-subtitle").toHaveCount(1);

        await advanceTime(1500);
        await animationFrame();
        expect(".o-aidt-recording-subtitle").toHaveCount(0);
    });

    test("dọn dẹp timeout khi destroy component", async () => {
        let busCallback;
        mockService("bus_service", {
            subscribe(eventName, callback) {
                if (eventName === "aidt_meeting_minutes/subtitle_update") {
                    busCallback = callback;
                }
            },
        });

        const target = await mountWithCleanup(RecordingSubtitle, {
            props: { isActiveCall: true },
        });

        busCallback({ text: "Xin chào", speaker_name: "Nguyen Van A" });
        await animationFrame();
        expect(".o-aidt-recording-subtitle").toHaveCount(1);

        destroy(target);
        await advanceTime(4000);
    });
});


