from odoo.tests import tagged
from odoo.tests.common import TransactionCase


class TranscriptCase(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.builder = cls.env['aidt.meeting.transcript']
        cls.an = cls.env['res.partner'].create({'name': 'Nguyễn Văn An'})
        cls.binh = cls.env['res.partner'].create({'name': 'Trần Thị Bình'})
        cls.channel = cls.env['discuss.channel'].create({
            'name': 'Cuộc gọi', 'channel_type': 'channel',
        })
        cls.recording = cls.env['aidt.meeting.recording'].sudo().create({
            'channel_id': cls.channel.id, 'secrecy_at_start': 'thuong',
        })

    def _seg(self, partner, start_ms, end_ms, text):
        return self.env['aidt.meeting.segment'].sudo().create({
            'recording_id': self.recording.id, 'partner_id': partner.id,
            'start_ms': start_ms, 'end_ms': end_ms, 'text': text,
        })


class TestTranscript(TranscriptCase):
    def test_tron_dung_thu_tu_giua_hai_nguoi(self):
        self._seg(self.binh, 5000, 7000, 'Tôi đồng ý')
        self._seg(self.an, 1000, 3000, 'Xin chào')
        text = self.builder._build(self.recording)
        self.assertLess(text.index('Xin chào'), text.index('Tôi đồng ý'))

    def test_gop_luot_noi_lien_tiep_cua_cung_mot_nguoi(self):
        """Ba đoạn liền của một người phải thành một khối, không phải ba
        dòng lặp tên — biên bản đọc được mới là mục tiêu."""
        self._seg(self.an, 0, 1000, 'Câu một.')
        self._seg(self.an, 1000, 2000, 'Câu hai.')
        self._seg(self.an, 2000, 3000, 'Câu ba.')
        text = self.builder._build(self.recording)
        self.assertEqual(text.count('Nguyễn Văn An'), 1)
        self.assertIn('Câu một. Câu hai. Câu ba.', text)

    def test_khu_trung_lap_o_moi_noi_chong_lan(self):
        """Chunk chồng lấn 1.5 giây nên câu ở mối nối bị bóc băng hai lần.
        Không khử thì biên bản lặp chữ ở mỗi 15 giây."""
        self._seg(self.an, 0, 15000, 'Chúng ta bắt đầu cuộc họp')
        self._seg(self.an, 13500, 28000, 'cuộc họp hôm nay bàn ba việc')
        text = self.builder._build(self.recording)
        self.assertEqual(text.count('cuộc họp'), 1)

    def test_danh_dau_khoang_thieu_am_thanh(self):
        """Khoảng khuyết phải được nói ra, ĐÚNG vị trí thời gian giữa các
        lượt nói xung quanh. Một biên bản có lỗ hổng vô hình tệ hơn một
        biên bản thừa nhận nó — nhưng nếu marker chỉ bị nối vào cuối bất kể
        thứ tự, bài test cũ vẫn xanh dù vị trí sai; test này đặt một lượt
        nói RÕ RÀNG trước và một lượt RÕ RÀNG sau mốc khoảng khuyết để buộc
        kiểm tra đúng vị trí xen kẽ."""
        self._seg(self.an, 0, 1000, 'Trước khoảng khuyết')
        chunk = self.env['aidt.meeting.chunk'].sudo().create({
            'recording_id': self.recording.id, 'partner_id': self.an.id,
            'seq': 5, 'offset_ms': 60000, 'duration_ms': 15000,
            'state': 'failed', 'error': 'ASR chết',
        })
        self.assertTrue(chunk)
        self._seg(self.binh, 90000, 91000, 'Sau khoảng khuyết')
        text = self.builder._build(self.recording)
        self.assertIn('[thiếu âm thanh', text)
        self.assertIn('01:00', text)
        self.assertLess(
            text.index('Trước khoảng khuyết'), text.index('[thiếu âm thanh'))
        self.assertLess(
            text.index('[thiếu âm thanh'), text.index('Sau khoảng khuyết'))

    def test_neu_ten_nguoi_tu_choi_o_dau_ban(self):
        self.recording.sudo().declined_partner_ids = [(4, self.binh.id)]
        self._seg(self.an, 0, 1000, 'Xin chào')
        text = self.builder._build(self.recording)
        self.assertIn('Trần Thị Bình', text.split('\n\n')[0])

    def test_ban_rong_van_tra_ve_chuoi_khong_nem_loi(self):
        text = self.builder._build(self.recording)
        self.assertIsInstance(text, str)


@tagged('post_install', '-at_install')
class TestStripOverlapDoLui(TranscriptCase):
    """Phần dò lùi 6 vị trí ở mối nối.

    Mọi ca ở đây đều xoay quanh MỘT đánh đổi: nới cửa sổ tìm kiếm bắt được
    nhiều seam thật hơn, đồng thời mở đường cho xoá NHẦM. Nên nửa số test
    dưới đây khẳng định cái được xoá, nửa còn lại khẳng định cái KHÔNG được
    xoá — nửa sau mới là nửa bảo vệ tính toàn vẹn của biên bản.
    """

    def test_khop_duoc_nho_do_lui_khi_duoi_mau_truoc_co_tu_thua(self):
        """Ca chính mà bản cũ trượt: mẩu trước kết thúc bằng hai từ đệm
        ("ừ à") mà mẩu sau không nghe ra, nên phép khớp SÁT ĐUÔI không thấy
        gì, dù "phương án một" rành rành bị bóc băng hai lần."""
        previous = 'Chúng ta thống nhất phương án một ừ à'
        current = 'phương án một sẽ trình lãnh đạo tuần sau'
        self.assertEqual(
            self.builder._strip_overlap(previous, current),
            'sẽ trình lãnh đạo tuần sau')

    def test_mot_tu_thua_chen_giua_khong_pha_duoc_phep_khop(self):
        """Chỉ MỘT từ ASR thừa ở mối nối cũng đủ làm bản cũ trượt sạch."""
        previous = 'Đề nghị các đơn vị báo cáo tiến độ ạ'
        current = 'báo cáo tiến độ trước ngày mười lăm'
        self.assertEqual(
            self.builder._strip_overlap(previous, current),
            'trước ngày mười lăm')

    def test_ca_tieng_viet_cua_du_an_tham_chieu(self):
        """Port nguyên văn ca test tiếng Việt của `STT_T-m-T-t-AI`
        (`test_strip_overlap_prefix_word_deduplication`). Giữ lại làm mốc
        đối chiếu với thuật toán nguồn, kể cả khi bản của ta đã xử lý được
        ca này từ trước."""
        previous = (
            'Làm giọng a đầm dễ mà các vợ ơi không biết người khác làm như '
            'nào nhưng đây là cách anh làm từ a đến z nha video này sẽ hơi '
            'dài đó lưu lại nếu đang bận nha bước một là các vợ tải app này '
            'về cho anh')
        current = (
            'App này về cho anh sau đó đăng nhập bằng gmail bước hai các vợ '
            'viết kịch bản đi đã bước ba là bước quan trọng này muốn giọng '
            'thằng a đầm cảm xúc hơn')
        result = self.builder._strip_overlap(previous, current)
        self.assertFalse(result.startswith('App này về cho anh'))
        self.assertFalse(result.startswith('app này về cho anh'))
        self.assertTrue(result.startswith('sau đó đăng nhập bằng gmail'))

    def test_trung_hop_mot_tu_khong_bao_gio_bi_xoa(self):
        """"vâng" vừa kết thúc lượt này vừa mở đầu lượt sau là chuyện thường
        ngày trong hội thoại tiếng Việt, không phải bằng chứng về seam. Sàn
        2 từ phải chặn nó — và dò lùi KHÔNG được phép hạ sàn đó xuống."""
        previous = 'Tôi hoàn toàn đồng ý vâng'
        current = 'vâng chúng ta sang mục tiếp theo'
        self.assertEqual(
            self.builder._strip_overlap(previous, current), current)

    def test_trung_hop_mot_tu_o_vi_tri_lui_cung_khong_bi_xoa(self):
        """Cùng lý do, nhưng từ trùng nằm SÂU trong vùng dò lùi — chính là
        vùng mà thay đổi này vừa mở ra."""
        previous = 'Vâng thưa các đồng chí tôi xin phép trình bày'
        current = 'vâng nội dung thứ nhất là ngân sách'
        self.assertEqual(
            self.builder._strip_overlap(previous, current), current)

    def test_khong_an_noi_dung_that_khi_cum_tu_lap_lai_tu_nhien(self):
        """Ca hồi quy quan trọng nhất. "các đơn vị" xuất hiện thật ở CẢ HAI
        câu, nhưng lần trước nằm ở ĐẦU `previous`, cách xa mối nối — đó là
        văn phong hành chính lặp cụm, không phải audio bị bóc hai lần. Bó
        cửa sổ dò ở 6 vị trí là thứ giữ cho "Các đơn vị" của câu sau không
        bị xoá âm thầm; nới rộng hằng số này sẽ làm test này đỏ."""
        previous = 'Đề nghị các đơn vị báo cáo trước ngày mười lăm'
        current = 'Các đơn vị chưa báo cáo sẽ bị nhắc nhở'
        self.assertEqual(
            self.builder._strip_overlap(previous, current), current)

    def test_bien_cua_so_do_lui_nam_dung_o_nam_tu_thua(self):
        """Chốt cứng độ rộng cửa sổ: 5 từ thừa ở đuôi còn khớp được, 6 thì
        không. Ghi lại bằng test để lần sau ai đó đổi hằng số thì thấy ngay
        hệ quả, thay vì phải đọc lại vòng lặp."""
        overlap = 'cuộc họp hôm nay'
        current = f'{overlap} bàn ba nội dung'
        nam_tu = 'ừ à ừm vâng dạ'
        sau_tu = f'{nam_tu} rồi'
        self.assertEqual(
            self.builder._strip_overlap(
                f'Chúng ta bắt đầu {overlap} {nam_tu}', current),
            'bàn ba nội dung')
        self.assertEqual(
            self.builder._strip_overlap(
                f'Chúng ta bắt đầu {overlap} {sau_tu}', current),
            current)

    def test_do_lui_co_hieu_luc_trong_ban_boc_bang_hoan_chinh(self):
        """Không chỉ hàm thuần: hai đoạn liền của cùng một người, mẩu trước
        có từ thừa ở đuôi, thì bản dựng ra không được lặp cụm ở mối nối."""
        self._seg(self.an, 0, 15000, 'Chúng ta thống nhất phương án một ừ')
        self._seg(self.an, 13500, 28000,
                  'phương án một sẽ trình lãnh đạo tuần sau')
        text = self.builder._build(self.recording)
        self.assertEqual(text.count('phương án một'), 1)
