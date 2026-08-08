import time
from collections import deque
import numpy as np


class AudioBuffer:
    def __init__(self, min_duration_sec: float = 0.3, max_duration_sec: float = 8.0, sample_rate: int = 16000):
        self.chunks = deque()
        self.min_samples = int(min_duration_sec * sample_rate)
        self.max_samples = int(max_duration_sec * sample_rate)
        self.sample_rate = sample_rate

    def add_chunk(self, audio: np.ndarray, is_speech_end: bool):
        self.chunks.append(audio)
        total_samples = sum(len(c) for c in self.chunks)
        if (is_speech_end and total_samples >= self.min_samples) or total_samples >= self.max_samples:
            merged = np.concatenate(list(self.chunks))
            self.chunks.clear()
            return merged
        return None
