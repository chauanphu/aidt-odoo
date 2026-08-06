import { Call } from "@mail/discuss/call/common/call";
import { RecordingBanner } from "@aidt_meeting_minutes/recording_banner";
import { RecordingSubtitle } from "@aidt_meeting_minutes/recording_subtitle";

// Tách khỏi recording_banner.js để tránh vòng import (component <-> patch
// đăng ký chính component đó vào Call).
Call.components = { ...Call.components, RecordingBanner, RecordingSubtitle };

