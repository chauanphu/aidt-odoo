import re
from collections import Counter

HALLUCINATION_BLACKLIST = {
    "cảm ơn các bạn đã theo dõi",
    "cảm ơn đã xem video",
    "đăng ký kênh",
    "subscribe",
}


def is_hallucination(text: str) -> bool:
    normalized = text.lower().strip()
    if any(phrase in normalized for phrase in HALLUCINATION_BLACKLIST):
        return True
    words = normalized.split()
    if len(words) >= 6:
        most_common_count = Counter(words).most_common(1)[0][1]
        if most_common_count / len(words) > 0.5:
            return True
    return False


def clean_transcript(text: str) -> str:
    # Remove consecutive repeated words (case-insensitive)
    text = re.sub(r'\b(\w+)( \1\b)+', r'\1', text, flags=re.IGNORECASE)
    return text.strip()
