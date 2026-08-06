/** @odoo-module **/
import { Component, onWillStart, onWillDestroy, useState } from "@odoo/owl";

export class RecordingSubtitle extends Component {
    static template = "aidt_meeting_minutes.RecordingSubtitle";
    static props = {
        isActiveCall: { type: Boolean, optional: true },
    };

    setup() {
        this.state = useState({
            text: "",
            isVisible: false,
        });

        this.recognition = null;
        this.timeoutId = null;

        onWillStart(() => {
            const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
            if (SpeechRecognition && this.props.isActiveCall) {
                this.recognition = new SpeechRecognition();
                this.recognition.continuous = true;
                this.recognition.interimResults = true;
                this.recognition.lang = "vi-VN"; // Default to Vietnamese

                this.recognition.onresult = (event) => {
                    let interimTranscript = '';
                    for (let i = event.resultIndex; i < event.results.length; i++) {
                        if (event.results[i].isFinal) {
                            interimTranscript += event.results[i][0].transcript;
                        } else {
                            interimTranscript += event.results[i][0].transcript;
                        }
                    }
                    this.state.text = interimTranscript;
                    this.state.isVisible = true;

                    // Auto-hide after 4 seconds of silence
                    if (this.timeoutId) clearTimeout(this.timeoutId);
                    this.timeoutId = setTimeout(() => {
                        this.state.isVisible = false;
                    }, 4000);
                };

                try {
                    this.recognition.start();
                } catch (e) {
                    console.error("Speech recognition failed to start", e);
                }
            }
        });

        onWillDestroy(() => {
            if (this.recognition) {
                this.recognition.stop();
            }
            if (this.timeoutId) {
                clearTimeout(this.timeoutId);
            }
        });
    }
}
