"""Client Unlimited-OCR.

Công thức gọi là BẮT BUỘC, sai một trong ba thì model trả chuỗi rỗng mà
không báo lỗi gì:
  1. prompt phải mở đầu bằng literal '<image>'
  2. skip_special_tokens phải là False
  3. vllm_xargs {ngram_size: 35, window_size: N}

Đã kiểm chứng thật: một trang A4 150dpi mất ~2.7s, trả text kèm bbox và
nhãn khối theo cú pháp <|det|>nhãn [x0, y0, x1, y1]<|/det|>nội dung.
"""

import base64
import json
import re
import urllib.error
import urllib.request

from ..types import Block

PROMPT = "<image>document parsing."
NGRAM_SIZE = 35
WINDOW_IMAGE = 128          # ảnh rời
WINDOW_PDF = 1024           # trang thuộc PDF nhiều trang
DEFAULT_MODEL = "baidu/Unlimited-OCR"

_DET_RE = re.compile(
    r"<\|det\|>\s*(?P<label>[^\[\]]*?)\s*\[\s*(?P<box>[-\d.,\s]+?)\s*\]\s*<\|/det\|>"
    r"(?P<text>.*)"
)


class OcrError(RuntimeError):
    """Không gọi được service, hoặc service trả lỗi."""


class OcrEmptyOutput(OcrError):
    """Service trả rỗng — hoặc trang trắng, hoặc sai công thức gọi."""


def _http_post(url, body, timeout):
    req = urllib.request.Request(
        url, data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, OSError, ValueError) as exc:
        raise OcrError(f"gọi OCR thất bại: {exc}") from exc


def parse_ocr_output(raw):
    """Chuỗi model trả về -> list[Block]."""
    blocks = []
    for line in (raw or "").splitlines():
        line = line.strip()
        if not line:
            continue
        m = _DET_RE.match(line)
        if not m:
            # Dòng trần không có thẻ det: vẫn giữ, mất chữ tệ hơn mất toạ độ.
            blocks.append(Block(text=line))
            continue
        text = m.group("text").strip()
        if not text:
            continue
        try:
            nums = [float(v) for v in m.group("box").split(",")]
            bbox = tuple(nums[:4]) if len(nums) >= 4 else None
        except ValueError:
            bbox = None
        blocks.append(Block(text=text, bbox=bbox))
    return blocks


def ocr_image(png_bytes, base_url, model=DEFAULT_MODEL, window_size=WINDOW_PDF,
              timeout=180, transport=None):
    """PNG bytes -> list[Block]. `transport` cho test tiêm hàm giả."""
    b64 = base64.b64encode(png_bytes).decode("ascii")
    body = {
        "model": model,
        "messages": [{"role": "user", "content": [
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
            {"type": "text", "text": PROMPT},
        ]}],
        "max_tokens": 4096,
        "skip_special_tokens": False,
        "vllm_xargs": {"ngram_size": NGRAM_SIZE, "window_size": window_size},
    }
    send = transport or _http_post
    url = f"{base_url.rstrip('/')}/chat/completions"
    try:
        data = send(url, body, timeout)
    except OcrError:
        raise
    except Exception as exc:                # TimeoutError, socket.error, ...
        raise OcrError(f"gọi OCR thất bại: {exc}") from exc

    try:
        content = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise OcrError(f"OCR trả về cấu trúc lạ: {data!r}") from exc

    # Một số backend OpenAI-compatible trả content dạng list content-part
    # thay vì str thuần khi multimodal — kiểm tường minh để không rò
    # AttributeError từ .strip() xuống tầng gọi.
    if not isinstance(content, str):
        raise OcrError(f"OCR trả về content không phải chuỗi: {content!r}")

    if not content.strip():
        raise OcrEmptyOutput(
            "OCR trả rỗng — kiểm tra prompt có mở đầu bằng '<image>', "
            "skip_special_tokens=False và vllm_xargs"
        )
    return parse_ocr_output(content)
