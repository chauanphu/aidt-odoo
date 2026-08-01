"""Nhánh PDF: bọc poppler-utils.

Dùng CLI thay vì thư viện Python có chủ ý. PyMuPDF là AGPL-3, không dùng
được cho module LGPL-3. Và ta đã cần pdftoppm để rasterize trang scan, nên
lấy luôn pdftotext/pdfinfo cùng gói là không tốn thêm dependency nào.
"""

import re
import subprocess

DEFAULT_DPI = 150
_TIMEOUT = 120
_PAGES_RE = re.compile(r"^Pages:\s+(\d+)", re.MULTILINE)


class PdfToolError(RuntimeError):
    """poppler không chạy được, hoặc tệp không đọc được."""


def _run(args, **kwargs):
    try:
        return subprocess.run(args, check=True, capture_output=True,
                               timeout=_TIMEOUT, **kwargs)
    except FileNotFoundError as exc:
        raise PdfToolError(f"thiếu poppler-utils: {args[0]}") from exc
    except subprocess.TimeoutExpired as exc:
        raise PdfToolError(f"{args[0]} quá thời gian") from exc
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or b"").decode("utf-8", "replace").strip()
        raise PdfToolError(f"{args[0]} lỗi: {detail}") from exc


def page_count(path):
    out = _run(["pdfinfo", path]).stdout.decode("utf-8", "replace")
    m = _PAGES_RE.search(out)
    if not m:
        raise PdfToolError("pdfinfo không trả về số trang")
    return int(m.group(1))


def page_text(path, page):
    """Text của một trang. -layout giữ cột và khoảng cách, giúp nhận vùng.

    Ép -enc UTF-8 tường minh: mặc định của pdftotext tuỳ bản dựng poppler,
    không ép thì output có thể ra một encoding khác trên một số hệ thống.
    """
    out = _run(["pdftotext", "-layout", "-enc", "UTF-8",
                "-f", str(page), "-l", str(page), path, "-"])
    return out.stdout.decode("utf-8", "replace")


def render_page_png(path, page, dpi=DEFAULT_DPI):
    """Rasterize một trang thành PNG để đưa vào OCR.

    KHÔNG truyền PPM-root: với poppler (đã kiểm chứng trên bản 22.12.0),
    pdftoppm tự ghi ra stdout khi không có PPM-root, kể cả khi có -f/-l.
    Truyền thêm '-' bị hiểu là PPM-root theo nghĩa đen — pdftoppm sẽ ghi
    tệp "--<n>.png" ra đĩa (không phải stdout), khiến hàm này nhận 0 byte
    hoặc lỗi "Could not write image" nếu cwd không ghi được.
    """
    out = _run(["pdftoppm", "-png", "-r", str(dpi),
                "-f", str(page), "-l", str(page), path])
    if not out.stdout.startswith(b"\x89PNG"):
        raise PdfToolError(f"pdftoppm không trả về PNG cho trang {page}")
    return out.stdout
