/** @odoo-module **/
import { Component, onWillStart, onWillDestroy, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

export class RecordingSubtitle extends Component {
    static template = "aidt_meeting_minutes.RecordingSubtitle";
    static props = {
        isActiveCall: { type: Boolean, optional: true },
    };

    setup() {
        this.busService = useService("bus_service");
        this.state = useState({
            text: "",
            speakerName: "",
            isVisible: false,
        });

        this.timeoutId = null;
        this.onSubtitleUpdate = this.onSubtitleUpdate.bind(this);

        onWillStart(() => {
            this.busService.subscribe("aidt_meeting_minutes/subtitle_update", this.onSubtitleUpdate);
        });

        onWillDestroy(() => {
            if (this.timeoutId) clearTimeout(this.timeoutId);
        });
    }

    onSubtitleUpdate(payload) {
        if (!this.props.isActiveCall) return;

        this.state.text = payload.text;
        this.state.speakerName = payload.speaker_name;
        this.state.isVisible = true;

        if (this.timeoutId) clearTimeout(this.timeoutId);
        this.timeoutId = setTimeout(() => {
            this.state.isVisible = false;
        }, 4000);
    }
}


