"""Sinh audio thật cho test — KHÔNG phải tệp nhị phân đóng gói sẵn.

VÌ SAO CẦN FILE NÀY: trước 05/08/2026 mọi fixture đều đẩy `b'AUDIO'` làm nội
dung mẩu audio. Điều đó chạy được vì hồi ấy `_process_one` chuyển thẳng byte
cho ASR, mà ASR thì luôn được mock. Từ khi `audio_prep` chen vào giữa,
`b'AUDIO'` không giải mã nổi thành audio nên bị cổng lọc chặn lại và mẩu ra 0
đoạn — đúng như thiết kế, nhưng nó làm mọi test hàng đợi kiểm thứ khác.

Cách chữa KHÔNG phải mock `audio_prep` đi: làm vậy thì đường đi thật —
giải mã, lọc tiếng nói, đóng gói WAV — không bao giờ chạy trong một test tích
hợp nào. Thay vào đó sinh MP3 THẬT, đúng thứ trình duyệt gửi lên (16 kHz
mono, lamejs 32 kbps), để mọi test hàng đợi đi trọn đường ống với duy nhất
lời gọi HTTP tới ASR là giả.

Sinh tại chỗ chứ không kèm tệp mẫu: một tệp nhị phân trong repo không ai đọc
được, không ai sửa được, và không nói cho người đọc biết nó chứa gì.
"""
import io

import av
import numpy as np

SAMPLE_RATE = 16000


def speech_like_pcm(duration_ms=15000, rms=0.08, seed=0):
    """Tín hiệu "giống tiếng nói" đủ để qua cổng lọc của `audio_prep`.

    Không phải tiếng nói thật, và không cần phải thế: cổng lọc chỉ đo NĂNG
    LƯỢNG THEO KHUNG 20 ms. Thứ phải mô phỏng đúng là hình bao biên độ —
    tiếng nói có âm tiết nên năng lượng lên xuống, khác hẳn nhiễu nền phẳng
    lì. Điều chế biên độ ~5 Hz xấp xỉ nhịp âm tiết tiếng Việt.
    """
    rng = np.random.default_rng(seed)
    n = int(SAMPLE_RATE * duration_ms / 1000)
    t = np.arange(n) / SAMPLE_RATE
    # Sóng mang quanh F0 giọng người + hài, nhân với hình bao âm tiết.
    carrier = (np.sin(2 * np.pi * 180 * t)
               + 0.5 * np.sin(2 * np.pi * 360 * t)
               + 0.25 * np.sin(2 * np.pi * 540 * t))
    envelope = 0.5 + 0.5 * np.sin(2 * np.pi * 5 * t)
    x = carrier * envelope + rng.normal(0, 0.01, n)
    current = float(np.sqrt((x ** 2).mean())) or 1.0
    return (x * (rms / current)).astype(np.float32)


def to_mp3(pcm):
    """float32 mono 16 kHz -> byte MP3, đúng thông số recorder_service.js."""
    buf = io.BytesIO()
    container = av.open(buf, 'w', format='mp3')
    stream = container.add_stream('libmp3lame', rate=SAMPLE_RATE)
    stream.layout = 'mono'
    stream.bit_rate = 32000
    frame = av.AudioFrame.from_ndarray(
        (np.clip(pcm, -1, 1) * 32767).astype('<i2').reshape(1, -1),
        format='s16', layout='mono')
    frame.rate = SAMPLE_RATE
    for packet in stream.encode(frame):
        container.mux(packet)
    for packet in stream.encode(None):
        container.mux(packet)
    container.close()
    return buf.getvalue()


def speech_like_mp3(duration_ms=15000, rms=0.08, seed=0):
    return to_mp3(speech_like_pcm(duration_ms, rms, seed))


def silent_mp3(duration_ms=15000):
    """MP3 im lặng — để kiểm rằng cổng lọc THẬT SỰ chặn ở đường đi đầy đủ."""
    n = int(SAMPLE_RATE * duration_ms / 1000)
    return to_mp3(np.zeros(n, dtype=np.float32))
