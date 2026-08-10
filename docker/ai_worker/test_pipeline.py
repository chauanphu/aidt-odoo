"""Chạy lại pipeline bóc băng trên một thư mục cuộc họp có sẵn, không gọi webhook."""
import sys, json
from pathlib import Path
import main

meeting_id = sys.argv[1]
chunk_dir = main.MEETINGS_ROOT / meeting_id
speakers = main._load_speakers(chunk_dir, 0)
print("speakers:", json.dumps(speakers, ensure_ascii=False))

streams = []
for spk in speakers:
    wav = main.assemble_speaker_stream(chunk_dir, spk["key"], spk["files"], main.AUDIO_FILTER_CHAIN)
    if wav:
        streams.append({**spk, "wav": wav, "duration_ms": main.probe_duration_ms(wav)})
print("streams:", [(s["key"], s["name"], s["offset_ms"], s["duration_ms"]) for s in streams])

segs = []
for st in streams:
    raw = main.transcribe_stream(st["wav"], main.WHISPER_MODEL_NAME, main.DEFAULT_ASR_PROMPT)
    for s in raw:
        s["abs_start"] = st["offset_ms"] + int(s["start"] * 1000)
        s["abs_end"] = st["offset_ms"] + int(s["end"] * 1000)
        s["speaker"] = st["name"]
    segs.extend(raw)
segs.sort(key=lambda s: s["abs_start"])
segs = main.filter_segments(segs)
print("=== TRANSCRIPT ===")
print(main.build_transcript_for_llm(segs))
