import io
import struct
from unittest.mock import patch

import av
import numpy as np
import soundfile as sf

from odoo.tests.common import TransactionCase
from odoo.tests import tagged
from odoo.tools import mute_logger

from odoo.addons.aidt_meeting_minutes.models.audio_prep import (
    AudioPrepError, FRAME_SAMPLES, MIN_VOICED_FRAMES, SAMPLE_RATE, VOICED_RMS,
)

_LOG = 'odoo.addons.aidt_meeting_minutes.models.audio_prep'


def _mp3(samples, rate=SAMPLE_RATE, bit_rate=32000):
    """Đóng gói mảng float32 thành MP3 mono giống hệt cái lamejs gửi lên.

    Sinh audio TRONG test chứ không nhét tệp nhị phân vào repo: một fixture
    .mp3 không nói được nó chứa gì, không sửa được khi ngưỡng đổi, và không ai
    review được nội dung của nó.
    """
    buf = io.BytesIO()
    container = av.open(buf, mode='w', format='mp3')
    stream = container.add_stream('mp3', rate=rate)
    stream.bit_rate = bit_rate
    frame = av.AudioFrame.from_ndarray(
        (np.clip(samples, -1.0, 32767 / 32768) * 32768.0).astype('<i2')
        .reshape(1, -1),
        format='s16', layout='mono')
    frame.rate = rate
    frame.pts = 0
    for packet in stream.encode(frame):
        container.mux(packet)
    for packet in stream.encode(None):
        container.mux(packet)
    container.close()
    return buf.getvalue()


def _t(seconds, rate=SAMPLE_RATE):
    return np.arange(int(rate * seconds), dtype=np.float64) / rate


def _tone(seconds, freq=440.0, amp=0.3):
    return (amp * np.sin(2 * np.pi * freq * _t(seconds))).astype(np.float32)


def _silence(seconds):
    return np.zeros(int(SAMPLE_RATE * seconds), dtype=np.float32)


def _noise(seconds, amp=0.05, seed=0):
    rng = np.random.default_rng(seed)
    return (rng.standard_normal(int(SAMPLE_RATE * seconds))
            * amp).astype(np.float32)


def _noise_at_rms(seconds, rms, seed=0):
    """Nhiễu Gauss ĐÚNG một mức RMS cho trước.

    `_noise` đặt độ lệch chuẩn chứ không đặt RMS, nên mức thật lệch vài phần
    trăm theo seed. Các ca hiệu chỉnh dưới đây so với một con số ĐO ĐƯỢC
    (0.00599) nên phải chuẩn hoá đúng mức, không được xê dịch theo seed.
    """
    x = np.random.default_rng(seed).standard_normal(int(SAMPLE_RATE * seconds))
    return (x / np.sqrt(np.mean(x ** 2)) * rms).astype(np.float32)


def _speechlike(seconds, amp=0.25, syllable_hz=4.0, f0=180.0):
    """Sóng mang F0 giọng người, bọc biên độ ~4 âm tiết/giây.

    Không phải tiếng nói thật, và test nào dựa vào nó KHÔNG chứng minh được
    cổng lọc chạy đúng trên giọng người — nó chỉ chứng minh cổng phân biệt
    được "có bao bọc năng lượng nhịp âm tiết" với "im lặng".
    """
    t = _t(seconds)
    envelope = 0.5 + 0.5 * np.sin(2 * np.pi * syllable_hz * t)
    return (amp * envelope * np.sin(2 * np.pi * f0 * t)).astype(np.float32)


def _speechlike_at_rms(seconds, rms, **kwargs):
    """`_speechlike` chuẩn hoá về đúng một mức RMS, để so trực tiếp với nhiễu.

    `amp` của `_speechlike` là hệ số ĐỈNH, không phải RMS (bao biên độ kéo
    RMS xuống ~0.43 lần), nên so một `amp` với một mức nhiễu là so nhầm đơn
    vị — đúng kiểu nhầm làm một phép hiệu chỉnh trông như đã chứng minh điều
    nó không chứng minh.
    """
    x = _speechlike(seconds, **kwargs).astype(np.float64)
    return (x / np.sqrt(np.mean(x ** 2)) * rms).astype(np.float32)


@tagged('post_install', '-at_install')
class TestAudioPrep(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.prep = cls.env['aidt.meeting.audio.prep']

    # ------------------------------------------------------------------ #
    # Giải mã
    # ------------------------------------------------------------------ #
    def test_giai_ma_ra_float32_mono_16k(self):
        samples = self.prep._decode(_mp3(_tone(2.0)))
        self.assertEqual(samples.dtype, np.float32)
        self.assertEqual(samples.ndim, 1)
        self.assertTrue(np.all(np.abs(samples) <= 1.0))

    def test_giai_ma_giu_nguyen_do_dai(self):
        """Ràng buộc CỨNG của cả module. `_write_segments` ánh xạ mốc ASR lên
        `offset_ms`/`duration_ms`, nên độ dài đổi là mọi mốc thời gian của
        cuộc họp sai. Dung sai 100 ms cho phần đệm mà bộ mã hoá MP3 thêm vào
        hai đầu khung."""
        for seconds in (2.0, 15.0):
            with self.subTest(seconds=seconds):
                samples = self.prep._decode(_mp3(_tone(seconds)))
                decoded_ms = len(samples) * 1000 / SAMPLE_RATE
                self.assertAlmostEqual(decoded_ms, seconds * 1000, delta=100)

    def test_giai_ma_lay_mau_lai_ve_16k(self):
        """Đầu vào thật là 16 kHz, nhưng cấu hình recorder có thể đổi và
        Whisper thì luôn hạ về 16 kHz ở bên trong. Lấy mẫu lại ở đây để ta
        biết chắc model nghe thấy gì."""
        # Tông phải được SINH ở 48 kHz, không phải sinh ở 16 kHz rồi khai
        # nhầm nhịp lấy mẫu — khai nhầm chỉ tạo ra một tệp dài 2/3 giây và
        # test sẽ đo nhầm thứ khác.
        tone_48k = (0.3 * np.sin(2 * np.pi * 440 * _t(2.0, rate=48000))
                    ).astype(np.float32)
        samples = self.prep._decode(_mp3(tone_48k, rate=48000, bit_rate=64000))
        self.assertAlmostEqual(len(samples) / SAMPLE_RATE, 2.0, delta=0.15)

    def test_rac_thi_nem_audio_prep_error_chu_khong_lo_ra_loi_pyav(self):
        with self.assertRaises(AudioPrepError):
            self.prep._decode(b'day khong phai la audio' * 100)

    def test_rong_thi_nem_audio_prep_error(self):
        with self.assertRaises(AudioPrepError):
            self.prep._decode(b'')

    # ------------------------------------------------------------------ #
    # Cổng lọc tiếng nói
    # ------------------------------------------------------------------ #
    def test_im_lang_tuyet_doi_bi_chan(self):
        ok, reason = self.prep._has_speech(_silence(15.0))
        self.assertFalse(ok)
        self.assertIn('không phát hiện tiếng nói', reason)

    def test_nen_phong_rat_nho_bi_chan(self):
        """Nhiễu Gauss RMS 0.00100. Đo 05/08/2026 trên
        `openai/whisper-large-v3`: tệp này trả về "Cảm ơn các bạn đã theo dõi
        và hẹn gặp lại." — một câu KHÔNG AI NÓI."""
        ok, reason = self.prep._has_speech(_noise_at_rms(15.0, 0.00100))
        self.assertFalse(ok)
        self.assertIn('RMS đỉnh khung', reason)

    def test_nen_phong_0_006_bi_chan_day_la_ca_quyet_dinh(self):
        """CA QUYẾT ĐỊNH CỦA CẢ CỔNG LỌC, đừng nới ngưỡng làm hỏng test này.

        Nhiễu Gauss RMS 0.00599 VƯỢT `RMS_FLOOR = 0.005` của
        `static/src/recorder_service.js`, nên hôm nay nó lên tới ASR thật —
        và đo 05/08/2026 trên `openai/whisper-large-v3` nó trả về "Cảm ơn các
        bạn đã theo dõi và hẹn gặp lại.". Đây chính xác là lỗ hổng mà cổng
        này sinh ra để bịt. Khung to nhất của tệp đó đo được 0.00693, dưới
        `VOICED_RMS` 1.44 lần."""
        signal = _noise_at_rms(15.0, 0.00599)
        self.assertLess(float(self.prep._frame_rms(signal).max()), VOICED_RMS)
        ok, reason = self.prep._has_speech(signal)
        self.assertFalse(ok)
        self.assertIn('0/750', reason)

    def test_tong_440hz_to_VAN_qua_cong_gioi_han_da_biet(self):
        """GHIM MỘT GIỚI HẠN ĐÃ BIẾT, không phải mô tả một hành vi mong muốn.

        Tông 440 Hz ở RMS 0.19797 cũng làm `openai/whisper-large-v3` bịa ra
        "Hãy subscribe cho kênh La La School…" (đo 05/08/2026), nhưng mọi
        khung của nó đều vượt ngưỡng nên cổng CHO QUA. Không có luật theo độ
        to nào chặn được ca này: nó to hơn khối tiếng nói thật. Lưới thứ hai
        là blocklist ở `models/text_filter.py`. Test này tồn tại để người đọc
        sau không tưởng cổng lọc là bộ lọc ảo giác đầy đủ."""
        ok, _ = self.prep._has_speech(_tone(15.0, freq=440.0, amp=0.28))
        self.assertTrue(ok)

    def test_ly_do_bi_chan_co_du_so_de_chan_doan(self):
        """Người đọc lý do này đang hỏi 'vì sao 15 giây của tôi biến mất'.
        Một câu 'không có tiếng nói' trơ trọi không phân biệt được 'micro
        tắt' với 'ngưỡng đặt sai'."""
        _, reason = self.prep._has_speech(_silence(15.0))
        self.assertIn(str(MIN_VOICED_FRAMES), reason)
        self.assertIn(str(VOICED_RMS), reason)
        self.assertIn('750', reason)          # 15 s / 20 ms = 750 khung
        self.assertIn('RMS cả mẩu', reason)

    def test_tong_don_to_qua_duoc_cong(self):
        ok, reason = self.prep._has_speech(_tone(15.0, amp=0.3))
        self.assertTrue(ok)
        self.assertIsNone(reason)

    def test_tin_hieu_giong_tieng_noi_qua_duoc_cong(self):
        ok, _ = self.prep._has_speech(_speechlike(15.0))
        self.assertTrue(ok)

    def test_tieng_noi_rat_nho_van_qua_duoc_cong(self):
        """Nghiêng về phía GIỮ, có chủ ý. Biên độ 0.02 cho RMS cả mẩu 0.0087
        — DƯỚI ngưỡng năng lượng 0.0316 của repo tham chiếu, nghĩa là cổng
        của họ sẽ bỏ mẩu này. Ta không bỏ: bỏ nhầm thì 15 giây biên bản biến
        mất không dấu vết, cho qua nhầm chỉ tốn một lời gọi ASR."""
        ok, _ = self.prep._has_speech(_speechlike(15.0, amp=0.02))
        self.assertTrue(ok)

    def test_mot_tieng_go_ngan_giua_im_lang_van_qua_duoc_cong(self):
        """150 ms năng lượng trong 15 giây im lặng vẫn qua. Đây là giá phải
        trả có ý thức cho việc nghiêng về phía giữ: đúng bằng độ dài một âm
        tiết tiếng Việt, nên không phân biệt được với một từ bị nói lỡ."""
        x = _silence(15.0)
        burst = _tone(0.15, freq=200.0, amp=0.2)
        x[SAMPLE_RATE:SAMPLE_RATE + len(burst)] = burst
        ok, _ = self.prep._has_speech(x)
        self.assertTrue(ok)

    def test_cong_uu_ai_tieng_noi_hon_nhieu_o_cung_mot_do_to(self):
        """Ghim con số 1.45 lần mà bình luận ở `VOICED_RMS` viện dẫn.

        Đây là toàn bộ lý do cổng theo KHUNG hơn cổng theo cả mẩu: ở cùng một
        mức RMS, nhiễu băng rộng trải đều trên mọi khung nên không khung nào
        vượt ngưỡng, còn tín hiệu có nhịp âm tiết dồn năng lượng vào các đỉnh
        nên vẫn có khung vượt. Nếu ai đó thay cách tính RMS và làm mất khoảng
        cách này, cổng lọc sẽ chỉ còn là cổng độ to — test này phải đỏ."""
        ok, _ = self.prep._has_speech(_noise_at_rms(15.0, 0.0089))
        self.assertFalse(ok, 'nhiễu băng rộng RMS 0.0089 phải bị chặn')
        ok, _ = self.prep._has_speech(_speechlike_at_rms(15.0, 0.0065))
        self.assertTrue(
            ok, 'tín hiệu nhịp âm tiết CÒN NHỎ HƠN vẫn phải được giữ')

    def test_qua_ngan_de_chua_du_khung_thi_bi_chan(self):
        ok, reason = self.prep._has_speech(_tone(0.05, amp=0.3))
        self.assertFalse(ok)
        self.assertIn('không phát hiện tiếng nói', reason)

    def test_mang_rong_khong_lam_no_cong(self):
        ok, reason = self.prep._has_speech(np.zeros(0, dtype=np.float32))
        self.assertFalse(ok)
        self.assertIn('0/0', reason)

    def test_frame_rms_chia_dung_khung_20ms(self):
        rms = self.prep._frame_rms(_tone(1.0, amp=0.5))
        self.assertEqual(len(rms), SAMPLE_RATE // FRAME_SAMPLES)
        # RMS của sin biên độ 0.5 là 0.5/sqrt(2).
        self.assertAlmostEqual(float(rms.mean()), 0.5 / np.sqrt(2), places=2)

    # ------------------------------------------------------------------ #
    # Điều kiện hoá
    # ------------------------------------------------------------------ #
    def test_dieu_kien_hoa_giu_nguyen_so_mau(self):
        """Cùng ràng buộc cứng với giải mã, nhưng ở đây dễ vi phạm hơn nhiều
        — chỉ cần một filter có độ trễ nhóm hoặc quên xả bộ đệm."""
        for signal in (_tone(15.0), _speechlike(15.0), _noise(15.0)):
            with self.subTest(rms=float(np.sqrt(np.mean(signal ** 2)))):
                out = self.prep._condition(signal)
                self.assertEqual(len(out), len(signal))
                self.assertEqual(out.dtype, np.float32)

    def test_dieu_kien_hoa_can_muc_len_chu_khong_lam_vo_tieng(self):
        quiet = _speechlike(5.0, amp=0.05)
        out = self.prep._condition(quiet)
        self.assertGreater(float(np.sqrt(np.mean(out.astype(np.float64) ** 2))),
                           float(np.sqrt(np.mean(quiet.astype(np.float64) ** 2))))
        self.assertLessEqual(float(np.abs(out).max()), 1.0)

    def test_dieu_kien_hoa_cat_thanh_phan_duoi_80hz(self):
        """High-pass phải thật sự làm gì đó: một tông 20 Hz (trôi DC / rung
        bàn) phải yếu đi rõ rệt, còn 300 Hz (vùng tiếng nói) thì không."""
        low = self.prep._condition(_tone(2.0, freq=20.0, amp=0.3))
        mid = self.prep._condition(_tone(2.0, freq=300.0, amp=0.3))
        low_rms = float(np.sqrt(np.mean(low[SAMPLE_RATE:].astype(np.float64) ** 2)))
        mid_rms = float(np.sqrt(np.mean(mid[SAMPLE_RATE:].astype(np.float64) ** 2)))
        self.assertLess(low_rms, mid_rms / 4)

    def test_dieu_kien_hoa_hong_thi_lui_ve_tin_hieu_goc(self):
        """Điều kiện hoá là phần THÊM VÀO. Không bao giờ được là lý do một
        mẩu thất bại — chất lượng thấp hơn còn hơn mất 15 giây biên bản."""
        signal = _speechlike(2.0)
        with mute_logger(_LOG):
            with patch.object(type(self.prep), '_build_graph',
                              side_effect=RuntimeError('graph hỏng')):
                out = self.prep._condition(signal)
        np.testing.assert_array_equal(out, signal)

    def test_dieu_kien_hoa_mang_rong_khong_no(self):
        out = self.prep._condition(np.zeros(0, dtype=np.float32))
        self.assertEqual(len(out), 0)

    # ------------------------------------------------------------------ #
    # Mã hoá WAV
    # ------------------------------------------------------------------ #
    def test_wav_doc_lai_duoc_bang_soundfile_dung_16k_mono(self):
        signal = _tone(1.0, amp=0.5)
        data, rate = sf.read(io.BytesIO(self.prep._encode_wav(signal)),
                             dtype='float32')
        self.assertEqual(rate, SAMPLE_RATE)
        self.assertEqual(data.ndim, 1)
        self.assertEqual(len(data), len(signal))
        # Sai số lượng tử hoá 16 bit là 1/32768.
        np.testing.assert_allclose(data, signal, atol=2 / 32768)

    def test_wav_doc_lai_duoc_bang_pyav_dung_pcm_s16le(self):
        raw = self.prep._encode_wav(_tone(0.5))
        with av.open(io.BytesIO(raw)) as container:
            stream = container.streams.audio[0]
            self.assertEqual(stream.codec_context.name, 'pcm_s16le')
            self.assertEqual(stream.rate, SAMPLE_RATE)
            self.assertEqual(stream.codec_context.layout.nb_channels, 1)

    def test_header_riff_dung_kich_thuoc(self):
        """Kích thước sai trong header là kiểu hỏng mà nhiều bộ giải mã vẫn
        đọc được nhưng một số dịch vụ ASR thì từ chối — phải kiểm bằng số
        chứ không chỉ bằng 'đọc lại được'."""
        raw = self.prep._encode_wav(_tone(1.0))
        self.assertEqual(raw[:4], b'RIFF')
        self.assertEqual(raw[8:12], b'WAVE')
        self.assertEqual(struct.unpack('<I', raw[4:8])[0], len(raw) - 8)
        self.assertEqual(struct.unpack('<I', raw[40:44])[0], len(raw) - 44)
        self.assertEqual(len(raw), 44 + SAMPLE_RATE * 2)

    def test_wav_kep_bien_khong_de_tran_int16(self):
        """+1.0 không biểu diễn được bằng int16; nhân thẳng thì một đỉnh
        dương lật thành đỉnh ÂM — nghe thành tiếng 'tách', đúng kiểu tạo tác
        làm Whisper bịa chữ."""
        raw = self.prep._encode_wav(np.array([1.0, 1.5, -1.0, -2.0],
                                             dtype=np.float32))
        pcm = np.frombuffer(raw[44:], dtype='<i2')
        np.testing.assert_array_equal(pcm, [32767, 32767, -32768, -32768])

    # ------------------------------------------------------------------ #
    # `_prepare` đầu-cuối
    # ------------------------------------------------------------------ #
    def test_prepare_tra_wav_cho_mau_co_tieng(self):
        raw = _mp3(_speechlike(15.0))
        wav, reason = self.prep._prepare(raw, 15000)
        self.assertIsNone(reason)
        self.assertEqual(wav[:4], b'RIFF')
        data, rate = sf.read(io.BytesIO(wav), dtype='float32')
        self.assertEqual(rate, SAMPLE_RATE)
        # Toàn bộ đường ống giữ độ dài: cùng dung sai với test giải mã.
        self.assertAlmostEqual(len(data) * 1000 / SAMPLE_RATE, 15000, delta=100)

    def test_prepare_bo_mau_im_lang_va_khong_goi_asr(self):
        """Diệt cả lớp lỗi ảo-giác-trên-khoảng-lặng ngay từ gốc thay vì lọc
        đầu ra của nó. `openai/whisper-large-v3` ảo giác trên khoảng lặng
        NHIỀU HƠN v2, nên cổng này không phải phần thêm thắt."""
        # MP3 32 kbps trên khoảng lặng tuyệt đối vẫn ra nhiễu lượng tử hoá
        # rất nhỏ — đúng ca thật, không phải mảng zero lý tưởng.
        wav, reason = self.prep._prepare(_mp3(_silence(15.0)), 15000)
        self.assertIsNone(wav)
        self.assertIn('không phát hiện tiếng nói', reason)

    def test_prepare_khong_nem_loi_voi_byte_rac(self):
        """`_process_one` bọc mọi lỗi bằng `_mark_retry`, nên một ngoại lệ
        thoát ra khỏi đây sẽ đốt cả ba lượt retry rồi kết thúc bằng 'failed'
        — trong khi sự thật chỉ là 'mẩu này không đọc được'."""
        wav, reason = self.prep._prepare(b'\x00\x01\x02rac rac rac' * 50, 15000)
        self.assertIsNone(wav)
        self.assertTrue(reason)

    def test_prepare_khong_nem_loi_voi_byte_rong(self):
        wav, reason = self.prep._prepare(b'', 15000)
        self.assertIsNone(wav)
        self.assertIn('0 byte', reason)

    def test_prepare_khong_nem_loi_khi_pyav_no_kieu_khac(self):
        """Danh sách ngoại lệ PyAV ném ra đổi giữa các bản. Lời hứa 'không
        bao giờ ném lỗi' phải đúng cả với ngoại lệ ngoài họ FFmpegError."""
        with mute_logger(_LOG):
            with patch.object(type(self.prep), '_decode',
                              side_effect=MemoryError('hết bộ nhớ')):
                wav, reason = self.prep._prepare(_mp3(_tone(1.0)), 1000)
        self.assertIsNone(wav)
        self.assertIn('hết bộ nhớ', reason)

    def test_prepare_canh_bao_khi_do_dai_lech_xa_duration_ms(self):
        """Chỉ CẢNH BÁO, không bỏ mẩu: `duration_ms` do trình duyệt đo còn độ
        dài này do bộ giải mã đếm mẫu, và mẩu vẫn phải được bóc băng."""
        raw = _mp3(_speechlike(15.0))
        with self.assertLogs(_LOG, level='WARNING') as logs:
            wav, reason = self.prep._prepare(raw, 3000)
        self.assertIsNotNone(wav)
        self.assertIsNone(reason)
        self.assertTrue(any('lệch' in line for line in logs.output))

    def test_prepare_khong_canh_bao_khi_do_dai_khop(self):
        raw = _mp3(_speechlike(15.0))
        with self.assertNoLogs(_LOG, level='WARNING'):
            self.prep._prepare(raw, 15000)
