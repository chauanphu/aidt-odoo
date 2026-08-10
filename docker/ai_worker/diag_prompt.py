"""So sánh cùng một luồng audio: CÓ initial_prompt vs KHÔNG có."""
import sys
import main

wav = sys.argv[1]
prompt = main.DEFAULT_ASR_PROMPT or (
    "Đây là biên bản một cuộc họp hành chính. Chúng tôi trao đổi về việc ghi âm "
    "và bóc băng biên bản, phân quyền người dùng, độ mật của văn bản, cấu hình "
    "server và cơ sở dữ liệu, cùng con model AI chạy local trên hệ thống Odoo.")

m = main.get_whisper_model(main.WHISPER_MODEL_NAME)
for label, p in (("CÓ PROMPT", prompt), ("KHÔNG PROMPT", None)):
    segs, _ = m.transcribe(
        wav, language="vi", beam_size=5, vad_filter=True,
        vad_parameters={"min_silence_duration_ms": 500, "speech_pad_ms": 200},
        no_speech_threshold=0.6, condition_on_previous_text=False,
        temperature=main.TEMPERATURE_FALLBACK, compression_ratio_threshold=2.4,
        initial_prompt=p, word_timestamps=False)
    segs = list(segs)
    print(f"\n########## {label} — {len(segs)} segment ##########")
    for s in segs:
        print(f"[{s.start:6.1f}-{s.end:6.1f}] lp={s.avg_logprob:6.2f} "
              f"ns={s.no_speech_prob:4.2f} cr={s.compression_ratio:4.2f} | {s.text.strip()}")
