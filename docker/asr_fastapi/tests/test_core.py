import sys
import os
import numpy as np
import pytest

# Add parent directory to sys.path to allow direct imports of audio_buffer and text_filter
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from audio_buffer import AudioBuffer
from text_filter import is_hallucination, clean_transcript


def test_audio_buffer_min_duration():
    buf = AudioBuffer(min_duration_sec=0.3, max_duration_sec=8.0, sample_rate=16000)
    audio = np.zeros(1600, dtype=np.float32)  # 100ms (1600 samples)
    res = buf.add_chunk(audio, is_speech_end=True)
    assert res is None  # < 300ms (4800 samples)
    assert len(buf.chunks) == 1

    audio2 = np.zeros(3200, dtype=np.float32)  # 200ms (3200 samples)
    res2 = buf.add_chunk(audio2, is_speech_end=True)
    assert res2 is not None
    assert isinstance(res2, np.ndarray)
    assert len(res2) == 4800  # Total 4800 samples = 300ms
    assert len(buf.chunks) == 0  # Buffer cleared after return


def test_audio_buffer_max_duration():
    buf = AudioBuffer(min_duration_sec=0.3, max_duration_sec=2.0, sample_rate=16000)
    # 2.0 sec = 32000 samples
    chunk1 = np.zeros(16000, dtype=np.float32)  # 1.0 sec
    res1 = buf.add_chunk(chunk1, is_speech_end=False)
    assert res1 is None
    assert len(buf.chunks) == 1

    chunk2 = np.zeros(16000, dtype=np.float32)  # 1.0 sec -> total 2.0 sec >= max_samples
    res2 = buf.add_chunk(chunk2, is_speech_end=False)
    assert res2 is not None
    assert len(res2) == 32000
    assert len(buf.chunks) == 0


def test_audio_buffer_fresh_start_after_flush():
    buf = AudioBuffer(min_duration_sec=0.3, max_duration_sec=8.0, sample_rate=16000)
    audio = np.zeros(4800, dtype=np.float32)
    res = buf.add_chunk(audio, is_speech_end=True)
    assert res is not None
    assert len(res) == 4800

    # Next chunk should start fresh
    next_audio = np.zeros(1600, dtype=np.float32)
    res_next = buf.add_chunk(next_audio, is_speech_end=False)
    assert res_next is None
    assert len(buf.chunks) == 1


def test_hallucination_filter_blacklist():
    assert is_hallucination("cảm ơn các bạn đã theo dõi") is True
    assert is_hallucination("  CẢM ƠN ĐÃ XEM VIDEO  ") is True
    assert is_hallucination("Hãy đăng ký kênh ủng hộ mình") is True
    assert is_hallucination("Subscribe for more content") is True
    assert is_hallucination("Báo cáo cuộc họp hôm nay") is False


def test_hallucination_filter_repetition():
    # Repetition ratio > 50% with >= 6 words
    assert is_hallucination("alo alo alo alo alo xin chào xin chào") is True  # 5/8 = 62.5% "alo" > 50%
    assert is_hallucination("hôm nay chúng ta họp về dự án mới") is False
    # Less than 6 words should not trigger repetition hallucination filter
    assert is_hallucination("alo alo alo") is False


def test_clean_transcript():
    assert clean_transcript("tôi tôi muốn báo báo cáo") == "tôi muốn báo cáo"
    assert clean_transcript("báo cáo kế hoạch") == "báo cáo kế hoạch"
    assert clean_transcript("   xin xin chào   ") == "xin chào"
    assert clean_transcript("") == ""
