import fractions
import io
import logging
import struct

import av
import numpy as np

from odoo import api, models

_logger = logging.getLogger(__name__)

# Định dạng ASR nhận: 16 kHz mono. Đây KHÔNG phải một lựa chọn tuỳ ý — mọi
# checkpoint dòng Whisper đều lấy mẫu lại về đúng 16 kHz ở bên trong, nên gửi
# cao hơn chỉ tốn băng thông rồi bị hạ xuống bằng một bộ lấy mẫu ta không
# kiểm soát được. Làm sẵn ở đây thì ta biết chính xác model nghe thấy gì.
SAMPLE_RATE = 16000

# ------------------------------------------------------------------------- #
# Hằng số cổng lọc tiếng nói
# ------------------------------------------------------------------------- #
# BẰNG CHỨNG ĐO ĐƯỢC — 05/08/2026, gửi thẳng WAV tổng hợp 15 giây (16 kHz
# mono) tới ĐÚNG dịch vụ và ĐÚNG model mà cổng này sinh ra để bảo vệ
# (`openai/whisper-large-v3` trên `http://aidt-asr:8002`). Đầu ra nguyên văn:
#
#   im lặng số (toàn 0)   RMS 0.00000 -> "Hãy subscribe cho kênh La La School
#                                         Để không bỏ lỡ những video hấp dẫn"
#   nhiễu Gauss           RMS 0.00100 -> "Cảm ơn các bạn đã theo dõi và hẹn
#                                         gặp lại."
#   nhiễu Gauss "nền phòng" RMS 0.00599 -> "Cảm ơn các bạn đã theo dõi và hẹn
#                                         gặp lại."
#   tông 440 Hz           RMS 0.19797 -> "Hãy subscribe cho kênh La La School
#                                         Để không bỏ lỡ những video hấp dẫn"
#
# HÀNG QUYẾT ĐỊNH LÀ HÀNG 0.00599: nó VƯỢT `RMS_FLOOR = 0.005` của
# `static/src/recorder_service.js`, nghĩa là HÔM NAY nó đi lọt lên tới ASR và
# đẻ ra một câu bịa. Cổng này bắt buộc phải chặn được nó — đó là ràng buộc
# cứng, không phải sở thích.
#
# HÃY ĐỌC CẢ HÀNG 440 Hz: RMS 0.198, to hơn khối tiếng nói thật, và VẪN ảo
# giác. Không một luật theo độ to nào chặn được nó. Cổng này KHÔNG chữa được
# ca đó và không được mô tả như thể có (xem `_has_speech`).
#
# ĐO ĐƯỢC VÀ ĐÃ LOẠI: `avg_logprob` của bốn ca trên là -0.108 / -0.135 (rất
# tự tin) và `compression_ratio` 0.88-0.94 (bình thường). Lọc theo độ tự tin
# của model KHÔNG bắt được lớp lỗi này — đừng quay lại ý đó.
#
# CÒN LẠI LÀ GÌ CHƯA ĐO: chưa có mẩu audio HỌP THẬT nào được gán nhãn "có
# tiếng nói / không có tiếng nói" để đối chiếu. Cụ thể là chưa biết nền phòng
# thật của người dùng thật nằm ở mức RMS nào — số 0.00599 ở trên là nhiễu
# Gauss tổng hợp, không phải một phòng họp. `MIN_VOICED_FRAMES` thì hoàn toàn
# là lập luận, chưa có phép đo nào chống lưng.
#
# NGUYÊN TẮC CHỌN, và nó lệch hẳn về MỘT phía: bỏ nhầm một mẩu CÓ tiếng nói
# sẽ âm thầm xoá tới 15 giây biên bản mà không ai biết — không có gì trong
# giao diện nói cho người dùng rằng đoạn đó từng tồn tại. Cho nhầm một mẩu IM
# LẶNG đi qua chỉ tốn một lời gọi ASR, và tệ nhất là một câu ảo giác mà
# `models/text_filter.py` còn cơ hội bắt lại — hai câu bịa đo được ở trên đều
# NẰM SẴN trong blocklist đó. Hai vế không cùng giá, nên mọi hằng số ở đây
# đều nghiêng về phía GIỮ.

# Khung 20 ms là kích thước khung tiêu chuẩn của VAD tiếng nói (WebRTC VAD,
# Silero đều dùng 10/20/30 ms): đủ dài để RMS ổn định, đủ ngắn để một âm tiết
# tiếng Việt (~100-150 ms) trải trên nhiều khung.
FRAME_MS = 20
FRAME_SAMPLES = SAMPLE_RATE * FRAME_MS // 1000      # 320

# RMS của MỘT KHUNG để khung đó được tính là "có tiếng". 0.01 ≈ -40 dBFS.
#
# ĐO TRÊN CHÍNH TỆP LÀM HỎNG VIỆC: tệp "nền phòng" RMS 0.00599 ở trên có
# khung to nhất chỉ 0.00693 — 0/750 khung vượt 0.01, nên nó bị chặn. Tệp
# nhiễu 0.00099 có khung to nhất 0.00112. Cả hai đều nằm gọn dưới ngưỡng.
#
# CƠ CHẾ, và đây mới là phần đáng hiểu: nhiễu băng rộng có phân bố RMS theo
# khung CỰC HẸP (đo được: 0.00537-0.00693 quanh trung bình 0.00599, tức
# ±15%), còn tiếng nói thì cực rộng vì năng lượng dồn vào các âm tiết. Nhờ
# vậy cùng một ngưỡng vừa chặn được nhiễu vừa cho lọt tín hiệu có nhịp âm
# tiết YẾU HƠN. Quét nhị phân trên tín hiệu tổng hợp cho khoảng cách đó:
# ở ngưỡng 0.01 cổng chặn được nhiễu băng rộng tới RMS 0.00896 và vẫn cho
# lọt tín hiệu nhịp-âm-tiết từ RMS 0.00618 trở lên — tức là ở CÙNG một mức
# to, tiếng nói được ưu ái hơn nhiễu 1.45 lần.
#
# TỈ SỐ 1.45 ĐÓ KHÔNG ĐỔI THEO NGƯỠNG (đã quét 0.008/0.01/0.012/0.015/0.02,
# ra đúng 1.45 ở cả năm). Nghĩa là chọn ngưỡng KHÔNG phải chọn "cổng tốt hơn"
# mà chỉ là trượt cả cửa sổ: cao lên thì chịu được phòng ồn hơn nhưng bỏ mất
# người nói nhỏ hơn. Vì vậy chọn theo ràng buộc cứng chứ không theo cảm giác:
# ngưỡng THẤP NHẤT còn chặn được tệp 0.00599 với biên thật. 0.01 cho biên
# 1.5 lần (chặn tới 0.00896); 0.012 cho 1.79 lần nhưng bắt đầu bỏ người nói
# nhỏ từ RMS 0.00742. Lấy 0.01 vì hai vế không cùng giá: nền phòng lọt qua
# đẻ ra một câu mà `text_filter` bắt được, tiếng nói bị bỏ thì mất hẳn.
#
# VÌ SAO KHÔNG LẤY THẲNG 0.0316 CỦA REPO THAM CHIẾU: con số đó
# (`np.mean(x**2) > 0.001`) là cổng năng lượng tính trên TOÀN đoạn, không
# phải trên từng khung — đem một ngưỡng "cả đoạn" áp cho "từng khung" sẽ chặt
# hơn nhiều lần so với ý định gốc của nó, và chính là vứt bỏ đúng cái khoảng
# cách 1.45 lần vừa nói.
VOICED_RMS = 0.01

# Số khung "có tiếng" tối thiểu trong cả mẩu. 5 khung = 100 ms.
#
# Repo tham chiếu đòi tối thiểu 300 ms cho một đoạn tiếng nói của Silero VAD.
# Ta lấy 100 ms, tức LỎNG HƠN BA LẦN, có chủ ý: đoạn của họ dùng để CẮT mẩu
# (bỏ nhầm chỉ làm mối nối xấu), còn con số này quyết định có XOÁ 15 giây
# biên bản hay không. Một âm tiết tiếng Việt ngắn nhất cũng khoảng 100-150 ms,
# nên dưới 100 ms năng lượng trong suốt 15 giây thì không thể là một từ —
# nhiều khả năng là tiếng gõ phím hay tiếng ghế kéo.
#
# CHƯA CÓ PHÉP ĐO NÀO CHỐNG LƯNG CHO SỐ 5. Khác với `VOICED_RMS`, nó không
# đến từ bản đo 05/08/2026 mà thuần tuý từ lập luận trên độ dài âm tiết. Bốn
# tệp đo được đều là tín hiệu ĐỀU (nhiễu hoặc tông kéo dài), nên chúng quyết
# định ở `VOICED_RMS` chứ không chạm tới hằng số này: cả 750 khung hoặc cùng
# vượt, hoặc cùng không.
MIN_VOICED_FRAMES = 5

# ------------------------------------------------------------------------- #
# Hằng số điều kiện hoá
# ------------------------------------------------------------------------- #
# High-pass 80 Hz: dưới ngưỡng này gần như không còn gì thuộc về tiếng nói
# (F0 giọng nam trầm nhất cũng ~85 Hz), chỉ còn ù điện 50 Hz, tiếng rung bàn
# và trôi DC. Cắt đi trước khi cân mức là quan trọng: nếu không, `speechnorm`
# sẽ đo cả phần năng lượng rác đó và cân mức theo nó.
HIGHPASS_HZ = 80

# `speechnorm` = cân mức theo từng đỉnh cục bộ, KHÔNG phải nén dải động.
# `e=3` giới hạn khuếch đại ở 3 lần (một mẩu rất nhỏ tiếng không bị kéo lên
# thành nhiễu to), `r=0.0001` cho mức thay đổi chậm nên không nghe thấy hiệu
# ứng "bơm", `l=1` khoá các kênh với nhau (vô hại với mono nhưng để nguyên
# thì cùng một chuỗi tham số dùng lại được nếu sau này có stereo).
#
# VÌ SAO LÀ `speechnorm` MÀ KHÔNG PHẢI `loudnorm`: `loudnorm` một lượt
# (single-pass) đo LUFS tích luỹ trên cả luồng và cần vài giây mới hội tụ —
# trên một mẩu 15 giây độc lập thì phần đầu mẩu bị chỉnh sai. Mà mỗi mẩu của
# ta ĐƯỢC GIẢI MÃ RIÊNG, nên lỗi đó lặp lại ở đầu MỌI mẩu.
SPEECHNORM_ARGS = 'e=3:r=0.0001:l=1'

# Ngưỡng để CẢNH BÁO (không phải để bỏ mẩu) khi độ dài giải mã được lệch so
# với `duration_ms` mà recorder khai báo. Có ý nghĩa vì `_write_segments` kẹp
# mọi mốc thời gian ASR vào `[0, duration_ms]`: nếu audio thật dài hơn hẳn
# con số khai báo thì phần đuôi bị dồn hết về một mốc. Bộ giải mã MP3 vẫn
# thêm/bớt vài chục ms đệm ở hai đầu khi luồng không có header LAME, nên
# ngưỡng phải rộng — đây là công cụ chẩn đoán, không phải ràng buộc.
DURATION_MISMATCH_MS = 200
DURATION_MISMATCH_RATIO = 0.10


class AudioPrepError(ValueError):
    """Không đọc được audio đầu vào.

    Chỉ dùng cho các bước KHÔNG có đường lùi (giải mã). Điều kiện hoá không
    bao giờ ném lỗi này — nó có đường lùi là tín hiệu chưa xử lý.
    """


class AidtMeetingAudioPrep(models.AbstractModel):
    _name = 'aidt.meeting.audio.prep'
    _description = 'Tiền xử lý audio trước khi bóc băng'

    # -------------------------------------------------------------------- #
    # API công khai
    # -------------------------------------------------------------------- #
    @api.model
    def _prepare(self, raw, duration_ms):
        """MP3 bytes -> (wav_bytes | None, lý_do | None).

        Trả `(None, lý_do)` khi mẩu KHÔNG đáng gửi đi bóc băng; trả
        `(wav_bytes, None)` khi đáng gửi.

        HÀM NÀY KHÔNG BAO GIỜ NÉM LỖI. Bên gọi (`meeting_chunk._process_one`)
        bọc mọi lỗi bằng `_mark_retry`, nên một byte hỏng thoát ra khỏi đây sẽ
        đốt cả ba lượt retry rồi kết thúc bằng `failed` — trong khi sự thật
        chỉ là "mẩu này không có gì để bóc băng". Một lý do trả về cho bên gọi
        ghi lại đúng sự thật đó và đóng mẩu ngay ở lượt đầu.

        THỨ TỰ CÁC BƯỚC KHÔNG ĐƯỢC ĐỔI: cổng lọc chạy TRƯỚC điều kiện hoá.
        `speechnorm` khuếch đại tới 3 lần, nên chạy nó trước sẽ kéo nền phòng
        im lặng vượt lên trên ngưỡng và vô hiệu hoá đúng cái cổng mà nó đi
        qua. Cổng phải đo tín hiệu như micro thật sự nghe thấy.
        """
        try:
            samples = self._decode(raw)
        except AudioPrepError as exc:
            return None, str(exc)
        except Exception as exc:                     # noqa: BLE001
            # PyAV gói lỗi của libav thành khá nhiều lớp ngoại lệ khác nhau
            # (InvalidDataError, ValueError, OSError, MemoryError…) và danh
            # sách đó thay đổi giữa các bản. Bắt rộng ở ĐÚNG một chỗ này là
            # cách duy nhất giữ được lời hứa "không bao giờ ném lỗi" ở trên
            # mà không phải đuổi theo từng phiên bản PyAV.
            _logger.exception('Giải mã audio thất bại ngoài dự kiến')
            return None, f'giải mã audio thất bại: {exc}'

        self._warn_if_duration_mismatch(samples, duration_ms)

        ok, reason = self._has_speech(samples)
        if not ok:
            return None, reason

        return self._encode_wav(self._condition(samples)), None

    # -------------------------------------------------------------------- #
    # Giải mã
    # -------------------------------------------------------------------- #
    @api.model
    def _decode(self, raw):
        """MP3 bytes -> np.float32 mono 16 kHz, giá trị trong [-1, 1).

        Ném `AudioPrepError` khi không đọc được; `_prepare` là nơi đổi nó
        thành lý do. Tách riêng để test gọi được một mình.

        Chuỗi `s16` -> chia 32768 chứ không lấy thẳng `flt` từ bộ lấy mẫu:
        `flt` cũng chạy được, nhưng `s16` là ĐÚNG thứ sẽ nằm trong tệp WAV ở
        cuối đường ống, nên làm tròn ở đây một lần thì phần tính RMS của cổng
        lọc đo trên đúng những con số mà ASR sẽ nhận. Đo trên một tín hiệu
        rồi gửi đi một tín hiệu khác là cách êm ái nhất để hai bên lệch nhau.
        """
        if not raw:
            raise AudioPrepError('không có dữ liệu audio (0 byte)')
        blocks = []
        try:
            with av.open(io.BytesIO(raw)) as container:
                if not container.streams.audio:
                    raise AudioPrepError('tệp không có luồng audio nào')
                resampler = av.audio.resampler.AudioResampler(
                    format='s16', layout='mono', rate=SAMPLE_RATE)
                for frame in container.decode(audio=0):
                    for out in resampler.resample(frame):
                        blocks.append(out.to_ndarray().reshape(-1))
                # Xả bộ lấy mẫu: nó giữ lại phần đuôi chưa đủ một khung nội
                # bộ. Bỏ bước này là mất vài chục ms cuối MỖI mẩu — vừa đúng
                # chỗ mà phần chồng lấn 1.5 giây sinh ra để bảo vệ.
                for out in resampler.resample(None):
                    blocks.append(out.to_ndarray().reshape(-1))
        except av.error.FFmpegError as exc:
            raise AudioPrepError(f'không giải mã được audio: {exc}') from exc
        if not blocks:
            raise AudioPrepError('giải mã ra 0 mẫu audio')
        return np.concatenate(blocks).astype(np.float32) / 32768.0

    @api.model
    def _warn_if_duration_mismatch(self, samples, duration_ms):
        """Ghi log khi độ dài thật lệch xa `duration_ms` recorder khai báo.

        CHỈ cảnh báo, tuyệt đối không bỏ mẩu. `duration_ms` do trình duyệt đo
        bằng `performance.now()`, còn độ dài này do bộ giải mã đếm mẫu — hai
        cách đo khác nhau thì lệch chút là bình thường. Nhưng lệch NHIỀU thì
        mọi mốc thời gian của mẩu này đều sai, vì `_write_segments` kẹp mốc
        ASR vào `[0, duration_ms]`, và đó là thứ đáng để lại dấu vết trong log
        chứ không phải thứ nên tự đoán rồi tự sửa.
        """
        if not duration_ms or duration_ms <= 0:
            return
        decoded_ms = round(len(samples) * 1000 / SAMPLE_RATE)
        gap = abs(decoded_ms - duration_ms)
        if gap > max(DURATION_MISMATCH_MS,
                     duration_ms * DURATION_MISMATCH_RATIO):
            _logger.warning(
                'Độ dài audio giải mã được (%s ms) lệch %s ms so với '
                'duration_ms recorder khai báo (%s ms); mốc thời gian của '
                'mẩu này sẽ bị kẹp theo con số khai báo.',
                decoded_ms, gap, duration_ms)

    # -------------------------------------------------------------------- #
    # Cổng lọc tiếng nói
    # -------------------------------------------------------------------- #
    @api.model
    def _frame_rms(self, samples):
        """RMS của từng khung 20 ms. Phần đuôi thiếu khung bị bỏ.

        Tính ở `float64`: `np.mean` trên `float32` cộng dồn 320 số bình
        phương cỡ 1e-8 và mất chữ số có nghĩa đúng ở vùng biên độ nhỏ — tức
        là đúng vùng mà quyết định "im lặng hay không" được đưa ra.
        """
        count = len(samples) // FRAME_SAMPLES
        if count == 0:
            return np.zeros(0, dtype=np.float64)
        block = samples[:count * FRAME_SAMPLES].astype(np.float64)
        return np.sqrt(np.mean(block.reshape(count, FRAME_SAMPLES) ** 2,
                               axis=1))

    @api.model
    def _has_speech(self, samples):
        """np.ndarray -> (bool, lý_do | None).

        CỔNG NÀY CHẶN AUDIO GẦN RỖNG, KHÔNG CHẶN "NỘI DUNG SUY BIẾN NHƯNG TO".
        Nói rõ ra vì rất dễ đọc nhầm nó thành "bộ lọc ảo giác":

          * Bắt được, và đã đo: im lặng số, nhiễu nhỏ, nền phòng ở RMS
            0.00599 — cả ba đều làm `openai/whisper-large-v3` bịa ra một câu
            hoàn chỉnh, và hàng 0.00599 hôm nay còn đi lọt cổng độ to của
            trình duyệt. Bỏ hẳn lời gọi ASR là cách chặt nhất để diệt lớp lỗi
            này: không có đầu ra thì không có gì phải lọc.
          * KHÔNG bắt được, và cũng đã đo: tông 440 Hz ở RMS 0.19797 vẫn trả
            về "Hãy subscribe cho kênh La La School…". Mọi khung của nó đều
            vượt ngưỡng — tín hiệu đều thì 750/750 khung "có tiếng" — nên
            cổng cho qua, và ĐÚNG như vậy: một luật theo độ to không có cách
            nào biết nội dung đó suy biến. Lưới thứ hai cho ca này là
            blocklist ở `models/text_filter.py`; hai câu bịa đo được đều nằm
            sẵn trong đó. Cố nhét thêm phần dò phổ (spectral flatness) vào
            đây là đi ra ngoài phạm vi và làm cổng khó hiểu đi.
          * Cũng KHÔNG dùng được: lọc theo độ tự tin của model. Đo cùng đợt,
            bốn ca ảo giác cho `avg_logprob` -0.108 / -0.135 và
            `compression_ratio` 0.88-0.94 — model tự tin y như khi nó bóc
            băng đúng.

        Lý do trả về PHẢI có số đo. Người đọc lý do này là người đang tự hỏi
        "vì sao 15 giây của tôi biến mất" và họ cần biết mẩu đó im tới mức
        nào để phân biệt "micro tắt" với "ngưỡng đặt sai".
        """
        rms = self._frame_rms(samples)
        total = len(rms)
        voiced = int((rms > VOICED_RMS).sum())
        if voiced >= MIN_VOICED_FRAMES:
            return True, None
        peak = float(rms.max()) if total else 0.0
        whole = float(np.sqrt(np.mean(samples.astype(np.float64) ** 2))) \
            if len(samples) else 0.0
        return False, (
            f'không phát hiện tiếng nói: {voiced}/{total} khung {FRAME_MS} ms '
            f'vượt RMS {VOICED_RMS} (cần tối thiểu {MIN_VOICED_FRAMES}); '
            f'RMS đỉnh khung {peak:.5f}, RMS cả mẩu {whole:.5f}'
        )

    # -------------------------------------------------------------------- #
    # Điều kiện hoá
    # -------------------------------------------------------------------- #
    @api.model
    def _condition(self, samples):
        """np.ndarray -> np.ndarray CÙNG SỐ MẪU. Không bao giờ ném lỗi.

        Điều kiện hoá là phần THÊM VÀO. Nếu dựng đồ thị filter hỏng (bản
        ffmpeg trong ảnh thiếu `speechnorm`, tham số đổi nghĩa giữa các bản…)
        thì tín hiệu chưa xử lý vẫn bóc băng được hoàn toàn bình thường —
        chất lượng thấp hơn một chút chứ không mất mẩu. Để một lỗi ở đây làm
        hỏng cả mẩu là đổi một cải tiến lấy một sự cố.

        CỐ Ý KHÔNG CÓ Ở ĐÂY, và đừng thêm vào "cho chắc":
          * KHỬ NHIỄU (`afftdn`/`arnndn`) — audio tới từ một track mic WebRTC
            đã qua noise-suppression và AGC của trình duyệt. Chồng bộ khử
            nhiễu thứ hai lên tiếng nói đã bị xử lý là cách làm nó nghe méo
            thêm, không phải sạch thêm. Repo tham chiếu cũng không khử nhiễu.
          * CẮT KHOẢNG LẶNG (`silenceremove`) — xem `_encode_wav`: đổi độ dài
            là làm hỏng mọi mốc thời gian của cuộc họp.
        """
        if not len(samples):
            return samples
        try:
            graph = self._build_graph()
            frame = av.AudioFrame.from_ndarray(
                np.ascontiguousarray(samples.reshape(1, -1),
                                     dtype=np.float32),
                format='flt', layout='mono')
            frame.rate = SAMPLE_RATE
            frame.pts = 0
            frame.time_base = fractions.Fraction(1, SAMPLE_RATE)
            graph.push(frame)
            # Đẩy None để báo hết luồng: các filter IIR còn giữ đuôi trong bộ
            # đệm, không xả thì mẩu ngắn đi.
            graph.push(None)
            blocks = []
            while True:
                try:
                    blocks.append(graph.pull().to_ndarray().reshape(-1))
                except (BlockingIOError, EOFError):
                    break
            out = np.concatenate(blocks) if blocks else samples
        except Exception as exc:                     # noqa: BLE001
            _logger.warning(
                'Điều kiện hoá audio thất bại (%s); gửi tín hiệu chưa xử lý '
                'đi bóc băng.', exc)
            return samples
        if len(out) != len(samples):
            # Đường này lẽ ra không bao giờ chạy: cả `highpass` lẫn
            # `speechnorm` đều là filter một-vào-một-ra. Nhưng nếu một bản
            # ffmpeg nào đó làm khác, hậu quả là mốc thời gian sai lệch âm
            # thầm trên toàn bộ biên bản — đắt hơn nhiều so với việc mất phần
            # điều kiện hoá. Nên: phát hiện thì lùi về tín hiệu gốc.
            _logger.warning(
                'Điều kiện hoá làm đổi số mẫu (%s -> %s); lùi về tín hiệu '
                'chưa xử lý để giữ nguyên độ dài.', len(samples), len(out))
            return samples
        return out.astype(np.float32)

    @api.model
    def _build_graph(self):
        """Đồ thị filter: nguồn -> highpass -> speechnorm -> aformat -> đích.

        `aformat` ở cuối là bắt buộc chứ không phải trang trí: `speechnorm`
        có thể tự chọn một định dạng mẫu khác ở đầu ra, và khi đó
        `to_ndarray()` trả về kiểu dữ liệu khác `float32` mà phần còn lại của
        module đang giả định.
        """
        graph = av.filter.Graph()
        source = graph.add_abuffer(
            format='flt', layout='mono', sample_rate=SAMPLE_RATE,
            time_base=fractions.Fraction(1, SAMPLE_RATE))
        highpass = graph.add('highpass', f'f={HIGHPASS_HZ}')
        speechnorm = graph.add('speechnorm', SPEECHNORM_ARGS)
        aformat = graph.add(
            'aformat',
            f'sample_fmts=flt:channel_layouts=mono:sample_rates={SAMPLE_RATE}')
        sink = graph.add('abuffersink')
        graph.link_nodes(source, highpass, speechnorm, aformat, sink)
        graph.configure()
        return graph

    # -------------------------------------------------------------------- #
    # Mã hoá
    # -------------------------------------------------------------------- #
    @api.model
    def _encode_wav(self, samples):
        """np.ndarray -> WAV `pcm_s16le` 16 kHz mono, kèm header RIFF.

        ĐỘ DÀI PHẢI ĐƯỢC BẢO TOÀN TỪ ĐẦU ĐẾN CUỐI ĐƯỜNG ỐNG. Không cắt
        khoảng lặng, không xén hai đầu, không đổi tốc độ. `_write_segments`
        ánh xạ mốc ASR (tương đối trong mẩu) lên `offset_ms`/`duration_ms` do
        recorder đo; rút ngắn audio đi 2 giây không làm ASR trả mốc nhỏ đi 2
        giây theo — nó chỉ làm MỌI câu trong mẩu bị đặt sai chỗ, và sai một
        cách trông vẫn hợp lệ. Đây là lý do repo tham chiếu cũng GIỮ khoảng
        lặng và chỉ dùng VAD để chọn ĐIỂM CẮT.

        Tự ghép header thay vì dùng muxer `wav` của PyAV: đầu vào đã là PCM
        sẵn nên đi qua một encoder + muxer chỉ để ghi 44 byte cố định là thêm
        một tầng có thể hỏng (và ffmpeg còn chèn thêm chunk `LIST` mà không
        phải bộ giải mã nào cũng bỏ qua êm). 44 byte này là toàn bộ chuẩn
        RIFF/WAVE cho PCM không nén.
        """
        # Kẹp trước khi nhân: `+1.0` không biểu diễn được bằng int16 nên nếu
        # `speechnorm` đẩy một mẫu chạm trần, phép nhân sẽ tràn và một đỉnh
        # dương biến thành một đỉnh ÂM — nghe thành tiếng "tách" giòn, đúng
        # kiểu tạo tác làm ASR bịa chữ.
        clipped = np.clip(samples.astype(np.float32), -1.0, 32767 / 32768)
        pcm = (clipped * 32768.0).astype('<i2').tobytes()
        header = (
            b'RIFF' + struct.pack('<I', 36 + len(pcm)) + b'WAVE'
            + b'fmt ' + struct.pack(
                '<IHHIIHH',
                16,                 # cỡ khối fmt cho PCM
                1,                  # WAVE_FORMAT_PCM
                1,                  # số kênh
                SAMPLE_RATE,
                SAMPLE_RATE * 2,    # byte/giây = rate * kênh * 2 byte
                2,                  # block align
                16,                 # bit/mẫu
            )
            + b'data' + struct.pack('<I', len(pcm))
        )
        return header + pcm
