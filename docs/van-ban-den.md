Với văn bản đến, Odoo Community + OCA đáp ứng được phần "khung", nhưng phần nghiệp vụ văn thư (số đến, sổ đến, chuyển giao, đôn đốc) gần như phải custom hết. Đi theo từng bước của bạn:

## 1. Tiếp nhận / số hóa văn bản đến

**Có sẵn:**
- **Mail gateway (core Community)** — `fetchmail`: cấu hình hộp mail cơ quan, email đến tự sinh bản ghi trong model bạn chỉ định (qua `mail.alias`). Văn bản đến qua email/trục sẽ tự nhảy vào hàng chờ tiếp nhận, kèm file đính kèm.
- **OCA `dms`** (repo OCA/dms) — thay thế Documents Enterprise: kho thư mục phân cấp, quyền theo thư mục, lưu file có version.
- **OCA `attachment_preview`** — xem PDF ngay trên form, không cần tải về (khớp V-04).

**Phải tự làm:** OCR tiếng Việt. OCA không có gì dùng được cho tiếng Việt. Kiến trúc hợp lý: máy scan đẩy file vào thư mục theo dõi hoặc upload hàng loạt (S-01) → Odoo gọi service OCR ngoài (bạn đằng nào cũng phải dựng cho pipeline AI của MVP) → trả text + metadata đề xuất về bản ghi văn bản đến ở trạng thái "chờ đăng ký". Đừng cố nhét OCR vào trong Odoo worker — chạy service riêng, gọi async qua queue (OCA `queue_job` rất đáng dùng ở đây).

## 2. Đăng ký văn bản đến — phần custom lõi

Model riêng, tách khỏi văn bản đi vì metadata khác nhau:

```python
class VanBanDen(models.Model):
    _name = 'vanban.den'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    so_den = fields.Integer('Số đến', readonly=True, copy=False)
    ngay_den = fields.Date('Ngày đến', default=fields.Date.today, readonly=True)
    # Thông tin trên văn bản gốc
    so_ky_hieu_goc = fields.Char('Số/ký hiệu của VB')
    ngay_van_ban = fields.Date('Ngày văn bản')
    co_quan_ban_hanh = fields.Many2one('res.partner')
    trich_yeu = fields.Text(required=True)
    do_mat = fields.Selection([...])
    do_khan = fields.Selection([...])
    han_xu_ly = fields.Date('Hạn giải quyết')
    # Luồng xử lý
    nguoi_trinh = fields.Many2one('res.users')          # văn thư
    lanh_dao_but_phe = fields.Many2one('res.users')
    y_kien_but_phe = fields.Text('Ý kiến chỉ đạo')
    don_vi_chu_tri = fields.Many2one('hr.department')
    don_vi_phoi_hop = fields.Many2many('hr.department')
    state = fields.Selection([
        ('tiep_nhan', 'Tiếp nhận'),
        ('da_dang_ky', 'Đã đăng ký'),
        ('cho_but_phe', 'Trình lãnh đạo'),
        ('dang_xu_ly', 'Đang giải quyết'),
        ('hoan_thanh', 'Hoàn thành'),
    ], default='tiep_nhan', tracking=True)
```

**Cấp số đến:** khác văn bản đi ở chỗ số đến cấp **ngay lúc đăng ký**, liên tục theo năm, thường theo sổ (sổ thường / sổ mật tách riêng theo quy định bảo vệ bí mật nhà nước — văn bản Mật trở lên vào sổ riêng, người thường không thấy cả sự tồn tại của nó):

```python
def action_dang_ky(self):
    for rec in self:
        so_type = 'mat' if rec.do_mat != 'thuong' else 'thuong'
        rec.so_den = self.env['ir.sequence'].next_by_code(
            f'vanban.den.{so_type}')
        rec.state = 'da_dang_ky'
```

Dùng `ir.sequence` với `use_date_range=True` reset đầu năm, và cân nhắc `implementation='no_gap'` vì sổ đến về nguyên tắc không được nhảy số.

**Sổ văn bản đến:** thực chất chỉ là list view + report. Làm một báo cáo QWeb/XLSX (OCA `report_xlsx`) xuất đúng mẫu sổ đăng ký văn bản đến theo quy định — cột số đến, ngày đến, tác giả, số ký hiệu, trích yếu, đơn vị nhận, ký nhận.

## 3. Trình văn bản & bút phê

Không có module sẵn nào mô hình hóa đúng "bút phê" — bản chất là: văn thư trình → lãnh đạo ghi ý kiến chỉ đạo + phân đơn vị chủ trì/phối hợp + hạn → chuyển xuống. Custom bằng state machine ở trên + `mail.activity` giao cho lãnh đạo. Ý kiến bút phê lưu vào trường riêng (`y_kien_but_phe`), không chỉ nằm trong chatter, vì sau này nó là nguồn để bóc tách nhiệm vụ (T-01) và phải xuất được ra phiếu xử lý văn bản.

Điểm hay: làm màn hình riêng tối giản cho lãnh đạo — danh sách chờ bút phê, mở ra thấy PDF bên trái (attachment_preview), form bút phê bên phải, vài nút chọn nhanh đơn vị. Lãnh đạo không dùng giao diện Odoo mặc định nổi đâu.

## 4. Chuyển giao giải quyết

Hai lớp:
- **Chuyển đơn vị:** ghi vào `don_vi_chu_tri`/`don_vi_phoi_hop`, record rule mở quyền đọc cho đơn vị được giao (đúng N-05 — chỉ thấy văn bản của mình + được chia sẻ).
- **Giao việc cụ thể:** đây là chỗ tận dụng **Project (core Community)** — mỗi văn bản đến cần giải quyết sinh task, link ngược về văn bản (trường `vanban_den_id` trên `project.task`). Bạn được miễn phí: kanban, người phụ trách, deadline, sub-task (T-10), trạng thái. Đỡ phải tự viết cả một module quản lý nhiệm vụ — chỉ cần kế thừa `project.task` thêm vài trường.

## 5. Theo dõi, đôn đốc

- **`mail.activity`** có sẵn cơ chế deadline + hiển thị quá hạn (đỏ) trên systray.
- Nhắc trước hạn 7/3/1 ngày (T-11): viết `ir.cron` chạy hàng ngày, quét văn bản/task sắp đến hạn, gửi mail template + tạo activity. Vài chục dòng code.
- Báo cáo quá hạn cho Chánh VP hàng tuần (T-14): thêm một cron nữa render QWeb report gửi mail.
- Dashboard đơn giản (T-15): list view + group by + filter là đủ cho MVP; đẹp hơn thì OCA có `web_dashboard`-type module hoặc dùng graph/pivot view core.

## Tóm lại phần OCA đáng cài

`dms`, `attachment_preview`, `queue_job`, `auditlog` (khớp N-07), `report_xlsx`, và ngó thêm `base_tier_validation` — module OCA làm luồng duyệt nhiều cấp cấu hình được trên bất kỳ model nào, có thể thay cho việc tự viết state machine trình ký nếu luồng của bạn không quá phức tạp (đáng thử trước khi quyết định tự code).

Tỷ lệ thực tế: khung + quyền + chatter + nhắc việc Odoo/OCA lo được, còn **model văn bản đến, cấp số theo sổ, màn hình bút phê, phiếu xử lý, sổ đăng ký** là ~2-3 tuần custom cho một dev Odoo quen tay. Phần OCR và bóc tách nhiệm vụ AI thì đứng ngoài Odoo hoàn toàn, chỉ nói chuyện qua API như đã bàn ở văn bản đi.

## Odoo cho phép task không có project

Từ Odoo 15 trở đi, `project_id` trên `project.task` **không phải trường required**. Task không có project được coi là "private task" — nó chỉ hiện trong "My Tasks" của người được giao, không nằm trong kanban chung nào. Bạn hoàn toàn có thể tạo:

```python
self.env['project.task'].create({
    'name': f"Xử lý VB đến số {rec.so_den}: {rec.trich_yeu[:80]}",
    'user_ids': [(6, 0, nguoi_xu_ly.ids)],
    'date_deadline': rec.han_xu_ly,
    'vanban_den_id': rec.id,
})
```

mà không cần `project_id`.

**Nhưng đừng làm vậy** cho bài toán của bạn, vì private task mất gần hết giá trị: không có kanban theo dõi chung, Chánh VP không có chỗ nhìn tổng thể, không group theo stage, khó làm báo cáo đôn đốc — trong khi cái bạn cần chính là theo dõi tập trung (T-08, T-14, T-15).

## Ba phương án tổ chức project

**Phương án 1 — Một project duy nhất "Xử lý văn bản đến"** (khuyên dùng cho MVP):
Tạo sẵn 1 project qua data XML khi cài module, mọi task giao việc từ văn bản đến đều rơi vào đây. Stage của project map với trạng thái nhiệm vụ của bạn (Mới → Đang thực hiện → Chờ duyệt → Hoàn thành). Lọc theo đơn vị thì dùng trường custom `don_vi_id` trên task + filter/group by. Đơn giản, một chỗ nhìn toàn bộ, dễ làm báo cáo.

**Phương án 2 — Mỗi đơn vị/phòng ban một project:**
Hợp nếu các phòng muốn không nhìn thấy việc của nhau (quyền theo project là cơ chế sẵn có của Odoo — project private chỉ member thấy). Đổi lại, nhìn tổng hợp phải qua "All Tasks" + group by project, và phải viết logic tự chọn project theo `don_vi_chu_tri` khi sinh task. Vẫn gọn: tạo project tự động lần đầu mỗi phòng phát sinh việc, hoặc tạo sẵn theo cây tổ chức.

**Phương án 3 — Mỗi văn bản một project:** đừng. Sẽ có hàng nghìn project rác sau một năm, kanban vô nghĩa, chọn project khi giao việc thành cực hình.

## Lưu ý triển khai

- Với phương án 1, hardcode project qua XML data + `noupdate="1"`, và lấy bằng `self.env.ref('ten_module.project_vb_den')` khi sinh task — đừng để người dùng phải chọn.
- Trường `stage_id` của task là **per-project** (stage thuộc về project), nên nếu sau này chuyển từ phương án 1 sang 2, phải nhân bản bộ stage cho từng project — thêm lý do để MVP bắt đầu bằng 1 project.
- Quyền: user chỉ cần group "Project / User" là thấy và cập nhật task của mình; kết hợp record rule nếu muốn task đơn vị nào đơn vị đó thấy ngay cả trong cùng 1 project.
- Nhớ thêm smart button hai chiều: trên form văn bản đến hiện "N nhiệm vụ", trên task hiện nút mở văn bản nguồn — đây chính là "liên kết nguồn" (T-07) của bạn.

Tóm lại: dùng **1 project cố định tạo sẵn khi cài module**, task nào cũng có project nhưng người dùng không bao giờ phải "tạo project" — thao tác giao việc chỉ là bấm nút trên văn bản đến.