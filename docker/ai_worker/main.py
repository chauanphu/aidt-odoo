"""Worker xử lý hậu kỳ cuộc họp: ghép audio -> bóc băng -> tóm tắt.

KIẾN TRÚC: mỗi máy thu MICRO CỦA CHÍNH NGƯỜI ĐÓ (xem
custom-addons/aidt_meeting_minutes/README.md §1), nên đầu vào của worker là
N luồng audio song song, KHÔNG phải một luồng nối tiếp. Đây là điều bản
trước làm sai và là gốc của phần lớn lỗi thời gian/người nói:

  * `ffmpeg -f concat` nối các mẩu theo THỨ TỰ TỆP. `seq` lại là duy nhất
    theo TỪNG NGƯỜI, nên với hai người trở lên thứ tự tệp không còn là thứ
    tự thời gian — trục thời gian của bản ghép không khớp `offset_ms` nữa,
    kéo theo gán sai người nói và sai mốc thời gian trong biên bản.
  * Mẩu do `MediaRecorder.start(timeslice)` sinh ra chỉ có mẩu ĐẦU chứa
    EBML header; các mẩu sau là fragment, KHÔNG giải mã độc lập được. Nối
    chúng như những tệp riêng biệt nghĩa là mọi cuộc họp dài hơn một nhịp
    chunk đều âm thầm mất tiếng từ mẩu thứ hai trở đi.

Cách làm ở đây: gom mẩu theo NGƯỜI, nối ở mức BYTE theo `seq` (đúng cách
ghép fragment của MediaRecorder), giải mã từng luồng người một, bóc băng
riêng từng luồng rồi trộn kết quả theo mốc thời gian TUYỆT ĐỐI. Người nói
là thứ ĐÃ BIẾT CHẮC theo luồng, không phải suy đoán theo cửa sổ thời gian.
"""

import json
import logging
import os
import re
import subprocess
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests
from fastapi import BackgroundTasks, FastAPI
from pydantic import BaseModel

try:
    from faster_whisper import WhisperModel
except ImportError:
    WhisperModel = None

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Meeting AI Worker")

MEETINGS_ROOT = Path(os.environ.get("MEETINGS_ROOT", "/var/lib/odoo/meetings"))

# --------------------------------------------------------------------------- #
# Tiền xử lý audio
# --------------------------------------------------------------------------- #
# NHẸ TAY LÀ CÓ CHỦ Ý, không phải làm cho xong. Whisper được huấn luyện trên
# audio đời thực có nhiễu; nó chịu nhiễu nhẹ TỐT HƠN chịu audio bị xử lý quá
# tay. Chuỗi filter bản trước (`lowpass=6000` + `afftdn=nf=-25` +
# `speechnorm=e=50` + `loudnorm`) sai theo cả ba hướng cùng lúc:
#   * lowpass 6000 cắt vào dải phụ âm (docs/meeting-ai-summary-flow.md §4.2
#     để 8000, và đó cũng là trần Whisper thực sự dùng);
#   * afftdn nf=-25 mạnh hơn mức -20 mà chính docs cảnh báo là "quá tay tạo
#     artifact gây ảo giác";
#   * speechnorm e=50 cho phép khuếch đại tới 50 lần — trong khoảng lặng nó
#     kéo nền nhiễu lên ngang mức giọng nói, đúng thứ khiến Whisper bịa chữ,
#     rồi loudnorm chồng thêm một tầng chuẩn hoá nữa lên trên.
# Mặc định giờ chỉ còn cắt hạ tần (ù điện, rung bàn) và chuẩn hoá mức tổng.
FILTER_GENTLE = "highpass=f=85,lowpass=f=8000,loudnorm=I=-16:TP=-1.5:LRA=11"

# Chỉ dùng khi ĐO ĐƯỢC là phòng ồn tới mức lớp nhẹ không đủ (docs §4.5: chọn
# mức NHẸ NHẤT vẫn cho transcript tốt, không chọn mức lọc mạnh nhất).
FILTER_NOISY = (
    "highpass=f=85,lowpass=f=8000,afftdn=nf=-20,"
    "dynaudnorm=f=150:g=15:p=0.7,loudnorm=I=-16:TP=-1.5:LRA=11"
)

AUDIO_FILTER_CHAIN = FILTER_NOISY if os.environ.get(
    "AUDIO_DENOISE", "gentle") == "noisy" else FILTER_GENTLE

# --------------------------------------------------------------------------- #
# Nhận dạng giọng nói
# --------------------------------------------------------------------------- #
WHISPER_MODEL_NAME = os.environ.get("WHISPER_MODEL", "large-v3")
# PHẢI là float16 trên card này, KHÔNG PHẢI int8_float16.
#
# `ctranslate2.get_supported_compute_types('cuda')` LIỆT KÊ CẢ int8_float16 —
# nó suy ra từ thuộc tính thiết bị chứ không kiểm tra kernel có thật hay
# không, nên danh sách đó không phải bằng chứng. Thử thật (10/08/2026, RTX
# 5060 Ti, compute capability 12.0 / Blackwell, ctranslate2 4.8.1): model nạp
# xong, VAD chạy xong, rồi chết ở lượt encode đầu tiên với
#   RuntimeError: cuBLAS failed with status CUBLAS_STATUS_NOT_SUPPORTED
# float16 trên đúng tệp đó chạy bình thường. Đổi lại int8 chỉ khi đã ĐO trên
# card mới, đừng suy từ việc "compute type có trong danh sách".
#
# Giá phải trả: ~3.1 GiB thay vì ~1.6 GiB. Xem ràng buộc VRAM tổng ở khối
# comment của `aidt-llm` trong docker-compose.ai.yml — chính vì chỗ này mà
# LLM_NUM_CTX phải giữ ở mức vừa phải.
WHISPER_COMPUTE_TYPE = os.environ.get("WHISPER_COMPUTE", "float16")
WHISPER_DEVICE = os.environ.get("WHISPER_DEVICE", "cuda")

# RỖNG là có chủ ý — KHÔNG đặt một prompt mặc định ở đây.
#
# Bản duy nhất của prompt mặc định nằm ở `aidt_meeting.asr_prompt` trong
# custom-addons/aidt_meeting_minutes/data/ir_config_parameter.xml, và Odoo
# luôn gửi kèm nó theo mỗi job. Để thêm một bản sao trong Python là dựng
# đúng cái bẫy mà file XML kia đã ghi rõ: hai bản sẽ lệch nhau, và bản
# trong code sẽ là bản KHÔNG chạy — nên khi ai đó sửa nó để chữa một lỗi
# bóc băng, chẳng có gì thay đổi cả.
#
# Nếu tự đặt prompt ở đây (qua ASR_PROMPT) thì PHẢI VIẾT THÀNH VĂN XUÔI,
# tuyệt đối không viết kiểu liệt kê "a, b, c": Whisper tiếp nối VĂN PHONG
# của prompt, và một danh sách đang dở thì nó đẻ thêm mục cho tới hết đoạn.
# Đã gây sự cố thật hai lần — bản ghi 1141 phía Odoo, và chính worker này
# với "Odoo, PDF, OCR, tờ trình, phụ lục." (sửa 10/08/2026).
DEFAULT_ASR_PROMPT = os.environ.get("ASR_PROMPT", "")
DEFAULT_ASR_LANGUAGE = os.environ.get("ASR_LANGUAGE", "vi")

# Dải nhiệt độ, KHÔNG phải một giá trị. faster-whisper chỉ nhảy sang mức sau
# khi mức trước cho ra kết quả hỏng (tỉ lệ nén vượt ngưỡng = lặp vòng, hoặc
# avg_logprob quá thấp). Ghim cứng 0.0 như bản trước nghĩa là TẮT hẳn lối
# thoát đó: gặp vòng lặp lặp từ thì nó lặp cho tới hết đoạn.
TEMPERATURE_FALLBACK = (0.0, 0.2, 0.4, 0.6, 0.8, 1.0)

HALLUCINATION_BLACKLIST = {
    "cảm ơn các bạn đã theo dõi",
    "cảm ơn đã xem video",
    "hẹn gặp lại các bạn",
    "hãy subscribe cho kênh",
    "đăng ký kênh",
    "nhấn like và đăng ký",
    "subscribe",
    "phụ đề được thực hiện bởi",
    "phụ đề bởi",
    "ghiền mì gõ",
}

# --------------------------------------------------------------------------- #
# Tóm tắt
# --------------------------------------------------------------------------- #
LLM_URL = os.environ.get("LLM_URL", "http://aidt-llm:11434/api/chat")
LLM_MODEL = os.environ.get("LLM_MODEL", "gemma3:12b-it-qat")
# 12288 chứ không phải 32768. Ollama chạy gemma3 12B trên card đã gần đầy;
# num_ctx càng lớn thì KV cache càng lớn và Ollama càng đẩy nhiều layer sang
# CPU (xem `ollama ps`, cột CPU/GPU). 32k làm mỗi lượt tóm tắt chậm tới mức
# chạm timeout mà không báo lỗi gì rõ ràng. 12288 vừa đủ cho một cửa sổ
# MAX_SUMMARY_CHARS cộng phần sinh ra.
LLM_NUM_CTX = int(os.environ.get("LLM_NUM_CTX", "12288"))
LLM_TIMEOUT = int(os.environ.get("LLM_TIMEOUT", "600"))
MAX_SUMMARY_CHARS = int(os.environ.get("MAX_SUMMARY_CHARS", "8000"))

# `required` là thứ bản trước THIẾU, và nó không phải chi tiết nhỏ: thiếu nó
# thì `{}` cũng là JSON hợp lệ theo schema, nên `parse_and_validate` trả về
# ngay, nhánh retry-với-phản-hồi-lỗi KHÔNG BAO GIỜ chạy, và Odoo ghi một biên
# bản rỗng rồi đánh dấu `done`. Đã xảy ra thật trên aidt_demo: bản ghi
# 2795-2797 đều `done` với transcript ~2000 ký tự nhưng mọi trường tóm tắt
# đều rỗng.
MEETING_SCHEMA = {
    "type": "object",
    "required": [
        "tong_quan", "bien_ban_chi_tiet", "y_chinh", "rui_ro",
        "cong_viec", "quyet_dinh",
    ],
    "properties": {
        "tong_quan": {"type": "string"},
        "bien_ban_chi_tiet": {"type": "string"},
        "y_chinh": {"type": "array", "items": {"type": "string"}},
        "rui_ro": {"type": "array", "items": {"type": "string"}},
        "cong_viec": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["cong_viec"],
                "properties": {
                    "cong_viec": {"type": "string"},
                    "nguoi_phu_trach": {"type": "string"},
                    "thoi_han": {"type": "string"},
                    "muc_do": {"type": "string"},
                    "thoi_gian_trong_file": {"type": "string"},
                },
            },
        },
        "quyet_dinh": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["quyet_dinh"],
                "properties": {
                    "quyet_dinh": {"type": "string"},
                    "thoi_gian_trong_file": {"type": "string"},
                },
            },
        },
    },
}

SYSTEM_PROMPT = """Bạn là trợ lý ghi biên bản cuộc họp. Nhiệm vụ: đọc bản
ghi lời nói (transcript) và trích xuất thành biên bản có cấu trúc.

QUY TẮC BẮT BUỘC:
1. CHỈ dùng thông tin có trong transcript. Tuyệt đối không suy diễn,
   không bổ sung thông tin không được nói ra.
2. Nếu một trường không có thông tin trong transcript, để chuỗi rỗng
   hoặc mảng rỗng. KHÔNG được bịa để lấp chỗ trống.
3. Mỗi công việc và quyết định PHẢI kèm mốc thời gian [mm:ss] lấy từ
   dòng transcript tương ứng nơi nội dung đó được nói. BẠN CHỈ ĐƯỢC
   DÙNG CÁC MỐC THỜI GIAN ĐÃ XUẤT HIỆN TRONG TRANSCRIPT. Tuyệt đối
   KHÔNG được tự bịa ra mốc thời gian mới.
4. Transcript là kết quả nhận dạng giọng nói nên CÓ LỖI TỪ. Nếu một câu
   không rõ nghĩa, BỎ QUA nó. Không đoán xem người nói định nói gì.
5. Trường "tong_quan" và "bien_ban_chi_tiet" PHẢI có nội dung nếu
   transcript có bất kỳ câu nào hiểu được.
6. Chỉ trả về JSON hợp lệ, không kèm giải thích, không kèm markdown.
7. BẮT BUỘC TRẢ LỜI 100% BẰNG TIẾNG VIỆT, kể cả khi transcript rất dài.
   Tuyệt đối không dùng tiếng Anh trong phần giá trị của JSON.
8. Transcript có thể chứa dòng `--- TẠM DỪNG GHI ÂM ... ---`. Đó là khoảng
   thời gian KHÔNG được ghi. Tuyệt đối không suy diễn nội dung trong khoảng
   đó và không nối hai bên thành một mạch liên tục. Nếu một công việc hoặc
   quyết định chỉ có thể suy ra từ phần bị thiếu thì BỎ QUA.

Trả về đúng schema sau: {schema}"""


# --------------------------------------------------------------------------- #
# Tiện ích ffmpeg
# --------------------------------------------------------------------------- #
def _run(cmd: List[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True)


def probe_duration_ms(path: Path) -> int:
    """Độ dài THẬT của tệp, đo bằng ffprobe.

    Không tin `duration_ms` client gửi lên: nó chỉ là hiệu số giữa hai lần
    `performance.now()` của TRÌNH DUYỆT (`recorder_service.js`), không phải
    độ dài thật của audio đã mã hoá — tab bị trình duyệt tạm ngưng (throttle
    khi chạy nền, máy vào chế độ ngủ) giữa hai lần `dataavailable` làm giá
    trị này lệch khỏi tệp thật, và một mốc sai ở đây làm lệch toàn bộ mốc
    thời gian của những người nói sau trong bản trộn.
    """
    res = _run([
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=nw=1:nk=1", str(path),
    ])
    try:
        return int(float(res.stdout.strip()) * 1000)
    except (ValueError, TypeError):
        return 0


def decode_to_wav(src: Path, dst: Path, audio_filter: str,
                  max_duration_ms: Optional[int] = None) -> bool:
    """Giải mã một tệp audio bất kỳ về WAV 16 kHz mono đã lọc.

    `max_duration_ms` cắt tại ranh giới tạm dừng. Đây là chỗ DUY NHẤT bảo
    đảm audio sau thời điểm tạm dừng không lọt vào biên bản — server vẫn
    nhận mẩu ở trạng thái `paused` để không mất lời nói ngay trước lúc dừng.
    """
    cmd = ["ffmpeg", "-y", "-i", str(src)]
    if max_duration_ms is not None:
        cmd += ["-t", f"{max_duration_ms / 1000:.3f}"]
    cmd += ["-ar", "16000", "-ac", "1", "-af", audio_filter, str(dst)]
    res = _run(cmd)
    if res.returncode != 0 or not dst.exists() or dst.stat().st_size == 0:
        logger.warning("ffmpeg không giải mã được %s: %s",
                       src.name, res.stderr[-400:])
        return False
    return True


def assemble_speaker_stream(chunk_dir: Path, speaker_key: str,
                            files: List[str], audio_filter: str,
                            max_duration_ms: Optional[int] = None) -> Optional[Path]:
    """Ghép các mẩu của MỘT người (một take) thành một WAV liên tục.

    Nối ở mức BYTE, không phải bằng `-f concat`. Mẩu do MediaRecorder sinh ra
    theo `timeslice` là các fragment của CÙNG MỘT luồng: chỉ mẩu đầu mang
    EBML header, các mẩu sau nối tiếp vào đó. Nối byte lại đúng thứ tự `seq`
    cho ra một tệp WebM hợp lệ; coi chúng là những tệp độc lập thì từ mẩu thứ
    hai trở đi không giải mã được.

    `max_duration_ms`, nếu có, là ranh giới tạm dừng của take này — truyền
    thẳng vào lượt giải mã chính. Ở lượt dự phòng (giải mã từng mẩu con khi
    luồng nối byte hỏng), ranh giới đó áp cho TỔNG thời lượng đã giải mã qua
    các mẩu, không phải cho từng mẩu riêng lẻ: nếu áp riêng lẻ, một take có
    nhiều mẩu con ngắn mà không mẩu nào tự nó vượt mốc dừng vẫn có thể cho ra
    tổng vượt mốc — lọt audio sau tạm dừng vào biên bản, đúng thứ tính năng
    này phải chặn.
    """
    raw = chunk_dir / f"stream_{speaker_key}.webm"
    with open(raw, "wb") as out:
        for name in files:
            part = chunk_dir / name
            if part.exists():
                out.write(part.read_bytes())
            else:
                logger.warning("Thiếu mẩu %s của %s", name, speaker_key)

    if raw.stat().st_size == 0:
        return None

    wav = chunk_dir / f"stream_{speaker_key}.wav"
    if decode_to_wav(raw, wav, audio_filter, max_duration_ms):
        return wav

    # Dự phòng: luồng nối byte không giải mã được (mẩu đầu bị mất, hoặc mẩu
    # tới từ đường nạp thử nghiệm nên mỗi tệp là một tệp hoàn chỉnh riêng).
    # Giải mã từng tệp một rồi nối các WAV — WAV thì nối bằng concat được.
    logger.warning("Luồng nối byte của %s hỏng, giải mã từng mẩu một",
                   speaker_key)
    parts = []
    remaining_ms = max_duration_ms
    for idx, name in enumerate(files):
        if remaining_ms is not None and remaining_ms <= 0:
            # Ngân sách đã cạn ở mẩu trước — dừng hẳn, không giải mã thêm mẩu
            # nào sau mốc tạm dừng nữa.
            break
        part = chunk_dir / name
        if not part.exists():
            continue
        part_wav = chunk_dir / f"stream_{speaker_key}_{idx}.wav"
        if decode_to_wav(part, part_wav, audio_filter, remaining_ms):
            parts.append(part_wav)
            if remaining_ms is not None:
                remaining_ms -= probe_duration_ms(part_wav)
    if not parts:
        return None
    if len(parts) == 1:
        return parts[0]

    list_file = chunk_dir / f"stream_{speaker_key}.txt"
    list_file.write_text("".join(f"file '{p}'\n" for p in parts))
    res = _run([
        "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(list_file),
        "-c", "copy", str(wav),
    ])
    return wav if res.returncode == 0 and wav.exists() else parts[0]


def mix_for_playback(chunk_dir: Path, streams: List[Dict[str, Any]]) -> Optional[Path]:
    """Trộn các luồng người nói thành một tệp để nghe lại.

    TRỘN (`amix` + `adelay` theo offset thật), không phải NỐI: các luồng chạy
    SONG SONG trong đời thực. Bản nối của phiên trước cho ra một tệp dài bằng
    TỔNG thời lượng các máy, tức là dài gấp nhiều lần cuộc họp thật, và mọi
    mốc thời gian trên đó đều vô nghĩa.
    """
    output = chunk_dir / "full_audio.wav"
    if not streams:
        return None

    cmd = ["ffmpeg", "-y"]
    for s in streams:
        cmd += ["-i", str(s["wav"])]

    parts = []
    for i, s in enumerate(streams):
        delay = max(0, int(s["offset_ms"]))
        parts.append(f"[{i}]adelay=delays={delay}:all=1[a{i}]")
    labels = "".join(f"[a{i}]" for i in range(len(streams)))
    parts.append(f"{labels}amix=inputs={len(streams)}:normalize=0[out]")

    cmd += [
        "-filter_complex", ";".join(parts), "-map", "[out]",
        "-ar", "16000", "-ac", "1", str(output),
    ]
    res = _run(cmd)
    if res.returncode != 0:
        logger.warning("Trộn audio thất bại: %s", res.stderr[-400:])
        return None
    return output


# --------------------------------------------------------------------------- #
# Lọc hậu kiểm (docs §4.4)
# --------------------------------------------------------------------------- #
# Segment ngắn hơn mức này là dấu vết vòng lặp giải mã, không phải lời nói.
# Đo ở bản ghi 2858: 36 segment "Ok" cuối luồng nằm gọn trong 85.2 -> 86.0
# giây, mỗi cái dài ~0,0 giây. Một tiếng "Ok" THẬT ở cùng bản ghi đó dài 7
# giây (74.1 -> 81.1), còn "Dạ" và "Hả?" ở bản ghi 2797 dài 0,8 và 0,6 giây.
MIN_SEGMENT_SEC = float(os.environ.get("MIN_SEGMENT_SEC", "0.2"))

# Số từ tối thiểu trước khi đem một segment đi đối chiếu với prompt. Prompt
# có chứa những từ người ta nói thật ("cuộc họp", "hệ thống", "cấu hình"),
# nên đối chiếu một câu quá ngắn sẽ ăn nhầm nội dung thật.
PROMPT_ECHO_MIN_WORDS = 8
PROMPT_ECHO_NGRAM = 4
PROMPT_ECHO_RATIO = 0.5


def _words(text: str) -> List[str]:
    return re.findall(r"\b\w+\b", text.lower())


def _ngrams(words: List[str], n: int) -> List[str]:
    return [" ".join(words[i:i + n]) for i in range(len(words) - n + 1)]


def is_prompt_echo(text: str, prompt: str, prompt_grams=None) -> bool:
    """Segment này là model ĐỌC TIẾP `initial_prompt` chứ không phải bóc băng?

    Whisper coi `initial_prompt` như văn bản đứng ngay trước audio. Gặp cửa
    sổ nghèo tín hiệu, nó nối tiếp đoạn văn đó thay vì phiên âm — và nối rất
    "tự tin". Đo ở bản ghi 2858: một segment DUY NHẤT trải 44 giây với
    avg_logprob -0.06 mang nguyên văn prompt, nuốt trọn 44 giây phát biểu
    thật. Lọc theo độ tự tin KHÔNG bắt được vì logprob của nó đẹp hơn hẳn
    lời nói thật.

    So khớp theo CỤM 4 TỪ chứ không theo từ đơn: prompt nhắc tới "cuộc họp",
    "hệ thống", "cấu hình" — đúng những từ người ta nói thật trong họp, nên
    đếm từ đơn sẽ cắt luôn nội dung thật.

    `prompt_grams` cho người gọi truyền sẵn tập cụm của prompt: prompt không
    đổi trong suốt một lượt lọc, nên dựng lại nó cho từng segment là tính đi
    tính lại một kết quả cố định vài trăm lần trên cuộc họp dài.
    """
    if not prompt:
        return False
    words = _words(text)
    if len(words) < PROMPT_ECHO_MIN_WORDS:
        return False
    grams = _ngrams(words, PROMPT_ECHO_NGRAM)
    if not grams:
        return False
    if prompt_grams is None:
        prompt_grams = set(_ngrams(_words(prompt), PROMPT_ECHO_NGRAM))
    hits = sum(1 for g in grams if g in prompt_grams)
    return hits / len(grams) >= PROMPT_ECHO_RATIO


def is_hallucination(text: str) -> bool:
    normalized = text.lower().strip()
    if not normalized:
        return True

    # Khớp blacklist — di chứng dữ liệu huấn luyện lấy từ video YouTube.
    if any(phrase in normalized for phrase in HALLUCINATION_BLACKLIST):
        return True

    clean_words = _words(normalized)

    if len(clean_words) >= 6:
        most_common_count = Counter(clean_words).most_common(1)[0][1]
        if most_common_count / len(clean_words) > 0.4:
            return True

        for n in (2, 3, 4):
            if len(clean_words) >= n * 3:
                ngrams = _ngrams(clean_words, n)
                if ngrams and Counter(ngrams).most_common(1)[0][1] >= 4:
                    return True

    # KHÔNG loại theo độ dài chữ. Luật `len(normalized) <= 3` cũ vứt sạch
    # "Ok", "Dạ", "Vâng", "Hả?" — ở bản ghi 2858 nó loại 36 segment và TẤT
    # CẢ đều là "Ok", trong đó có cả tiếng đồng ý thật dài 7 giây. Trong
    # biên bản hành chính, đó chính là chỗ ghi nhận sự đồng thuận. Vòng lặp
    # giải mã nay nhận ra bằng THỜI LƯỢNG (MIN_SEGMENT_SEC), thứ phân biệt
    # được tiếng "Ok" thật với 36 tiếng "Ok" dài 0 giây.
    return False


def clean_text(text: str) -> str:
    # Xoá cụm từ lặp liên tiếp: "chào mọi người chào mọi người" -> "chào mọi người"
    text = re.sub(r"\b(.+?)( \1\b)+", r"\1", text, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", text).strip()


def filter_segments(segments: List[Dict[str, Any]],
                    prompt: str = "") -> List[Dict[str, Any]]:
    """Lọc theo độ tự tin, thời lượng, nhả ngược prompt và dấu hiệu ảo giác.

    Bản trước gọi `clean_text` nhưng KHÔNG bao giờ gọi `is_hallucination` —
    blacklist và bộ bắt lặp từ nằm đó như code chết, tức lớp 4 của docs §4.4
    trên thực tế chưa từng chạy.
    """
    kept, dropped = [], []
    prompt_grams = (set(_ngrams(_words(prompt), PROMPT_ECHO_NGRAM))
                    if prompt else None)

    for seg in segments:
        if seg.get("avg_logprob", 0) < -1.0 or seg.get("no_speech_prob", 0) > 0.6:
            dropped.append({**seg, "reason": "low_confidence"})
            continue

        # Thời lượng TRƯỚC nội dung: vòng lặp giải mã sinh ra hàng chục
        # segment dài 0 giây mà chữ thì hoàn toàn bình thường.
        if (seg.get("end", 0) - seg.get("start", 0)) < MIN_SEGMENT_SEC:
            dropped.append({**seg, "reason": "zero_duration"})
            continue

        cleaned = clean_text(seg["text"])

        if is_prompt_echo(cleaned, prompt, prompt_grams):
            dropped.append({**seg, "reason": "prompt_echo"})
            continue

        if is_hallucination(cleaned):
            dropped.append({**seg, "reason": "hallucination"})
            continue

        # Cùng một câu lặp lại LIÊN TIẾP là vòng lặp, kể cả khi mỗi segment
        # có thời lượng hợp lệ. So với segment được GIỮ gần nhất, không phải
        # segment đầu vào gần nhất, để một câu bị chèn giữa bởi rác đã loại
        # vẫn bắt được.
        if kept and _words(cleaned) == _words(kept[-1]["text"]):
            dropped.append({**seg, "reason": "repeat_of_previous"})
            continue

        kept.append({**seg, "text": cleaned})

    total = len(kept) + len(dropped)
    if total:
        ratio = len(dropped) / total
        logger.info("Giữ %s segment, loại %s (%.0f%%)",
                    len(kept), len(dropped), ratio * 100)
        # docs §10: loại quá 15%% là dấu hiệu lọc quá gắt, đang cắt cả câu thật.
        if ratio > 0.15:
            logger.warning(
                "Tỉ lệ loại %.0f%% vượt ngưỡng 15%% — xem lại ngưỡng lọc hoặc "
                "chất lượng thu âm. Đã loại: %s", ratio * 100,
                [(d.get("reason"), d.get("text", "")[:60]) for d in dropped])
    return kept


# --------------------------------------------------------------------------- #
# Bóc băng
# --------------------------------------------------------------------------- #
_whisper_model = None
_whisper_model_name = None


def get_whisper_model(model_name: str):
    global _whisper_model, _whisper_model_name
    if WhisperModel is None:
        return None
    if _whisper_model is None or _whisper_model_name != model_name:
        logger.info("Nạp model ASR %s (%s, %s)",
                    model_name, WHISPER_DEVICE, WHISPER_COMPUTE_TYPE)
        _whisper_model = WhisperModel(
            model_name,
            device=WHISPER_DEVICE,
            compute_type=WHISPER_COMPUTE_TYPE,
            num_workers=1,
        )
        _whisper_model_name = model_name
    return _whisper_model


def transcribe_stream(audio_path: Path, model_name: str, prompt: str,
                      language: Optional[str] = None) -> List[Dict[str, Any]]:
    model = get_whisper_model(model_name)
    if not model:
        logger.error("faster_whisper chưa được cài")
        return []

    segments, _info = model.transcribe(
        str(audio_path),
        # Để RỖNG = model tự nhận dạng, một lựa chọn thật cho họp song ngữ.
        # Ghim cứng "vi" ở đây thì tuỳ chọn đó không tồn tại.
        language=language or None,
        beam_size=5,
        vad_filter=True,
        vad_parameters={
            "min_silence_duration_ms": 500,
            "speech_pad_ms": 200,
        },
        no_speech_threshold=0.6,
        # Vẫn tắt: bật lên thì một câu bịa sẽ trở thành ngữ cảnh cho câu sau
        # và kéo theo cả chuỗi bịa tiếp.
        condition_on_previous_text=False,
        temperature=TEMPERATURE_FALLBACK,
        # Ngưỡng tỉ lệ nén: transcript lặp vòng nén rất tốt, nên vượt ngưỡng
        # này là tín hiệu để nhảy sang mức nhiệt độ sau thay vì trả kết quả hỏng.
        compression_ratio_threshold=2.4,
        initial_prompt=prompt or None,
        word_timestamps=False,
    )

    results = []
    for seg in segments:
        results.append({
            "start": seg.start,
            "end": seg.end,
            "text": seg.text.strip(),
            "avg_logprob": seg.avg_logprob,
            "no_speech_prob": seg.no_speech_prob,
        })
    return results


def normalize_timestamp(value: Any) -> str:
    """Gọt mốc thời gian LLM trả về thành `mm:ss` / `hh:mm:ss` trần.

    Transcript đưa vào có dạng `[01:56] Tên: ...`, và model bê nguyên cả cặp
    ngoặc vuông vào JSON. Cột "Thời gian trong file" trên giao diện là một
    trường Char nên nó hiện đúng những gì được ghi — kể cả dấu ngoặc.
    """
    if not value:
        return ""
    match = re.search(r"\d{1,2}:\d{2}(?::\d{2})?", str(value))
    return match.group(0) if match else ""


def format_timestamp(seconds: float) -> str:
    h, rem = divmod(int(seconds), 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


def format_duration_vi(ms: int) -> str:
    """'3 phút 28 giây'. Người đọc biên bản cần biết mất bao nhiêu, không
    phải một con số mili-giây."""
    total = max(0, ms) // 1000
    minutes, seconds = divmod(total, 60)
    if minutes and seconds:
        return f"{minutes} phút {seconds} giây"
    if minutes:
        return f"{minutes} phút"
    return f"{seconds} giây"


def pause_marker(pause: Dict[str, Any]) -> str:
    start = format_timestamp(pause["paused_at_ms"] / 1000)
    resumed = pause.get("resumed_at_ms") or 0
    if not resumed:
        # Không bịa một mốc kết thúc: ta biết lúc dừng, không biết cuộc họp
        # còn kéo dài bao lâu sau đó. `resumed_at_ms` là `None` (JSON null)
        # cho một khoảng dừng còn mở; `0` cũng được coi là "chưa ghi tiếp"
        # để phòng thủ, dù đường xuất dữ liệu thật không còn sinh ra nó.
        return (f"--- TẠM DỪNG GHI ÂM {start} — không ghi tiếp "
                f"cho tới hết cuộc họp ---")
    end = format_timestamp(resumed / 1000)
    gap = format_duration_vi(resumed - pause["paused_at_ms"])
    return f"--- TẠM DỪNG GHI ÂM {start} → {end} ({gap} không được ghi) ---"


def build_transcript_for_llm(segments: List[Dict[str, Any]],
                             pauses: List[Dict[str, Any]] = ()) -> str:
    """Transcript có mốc thời gian, kèm dòng đánh dấu các đoạn không được ghi.

    Mốc phải nằm ĐÚNG vị trí thời gian của nó giữa hai câu, chứ không gom
    hết xuống cuối: model đọc theo thứ tự, và một đoạn thiếu đặt sai chỗ còn
    khó hiểu hơn là không đánh dấu.
    """
    events = [(s["abs_start"], 0, s) for s in segments]
    events += [(p["paused_at_ms"], 1, p) for p in (pauses or [])]
    events.sort(key=lambda e: (e[0], e[1]))

    lines = []
    for _at, kind, item in events:
        if kind == 1:
            lines.append(pause_marker(item))
            continue
        stamp = format_timestamp(item["abs_start"] / 1000)
        speaker = item.get("speaker")
        lines.append(f"[{stamp}] {speaker}: {item['text']}" if speaker
                     else f"[{stamp}] {item['text']}")
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# Tóm tắt bằng LLM
# --------------------------------------------------------------------------- #
def call_llm(system: str, user: str, model: str, url: str,
             temperature: float = 0.2) -> str:
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "options": {
            "temperature": temperature,
            "num_ctx": LLM_NUM_CTX,
            "num_predict": 4096,
        },
        "stream": False,
    }
    resp = requests.post(url, json=payload, timeout=LLM_TIMEOUT)
    resp.raise_for_status()
    return resp.json()["message"]["content"]


def _strip_fence(raw: str) -> str:
    return (raw.strip().removeprefix("```json").removeprefix("```")
            .removesuffix("```").strip())


def _is_blank_summary(data: dict) -> bool:
    return not any([
        (data.get("tong_quan") or "").strip(),
        (data.get("bien_ban_chi_tiet") or "").strip(),
        data.get("y_chinh"), data.get("rui_ro"),
        data.get("cong_viec"), data.get("quyet_dinh"),
    ])


def parse_and_validate(raw: str, model: str, url: str,
                       max_retry: int = 2) -> dict:
    from jsonschema import ValidationError, validate

    try:
        data = json.loads(_strip_fence(raw))
        validate(instance=data, schema=MEETING_SCHEMA)
    except (json.JSONDecodeError, ValidationError) as exc:
        if max_retry > 0:
            return _retry_with_feedback(raw, str(exc), model, url, max_retry - 1)
        raise

    # Hợp schema nhưng rỗng toàn bộ vẫn là một lượt hỏng — bắt riêng, vì
    # jsonschema không có cách nào diễn đạt "ít nhất một trường có nội dung".
    if _is_blank_summary(data) and max_retry > 0:
        return _retry_with_feedback(
            raw, "Toàn bộ các trường đều rỗng. Transcript có nội dung nên "
                 "ít nhất 'tong_quan' và 'bien_ban_chi_tiet' phải có chữ.",
            model, url, max_retry - 1)
    return data


def _retry_with_feedback(raw: str, error: str, model: str, url: str,
                         max_retry: int) -> dict:
    logger.warning("Tóm tắt không hợp lệ, thử lại (%s lượt còn lại): %s",
                   max_retry, error)
    feedback = (f"Output JSON của bạn bị lỗi: {error}\n"
                f"Hãy sửa lại thành JSON hợp lệ theo đúng schema. "
                f"Nội dung bạn đã tạo:\n{raw}")
    response = call_llm(
        system=SYSTEM_PROMPT.format(
            schema=json.dumps(MEETING_SCHEMA, ensure_ascii=False)),
        user=feedback, model=model, url=url, temperature=0.1)
    return parse_and_validate(response, model, url, max_retry)


def chunk_transcript(transcript: str, max_chars: int) -> List[str]:
    chunks, current, current_len = [], [], 0
    for line in transcript.split("\n"):
        if current_len + len(line) > max_chars and current:
            chunks.append("\n".join(current))
            current, current_len = [line], len(line)
        else:
            current.append(line)
            current_len += len(line) + 1
    if current:
        chunks.append("\n".join(current))
    return chunks


def merge_summaries(summaries: List[dict], model: str, url: str) -> dict:
    y_chinh, rui_ro, cong_viec, quyet_dinh = [], [], [], []
    tong_quan_parts, bien_ban_parts = [], []

    for s in summaries:
        y_chinh.extend(s.get("y_chinh", []))
        rui_ro.extend(s.get("rui_ro", []))
        cong_viec.extend(s.get("cong_viec", []))
        quyet_dinh.extend(s.get("quyet_dinh", []))
        if s.get("tong_quan"):
            tong_quan_parts.append(s["tong_quan"])
        if s.get("bien_ban_chi_tiet"):
            bien_ban_parts.append(s["bien_ban_chi_tiet"])

    merge_prompt = f"""Dưới đây là các phần tóm tắt tổng quan và biên bản chi tiết của từng phần cuộc họp.
Hãy tổng hợp chúng thành một BẢN TỔNG QUAN chung và một BIÊN BẢN CHI TIẾT chung duy nhất, mạch lạc và xuyên suốt.
BẮT BUỘC TRẢ LỜI 100% BẰNG TIẾNG VIỆT.
Chỉ trả về JSON hợp lệ theo schema sau:
{{
    "tong_quan": "Tổng quan chung",
    "bien_ban_chi_tiet": "Biên bản chi tiết chung"
}}

Các phần tổng quan:
{" --- ".join(tong_quan_parts)}

Các phần biên bản:
{" --- ".join(bien_ban_parts)}
"""
    final = {"tong_quan": "", "bien_ban_chi_tiet": ""}
    if tong_quan_parts or bien_ban_parts:
        try:
            resp = call_llm(
                system="Bạn là trợ lý tổng hợp biên bản cuộc họp. Chỉ trả về "
                       "JSON hợp lệ, không Markdown, không giải thích.",
                user=merge_prompt, model=model, url=url, temperature=0.2)
            final = json.loads(_strip_fence(resp))
        except Exception as exc:                                # noqa: BLE001
            logger.warning("Không hợp nhất được các bản tóm tắt: %s", exc)
            final["tong_quan"] = "\n".join(tong_quan_parts)
            final["bien_ban_chi_tiet"] = "\n\n".join(bien_ban_parts)

    return {
        "tong_quan": final.get("tong_quan", ""),
        "bien_ban_chi_tiet": final.get("bien_ban_chi_tiet", ""),
        "y_chinh": list(dict.fromkeys(y_chinh)),
        "rui_ro": list(dict.fromkeys(rui_ro)),
        "cong_viec": cong_viec,
        "quyet_dinh": quyet_dinh,
    }


def summarize_meeting(transcript: str, model: str, url: str) -> dict:
    chunks = chunk_transcript(transcript, MAX_SUMMARY_CHARS)
    system = SYSTEM_PROMPT.format(
        schema=json.dumps(MEETING_SCHEMA, ensure_ascii=False))

    if len(chunks) == 1:
        response = call_llm(
            system=system, user=f"Transcript cuộc họp:\n\n{chunks[0]}",
            model=model, url=url, temperature=0.2)
        return parse_and_validate(response, model, url)

    partials = []
    for idx, chunk in enumerate(chunks):
        logger.info("Tóm tắt phần %s/%s", idx + 1, len(chunks))
        try:
            response = call_llm(
                system=system,
                user=f"Đây là phần {idx + 1}/{len(chunks)} của transcript "
                     f"cuộc họp. Hãy phân tích phần này:\n\n{chunk}",
                model=model, url=url, temperature=0.2)
            partials.append(parse_and_validate(response, model, url))
        except Exception as exc:                                # noqa: BLE001
            logger.warning("Không phân tích được phần %s: %s", idx + 1, exc)
    return merge_summaries(partials, model, url)


# --------------------------------------------------------------------------- #
# Job
# --------------------------------------------------------------------------- #
class JobPayload(BaseModel):
    meeting_id: int
    total_chunks: int
    webhook_url: str
    # Cấu hình do Odoo đẩy sang, để mấy ô trong Cài đặt thật sự điều khiển
    # được worker. Bản trước ghim cứng model/URL ở đây nên mọi thay đổi trong
    # giao diện quản trị đều không có tác dụng gì.
    asr_model: Optional[str] = None
    asr_prompt: Optional[str] = None
    asr_language: Optional[str] = None
    llm_model: Optional[str] = None
    llm_url: Optional[str] = None


def _pause_bound_for(take_offset_ms: int, pauses: List[Dict[str, Any]]):
    """Mốc tạm dừng ngay SAU lần ghi bắt đầu tại `take_offset_ms`, nếu có.

    Trả về số mili-giây tối đa mà lần ghi đó được phép dài, hoặc None nếu
    sau nó không có lần tạm dừng nào (tức là lần ghi cuối). Chỉ cần
    `paused_at_ms` để tính ranh giới cắt — `resumed_at_ms` là null (khoảng
    dừng còn mở, dừng tới hết cuộc họp) không làm sai kết quả ở đây vì nó
    không được đọc tới; nhầm null thành 0 chỉ nguy hiểm ở chỗ khác (tính mốc
    ghi tiếp), không phải ở hàm này.
    """
    after = [p["paused_at_ms"] for p in pauses
             if p.get("paused_at_ms", 0) > take_offset_ms]
    if not after:
        return None
    return min(after) - take_offset_ms


# Phân biệt "người gọi không truyền `meta`" với "đã đọc và đúng là không có
# metadata" (`None`) — hai thứ đó dẫn tới hai nhánh khác nhau ở `_load_streams`.
_UNSET = object()


def _load_metadata(chunk_dir: Path) -> Any:
    """Đọc và parse `metadata.json` đúng MỘT lần cho cả job.

    Trả `None` khi không có file. Ba nơi cần dữ liệu này (`_load_streams` cho
    speakers, cùng nó cho ranh giới cắt, và `process_meeting_task` cho mốc
    tạm dừng trong biên bản) — trước đây mỗi nơi tự mở file nên một job mở
    đĩa và parse JSON ba lần cho cùng một nội dung không đổi.
    """
    meta_file = chunk_dir / "metadata.json"
    if not meta_file.exists():
        return None
    return json.loads(meta_file.read_text())


def _pauses_from(meta: Any) -> List[Dict[str, Any]]:
    """Nguồn DUY NHẤT diễn giải trường `pauses`.

    Dùng chung cho `_load_streams` (cắt ranh giới take ở Task 10) và
    `process_meeting_task` (chèn mốc vào biên bản ở Task 11). Trước đây hai
    nơi tự lặp lại `isinstance`/`.get("pauses", [])`; gộp vào đây để một sửa
    đổi cách đọc field (đổi tên trường, thêm khuôn dạng mới, ...) không thể
    lệch âm thầm giữa hai chỗ.
    """
    return meta.get("pauses", []) if isinstance(meta, dict) else []


def _load_streams(chunk_dir: Path, total_chunks: int,
                  meta: Any = _UNSET) -> List[Dict[str, Any]]:
    """Mỗi phần tử trả về là một cặp (người, lần ghi) — một luồng độc lập.

    Nối byte CHỈ hợp lệ trong phạm vi một take: khi tạm dừng, client dừng
    `MediaRecorder` và lúc ghi tiếp tạo một cái mới mang EBML header riêng.
    Nối xuyên take cho ra tệp có header nằm giữa, ffmpeg giải mã phần đầu rồi
    dừng — mất im lặng toàn bộ phần sau lần ghi tiếp.

    Chấp nhận cả khuôn dạng cũ (một tầng, không có `takes`) để job đã nằm sẵn
    trên đĩa vẫn chạy lại được.

    `meta` nhận sẵn bản đã parse để không đọc lại đĩa; bỏ trống thì tự đọc
    (đường dùng của test).
    """
    if meta is _UNSET:
        meta = _load_metadata(chunk_dir)
    if meta is None:
        files = [f"chunk_{i}.webm" for i in range(total_chunks)]
        return [{"key": "0_t0", "name": "", "take": 0, "offset_ms": 0,
                 "files": files, "max_duration_ms": None}]

    pauses = _pauses_from(meta)
    speakers = meta.get("speakers", meta) if isinstance(meta, dict) else meta

    streams: List[Dict[str, Any]] = []
    for idx, spk in enumerate(speakers):
        key = str(spk.get("partner_id") or spk.get("speaker_name") or idx)
        name = spk.get("speaker_name") or ""
        takes = spk.get("takes")
        if takes is None:
            # Khuôn dạng cũ: cả người là một lần ghi liền mạch.
            takes = [{"take": 0,
                      "offset_ms": int(spk.get("offset_ms") or 0),
                      "files": list(spk.get("files") or [])}]
        for take in takes:
            offset_ms = int(take.get("offset_ms") or 0)
            streams.append({
                "key": f"{key}_t{take.get('take', 0)}",
                "name": name,
                "take": int(take.get("take", 0)),
                "offset_ms": offset_ms,
                "files": list(take.get("files") or []),
                "max_duration_ms": _pause_bound_for(offset_ms, pauses),
            })
    return streams


def _notify_failure(webhook_url: str, message: str) -> None:
    """Báo lỗi NGƯỢC VỀ Odoo.

    Bản trước chỉ ghi log rồi im: bản ghi kẹt ở `processing` vĩnh viễn, trạng
    thái `failed` có trong Selection nhưng không có đường nào đặt được nó, và
    người dùng không có cách gì biết là hỏng ngoài việc ngồi đợi.
    """
    try:
        requests.post(webhook_url, json={"error": message}, timeout=10)
    except Exception:                                           # noqa: BLE001
        logger.exception("Không báo được lỗi về Odoo")


def process_meeting_task(meeting_id: int, total_chunks: int, webhook_url: str,
                         asr_model: Optional[str] = None,
                         asr_prompt: Optional[str] = None,
                         asr_language: Optional[str] = None,
                         llm_model: Optional[str] = None,
                         llm_url: Optional[str] = None):
    logger.info("Bắt đầu xử lý cuộc họp %s", meeting_id)
    model_name = asr_model or WHISPER_MODEL_NAME
    prompt = DEFAULT_ASR_PROMPT if asr_prompt is None else asr_prompt
    language = DEFAULT_ASR_LANGUAGE if asr_language is None else asr_language
    llm = llm_model or LLM_MODEL
    llm_endpoint = llm_url or LLM_URL

    try:
        chunk_dir = MEETINGS_ROOT / str(meeting_id)
        meta = _load_metadata(chunk_dir)
        raw_streams = _load_streams(chunk_dir, total_chunks, meta=meta)

        streams = []
        for item in raw_streams:
            if not item["files"]:
                continue
            wav = assemble_speaker_stream(
                chunk_dir, item["key"], item["files"], AUDIO_FILTER_CHAIN,
                item["max_duration_ms"])
            if wav:
                streams.append({**item, "wav": wav,
                                "duration_ms": probe_duration_ms(wav)})

        if not streams:
            raise ValueError("Không có luồng audio nào giải mã được")

        # Nghe lại: trộn song song theo offset thật.
        mix_for_playback(chunk_dir, streams)

        # Bóc băng TỪNG LUỒNG. Người nói là thứ đã biết theo luồng, không phải
        # suy ra từ cửa sổ thời gian như bản trước.
        segments: List[Dict[str, Any]] = []
        for stream in streams:
            raw_segments = transcribe_stream(
                stream["wav"], model_name, prompt, language)
            for seg in raw_segments:
                seg["abs_start"] = stream["offset_ms"] + int(seg["start"] * 1000)
                seg["abs_end"] = stream["offset_ms"] + int(seg["end"] * 1000)
                seg["speaker"] = stream["name"]
            logger.info("Luồng %s (%s, lần ghi %s): %s segment thô",
                        stream["key"], stream["name"], stream["take"],
                        len(raw_segments))
            segments.extend(raw_segments)

        segments.sort(key=lambda s: s["abs_start"])
        segments = filter_segments(segments, prompt=prompt)

        pauses = _pauses_from(meta)
        transcript_raw = build_transcript_for_llm(segments, pauses)

        summary_data = {}
        if transcript_raw.strip():
            summary_data = summarize_meeting(transcript_raw, llm, llm_endpoint)
        else:
            logger.warning("Cuộc họp %s: transcript rỗng sau khi lọc",
                           meeting_id)

        webhook_payload = {
            "title": (summary_data.get("tong_quan", "") or "")[:100],
            "overview": summary_data.get("tong_quan", ""),
            "meeting_minutes": summary_data.get("bien_ban_chi_tiet", ""),
            "key_points": [{"content": k} for k in summary_data.get("y_chinh", [])],
            "risks": [{"content": r} for r in summary_data.get("rui_ro", [])],
            "action_items": [
                {
                    "task": item.get("cong_viec"),
                    "owner": item.get("nguoi_phu_trach"),
                    "deadline": item.get("thoi_han"),
                    "priority": item.get("muc_do"),
                    "timestamp": normalize_timestamp(item.get("thoi_gian_trong_file")),
                } for item in summary_data.get("cong_viec", [])
            ],
            "decisions": [
                {
                    "content": d.get("quyet_dinh"),
                    "timestamp": normalize_timestamp(d.get("thoi_gian_trong_file")),
                } for d in summary_data.get("quyet_dinh", [])
            ],
            "transcript_raw": transcript_raw,
        }

        logger.info("Gửi kết quả về %s", webhook_url)
        requests.post(webhook_url, json=webhook_payload, timeout=30)

    except Exception as exc:                                    # noqa: BLE001
        logger.exception("Lỗi khi xử lý cuộc họp %s", meeting_id)
        _notify_failure(webhook_url, f"{type(exc).__name__}: {exc}")


@app.on_event("startup")
def _preload_model():
    """Nạp model ASR NGAY LÚC KHỞI ĐỘNG, không đợi job đầu tiên.

    Không phải để chạy nhanh hơn — để THỨ TỰ CẤP PHÁT VRAM là xác định.
    Card này chia cho ba bên và chỉ có `aidt-embed` (vLLM) cấp phát trước
    theo tỉ lệ cố định; Ollama thì đo chỗ trống lúc nạp rồi tự co giãn, nên
    nó phải vào SAU CÙNG (xem khối comment của `aidt-llm`). Nạp lười cả hai
    phía nghĩa là ai gửi request trước thì bên đó chiếm chỗ trước — và bên
    thua sẽ chết bằng OOM giữa một cuộc họp thật chứ không phải lúc khởi
    động. Đã xảy ra: Ollama nạp trước với context 32768 chiếm 11.4 GiB, để
    lại 2.4 GiB và faster-whisper chết với "CUDA failed with error out of
    memory".
    """
    try:
        get_whisper_model(WHISPER_MODEL_NAME)
    except Exception:                                           # noqa: BLE001
        # Không chặn khởi động: healthcheck sẽ vẫn xanh, còn job đầu tiên sẽ
        # báo lỗi ngược về Odoo qua `_notify_failure` thay vì chết âm thầm.
        logger.exception("Không nạp được model ASR lúc khởi động")


@app.get("/health")
def health():
    return {"status": "ok", "asr_model": WHISPER_MODEL_NAME,
            "asr_loaded": _whisper_model is not None}


@app.post("/jobs/process_meeting")
def create_job(payload: JobPayload, background_tasks: BackgroundTasks):
    background_tasks.add_task(
        process_meeting_task, payload.meeting_id, payload.total_chunks,
        payload.webhook_url, payload.asr_model, payload.asr_prompt,
        payload.asr_language, payload.llm_model, payload.llm_url)
    return {"status": "queued"}
