Where the audio actually is

Media never reaches the Odoo Python server. Odoo only does signalling over the bus/websocket. The actual audio travels either peer-to-peer (addons/mail/static/src/discuss/call/common/peer_to_peer.js) or through an external SFU — a separate Node/mediasoup service configured via mail.use_sfu_server / mail.sfu_server_url (addons/mail/tools/discuss.py:54, addons/mail/models/res_config_settings.py:43-49).

So there is no "tap the server" option. You tap the browser, the SFU, or you join the call as a bot.

Option 1 — Patch the browser client (best for a prototype)

Both ends of the audio are already exposed as plain MediaStreams in rtc_service.js:

- Local mic: getUserMedia at rtc_service.js:847; the resulting track lands in this.state.audioTrack (:2066-2068, where mic and screen audio get mixed through an AudioContext at :2056).
- Each remote participant: rtc_service.js:2196-2204 — every RTC session gets its own session.audioElement with srcObject = stream.

That per-session split is the valuable part: you get one clean stream per speaker, so speaker attribution is free — no diarization needed.

You'd patch the service and route each stream into your own graph:
const src = audioContext.createMediaStreamSource(stream);
src.connect(yourWorkletNode);   // PCM frames → encode / stream out

Odoo already does exactly this shape for voice messages — addons/mail/static/src/discuss/voice_message/common/voice_recorder.js:92-131: AudioContext → AudioWorkletNode (module served at /discuss/voice/worklet_processor) → MP3 via bundled lamejs → uploaded as an attachment. Copy that pattern and you have a recorder in a small custom addon.

Limits: only captures what that one client hears, costs the participant's CPU, and dies if they close the tab.

Option 2 — Fork the audio at the SFU (best for production)

Odoo's SFU is a separate open-source mediasoup service (not vendored here). Running your own lets you add a PlainTransport consumer that forks each participant's audio as RTP into a recorder or straight into ASR. Centralized, per-speaker tracks, no client patching, unaffected by who closes their laptop. Cost: you now operate the SFU.

Option 3 — Bot participant

Join the meeting as an extra headless participant (headless Chrome, or a Node WebRTC client) that only records. No patching of real users' clients, scales on its own box. Downside: it shows up in the participant list, and needs an Odoo user/guest token to join.