from odoo.tests.common import TransactionCase
from odoo.tools import mute_logger

from odoo.addons.aidt_meeting_minutes.models.text_filter import (
    HALLUCINATION_PATTERNS,
)


class TextFilterCase(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.filt = cls.env['aidt.meeting.text.filter']

    # ---------------------------------------------------------------- #
    # Bỏ đi: ảo giác chiếm trọn đoạn
    # ---------------------------------------------------------------- #
    def test_pure_hallucination_dropped_with_reason(self):
        text, note = self.filt._filter('Hãy subscribe cho kênh Ghiền Mì Gõ')
        self.assertEqual(text, '')
        self.assertTrue(note, 'phải nêu lý do, không được bỏ im lặng')
        self.assertIn('ảo giác', note)

    def test_every_pattern_matches_something(self):
        """Mỗi mẫu phải bắt được ÍT NHẤT một chuỗi.

        Một mẫu chết (regex sai, gõ nhầm dấu) trông y hệt một mẫu chưa bao
        giờ gặp ca nào — cả hai đều im lặng. Test này phân biệt hai thứ đó.
        """
        samples = {
            r'hãy subscribe cho kênh': 'hãy subscribe cho kênh',
            r'ghiền mì gõ': 'ghiền mì gõ',
            r'để không bỏ lỡ nh[uưữ]ng video hấp dẫn':
                'để không bỏ lỡ những video hấp dẫn',
            r'đừng quên like và subscribe': 'đừng quên like và subscribe',
            r'nhấn nút đăng ký': 'nhấn nút đăng ký',
            r'cảm ơn các bạn đã theo dõi': 'cảm ơn các bạn đã theo dõi',
            r'hãy đăng ký kênh': 'hãy đăng ký kênh',
            r'xin chào các bạn.{0,20}kênh': 'xin chào các bạn của kênh',
            r'hẹn gặp lại.{0,20}video': 'hẹn gặp lại ở video sau',
            r'like.{0,20}share.{0,20}subscribe': 'like share subscribe',
            r'thank you for watching': 'thank you for watching',
            r'please subscribe': 'please subscribe',
            r'like and subscribe': 'like and subscribe',
            r"don'?t forget to subscribe": "don't forget to subscribe",
            r'hit the bell': 'hit the bell',
            r'©.{0,40}all rights reserved': '© 2026 all rights reserved',
            r'subtitles? by': 'subtitles by',
            r'www\.\w+\.\w+': 'www.example.com',
            r'^meeting\.?$': 'meeting.',
            r'^meeting discussion\.?$': 'meeting discussion',
            r'^cuộc họp công việc\.?$': 'cuộc họp công việc',
        }
        self.assertEqual(
            set(samples), set(HALLUCINATION_PATTERNS),
            'danh sách mẫu đổi mà bảng mẫu thử không đổi theo')
        for pattern, sample in samples.items():
            with self.subTest(pattern=pattern):
                text, note = self.filt._filter(sample)
                self.assertEqual(text, '', f'{pattern!r} không bắt được')
                self.assertTrue(note)

    def test_multi_pattern_hallucination_dropped(self):
        """Ảo giác nhiều câu khớp nhiều mẫu chồng nhau vẫn phải bị bỏ.

        Đây chính là ca mà cách xét từng vùng riêng lẻ bỏ lọt: không vùng nào
        một mình chiếm quá ngưỡng.
        """
        text, note = self.filt._filter(
            'Cảm ơn các bạn đã theo dõi. Hẹn gặp lại ở video sau.')
        self.assertEqual(text, '')
        self.assertIn('ảo giác', note)

    def test_measured_large_v3_hallucinations(self):
        """Đầu ra THẬT của `openai/whisper-large-v3`, đo ngày 05/08/2026.

        Không phải ví dụ bịa: gửi thẳng audio tổng hợp vào chính service
        `aidt-asr` đang chạy và chép lại nguyên văn đầu ra.
          - im lặng tuyệt đối (toàn số 0) -> câu thứ nhất, avg_logprob -0.108
          - nhiễu nền RMS 0.001 và 0.006  -> câu thứ hai, avg_logprob -0.135

        Chú ý `avg_logprob` cao: model RẤT TỰ TIN về những câu không ai nói.
        Đó là lý do lọc theo độ tin cậy KHÔNG bắt được lớp lỗi này, và là lý
        do phải có blocklist cộng với cổng lọc tiếng nói ở `audio_prep`.
        """
        for text in (
            'Hãy subscribe cho kênh La La School Để không bỏ lỡ những '
            'video hấp dẫn',
            'Cảm ơn các bạn đã theo dõi và hẹn gặp lại.',
        ):
            with self.subTest(text=text):
                kept, note = self.filt._filter(text)
                self.assertEqual(kept, '')
                self.assertIn('ảo giác', note)

    def test_vong_lap_nha_nguoc_prompt_bi_bo(self):
        """SỰ CỐ THẬT, bản ghi 1141 ngày 05/08/2026.

        Model nhả ngược chính `asr_prompt` ta gửi đi rồi lặp 18 lần, ngay
        giữa biên bản một cuộc họp thật của hai người. Blocklist KHÔNG bắt
        được: nội dung lặp là cấu hình của chính ta, không phải một khuôn
        mẫu cố định. Tỉ số nén đo được 9.89 so với 1.22 của câu nói thật
        dài nhất trong cùng bản ghi đó.
        """
        loop = ('Các bạn có thể tham gia một cuộc họp hành chính. '
                + 'Nội dung thường gặp: cuộc họp hành chính. ' * 18)
        text, note = self.filt._filter(loop)
        self.assertEqual(text, '')
        self.assertIn('vòng lặp', note)

    def test_cau_noi_that_dai_KHONG_bi_coi_la_vong_lap(self):
        """Bốn câu dưới đây là đoạn THẬT từ bản ghi 1141 và các ca đã dùng
        để hiệu chỉnh; tỉ số nén đo được nằm trong 0.89-1.22, cách ngưỡng
        2.4 rất xa. Test này giữ cho ngưỡng không bị siết xuống quá tay."""
        for real in (
            'Nhưng mà cái máy này là không hiểu sao là nó đi lóc luôn nha, '
            'máy anh thì được. Máy bảo được không hả? Thử đi, thử vô máy em đi.',
            'Vấn đề phân quyền thì mình chạy toàn bộ local, không đẩy lên '
            'server, thậm chí con model đang chạy này cũng là con Whisper luôn.',
            'Bây giờ thử dừng game lại trước thử.',
        ):
            with self.subTest(real=real[:40]):
                text, note = self.filt._filter(real)
                self.assertEqual(text, real)
                self.assertIsNone(note)

    def test_lap_lai_tu_nhien_ngan_khong_bi_bo(self):
        """Người nói lắp hoặc nhấn mạnh bằng cách lặp là chuyện bình thường
        và PHẢI được giữ — ngưỡng độ dài tối thiểu tồn tại vì lý do đó."""
        text, note = self.filt._filter('Dạ dạ dạ, vâng vâng, đúng rồi đúng rồi.')
        self.assertTrue(text)
        self.assertIsNone(note)

    def test_chuoi_khong_co_chu_nao_bi_bo(self):
        for junk in ('...', ',,,', '-- --', '???'):
            with self.subTest(junk=junk):
                text, note = self.filt._filter(junk)
                self.assertEqual(text, '')
                self.assertTrue(note)

    def test_luot_noi_ngan_KHONG_bi_bo(self):
        """Cố ý không port luật `len(text) <= 3` của dự án tham chiếu.

        Trong biên bản họp tiếng Việt, lượt nói ngắn nhất lại thường là lượt
        mang tính pháp lý nhất: tiếng đồng ý của người chủ trì. Xoá "Dạ" khỏi
        một biên bản chính thức là xoá đúng thứ người ta sẽ tra lại về sau.
        """
        for short in ('Dạ', 'Ừ', 'OK', 'Rồi', 'Vâng', 'a'):
            with self.subTest(short=short):
                text, note = self.filt._filter(short)
                self.assertEqual(text, short)
                self.assertIsNone(note)

    # ---------------------------------------------------------------- #
    # Giữ lại: câu nói thật, kể cả khi trùng khuôn mẫu
    # ---------------------------------------------------------------- #
    @mute_logger('odoo.addons.aidt_meeting_minutes.models.text_filter')
    def test_real_speech_containing_pattern_is_kept(self):
        """CA QUAN TRỌNG NHẤT của cả module này.

        Dự án tham chiếu xoá TOÀN BỘ đoạn khi bất kỳ mẫu nào khớp ở bất kỳ
        đâu. Câu dưới đây là lời kết thật của một buổi báo cáo — nếu bị xoá
        thì 15 giây biên bản chính thức biến mất không dấu vết.
        """
        real = ('Trước khi kết thúc phần trình bày về ngân sách quý ba, tôi '
                'xin cảm ơn các bạn đã theo dõi và mong nhận được ý kiến '
                'đóng góp của các đồng chí trong cuộc họp tới.')
        text, note = self.filt._filter(real)
        self.assertEqual(text, real)
        self.assertIsNone(note)

    def test_greedy_wildcard_does_not_swallow_real_sentence(self):
        """Ca đã làm hỏng phiên bản đầu của chính module này.

        Với `hẹn gặp lại.*video` (không chặn khoảng cách), phần khớp nuốt
        trọn 84% câu dưới đây và xoá mất một câu hoàn toàn bình thường. Chặn
        `.{0,20}` là thứ giữ cho ca này sống. Xoá ràng buộc đó ra thì test
        này phải đỏ — đó là lý do nó tồn tại.
        """
        real = ('Hẹn gặp lại các đồng chí vào tuần sau, chúng ta sẽ xem lại '
                'video hướng dẫn.')
        text, note = self.filt._filter(real)
        self.assertEqual(text, real)
        self.assertIsNone(note)

    def test_ordinary_speech_untouched(self):
        real = 'Vấn đề phân quyền thì mình chạy toàn bộ local, không đẩy lên.'
        text, note = self.filt._filter(real)
        self.assertEqual(text, real)
        self.assertIsNone(note)

    def test_whitespace_only_is_not_an_error(self):
        """Rỗng là im lặng hợp lệ, không phải thứ cần báo cáo."""
        text, note = self.filt._filter('   \n ')
        self.assertEqual(text, '')
        self.assertIsNone(note)

    # ---------------------------------------------------------------- #
    # Lọc theo danh sách đoạn
    # ---------------------------------------------------------------- #
    def test_filter_segments_keeps_good_drops_bad(self):
        parsed = [
            {'start_ms': 0, 'end_ms': 1000, 'text': 'Chào các đồng chí.'},
            {'start_ms': 1000, 'end_ms': 2000, 'text': 'Please subscribe'},
            {'start_ms': 2000, 'end_ms': 3000, 'text': 'Ta bắt đầu họp.'},
        ]
        kept, notes = self.filt._filter_segments(parsed)
        self.assertEqual([k['text'] for k in kept],
                         ['Chào các đồng chí.', 'Ta bắt đầu họp.'])
        self.assertEqual(len(notes), 1)
        self.assertIn('ảo giác', notes[0])

    def test_filter_segments_preserves_timestamps(self):
        """Lọc chữ KHÔNG được đụng vào mốc thời gian."""
        parsed = [{'start_ms': 4200, 'end_ms': 9900, 'text': ' Xin chào.  '}]
        kept, _notes = self.filt._filter_segments(parsed)
        self.assertEqual(kept[0]['start_ms'], 4200)
        self.assertEqual(kept[0]['end_ms'], 9900)
        self.assertEqual(kept[0]['text'], 'Xin chào.')

    def test_filter_segments_tolerates_missing_text_key(self):
        kept, notes = self.filt._filter_segments([{'start_ms': 0}])
        self.assertEqual(kept, [])
        self.assertEqual(notes, [])
