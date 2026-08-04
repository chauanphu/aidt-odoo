import os
import base64
from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.addons.aidt_sign.services.pdf_converter import convert_to_pdf
from odoo.addons.aidt_sign.services.pades_signer import sign_pades_pdf

class AidtDocument(models.Model):
    _inherit = 'aidt.document'

    state = fields.Selection(
        selection_add=[
            ('cho_duyet_tp', 'Chờ duyệt TP'),
            ('cho_duyet_cvp', 'Chờ duyệt CVP'),
            ('cho_duyet_lanh_dao', 'Chờ duyệt Lãnh đạo'),
            ('cho_ky', 'Chờ ký'),
            ('cho_cap_so', 'Chờ cấp số'),
            ('da_ban_hanh', 'Đã ban hành'),
        ],
        ondelete={
            'cho_duyet_tp': 'set default',
            'cho_duyet_cvp': 'set default',
            'cho_duyet_lanh_dao': 'set default',
            'cho_ky': 'set default',
            'cho_cap_so': 'set default',
            'da_ban_hanh': 'set default',
        },
    )

    so_ky_hieu = fields.Char('Số/Ký hiệu phát hành', readonly=True, copy=False)
    nguoi_soan_id = fields.Many2one('res.users', string='Người soạn', default=lambda self: self.env.user)
    template_id = fields.Many2one('aidt.document.template', string='Mẫu văn bản')

    @api.onchange('template_id')
    def _onchange_template_id(self):
        if self.template_id and self.template_id.doc_type and not self.doc_type:
            self.doc_type = self.template_id.doc_type

    
    nguoi_duyet_tp_id = fields.Many2one('res.users', string='Trưởng phòng duyệt', tracking=True)
    y_kien_tp = fields.Text('Ý kiến TP')
    ngay_duyet_tp = fields.Datetime('Ngày duyệt TP', readonly=True)
    
    nguoi_duyet_cvp_id = fields.Many2one('res.users', string='CVP duyệt', tracking=True)
    y_kien_cvp = fields.Text('Ý kiến CVP')
    ngay_duyet_cvp = fields.Datetime('Ngày duyệt CVP', readonly=True)
    
    nguoi_duyet_lanh_dao_id = fields.Many2one('res.users', string='Lãnh đạo duyệt', tracking=True)
    y_kien_lanh_dao = fields.Text('Ý kiến Lãnh đạo')
    ngay_duyet_lanh_dao = fields.Datetime('Ngày duyệt Lãnh đạo', readonly=True)
    
    nguoi_ky_id = fields.Many2one('res.users', string='Người ký')
    ngay_ky = fields.Datetime('Ngày ký', readonly=True)
    
    noi_nhan = fields.Text('Nơi nhận', help='Danh sách nơi nhận, mỗi dòng 1 đơn vị')
    so_ban_phat_hanh = fields.Integer('Số bản phát hành', default=1)
    
    format_ok = fields.Boolean('Thể thức đạt', default=False, readonly=True)
    format_note = fields.Text('Ghi chú thể thức', readonly=True)

    signed_pdf_file = fields.Binary('Tệp PDF đã ký số', compute='_compute_signed_pdf', store=False)
    signed_pdf_filename = fields.Char('Tên tệp PDF đã ký số', compute='_compute_signed_pdf', store=False)

    def _compute_signed_pdf(self):
        for rec in self:
            att = self.env['ir.attachment'].search([
                ('res_model', '=', 'aidt.document'),
                ('res_id', '=', rec.id),
                ('mimetype', '=', 'application/pdf')
            ], order='id desc', limit=1)
            if not att:
                att = self.env['ir.attachment'].search([
                    ('res_model', '=', 'aidt.document'),
                    ('res_id', '=', rec.id),
                    ('name', 'ilike', '.pdf')
                ], order='id desc', limit=1)
            if att:
                rec.signed_pdf_file = att.datas
                rec.signed_pdf_filename = att.name
            else:
                rec.signed_pdf_file = False
                rec.signed_pdf_filename = False

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if res.get('direction') == 'di':
            res['state'] = 'draft'
        return res

    def action_submit_tp(self):
        """Chuyên viên trình Trưởng phòng."""
        if not (self.env.user.has_group('aidt_org.group_chuyen_vien') or self.env.user.has_group('aidt_org.group_aidt_admin')):
            raise UserError("Bạn không có quyền trình Trưởng phòng.")
        for rec in self:
            if rec.direction != 'di':
                continue
            if not rec.name:
                raise UserError("Vui lòng nhập 'Trích yếu nội dung' trước khi trình duyệt.")
            if not rec.file_count:
                raise UserError("Chưa có tệp đính kèm. Vui lòng đính kèm file dự thảo (.docx/.pdf) trước khi trình Trưởng phòng.")
            rec.sudo().write({'state': 'cho_duyet_tp'})

    def action_approve_tp(self):
        """Trưởng phòng duyệt."""
        allowed_groups = ['aidt_org.group_truong_phong', 'aidt_org.group_aidt_admin']
        if not any(self.env.user.has_group(g) for g in allowed_groups):
            raise UserError("Bạn không có quyền duyệt với vai trò Trưởng phòng.")
        for rec in self:
            if rec.direction != 'di':
                continue
            rec.sudo().write({
                'state': 'cho_duyet_cvp',
                'nguoi_duyet_tp_id': self.env.uid,
                'ngay_duyet_tp': fields.Datetime.now(),
            })

    def action_reject_tp(self):
        """TP trả về chuyên viên."""
        self.filtered(lambda r: r.direction == 'di').sudo().write({'state': 'draft'})

    def action_approve_cvp(self):
        """CVP duyệt."""
        allowed_groups = ['aidt_org.group_chanh_vp', 'aidt_org.group_aidt_admin']
        if not any(self.env.user.has_group(g) for g in allowed_groups):
            raise UserError("Bạn không có quyền duyệt với vai trò Chánh văn phòng.")
        for rec in self:
            if rec.direction != 'di':
                continue
            rec.sudo().write({
                'state': 'cho_duyet_lanh_dao',
                'nguoi_duyet_cvp_id': self.env.uid,
                'ngay_duyet_cvp': fields.Datetime.now(),
            })

    def action_reject_cvp(self):
        """CVP trả về TP."""
        self.filtered(lambda r: r.direction == 'di').sudo().write({'state': 'cho_duyet_tp'})

    def action_approve_lanh_dao(self):
        """Lãnh đạo duyệt nội dung."""
        allowed_groups = ['aidt_org.group_bi_thu', 'aidt_org.group_pho_bi_thu', 'aidt_org.group_aidt_admin']
        if not any(self.env.user.has_group(g) for g in allowed_groups):
            raise UserError("Bạn không có quyền duyệt với vai trò Lãnh đạo.")
        for rec in self:
            if rec.direction != 'di':
                continue
            rec.sudo().write({
                'state': 'cho_ky',
                'nguoi_duyet_lanh_dao_id': self.env.uid,
                'ngay_duyet_lanh_dao': fields.Datetime.now(),
            })

    def action_reject_lanh_dao(self):
        """Lãnh đạo trả về CVP."""
        self.filtered(lambda r: r.direction == 'di').sudo().write({'state': 'cho_duyet_cvp'})

    def action_sign(self):
        """Ký số Lãnh đạo chuẩn PAdES & tự động convert file Word sang PDF."""
        allowed_groups = ['aidt_org.group_bi_thu', 'aidt_org.group_pho_bi_thu', 'aidt_org.group_aidt_admin']
        if not any(self.env.user.has_group(g) for g in allowed_groups):
            raise UserError("Bạn không có quyền thực hiện ký số.")

        for rec in self:
            if rec.direction != 'di':
                continue

            attachment = self.env['ir.attachment'].search([
                ('res_model', '=', 'aidt.document'),
                ('res_id', '=', rec.id)
            ], order='id desc', limit=1)

            if attachment and attachment.datas:
                file_bytes = base64.b64decode(attachment.datas)
                filename = attachment.name or 'document.docx'
                pdf_bytes = convert_to_pdf(file_bytes, filename)

                cert = self.env['aidt.sign.certificate'].sudo().search([
                    ('owner_id', '=', self.env.uid),
                    ('cert_type', '=', 'personal'),
                    ('active', '=', True)
                ], limit=1)

                if not cert or not cert.cert_file:
                    raise UserError(
                        f"Không thể ký số: Tài khoản của bạn ({self.env.user.name}) chưa được nạp Chứng thư số cá nhân (.p12).\n"
                        "Vui lòng vào menu 'Ký số PAdES -> Chứng thư số' để tải tệp chứng thư cá nhân trước khi thực hiện ký."
                    )

                new_filename = f"{os.path.splitext(filename)[0]}.pdf"
                cert_bytes = base64.b64decode(cert.cert_file)
                user_sig_img = self.env.user.digital_signature_img
                img_bytes = base64.b64decode(user_sig_img) if user_sig_img else None
                signed_pdf = sign_pades_pdf(
                    pdf_bytes=pdf_bytes,
                    cert_bytes=cert_bytes,
                    password=cert.password or '',
                    img_bytes=img_bytes,
                    signer_name=self.env.user.name
                )
                self.env['aidt.sign.log'].sudo().create({
                    'res_model': 'aidt.document',
                    'res_id': rec.id,
                    'user_id': self.env.uid,
                    'sign_type': 'leader',
                    'cert_name': cert.name,
                })

                attachment.sudo().write({
                    'datas': base64.b64encode(signed_pdf),
                    'name': new_filename,
                    'mimetype': 'application/pdf'
                })

            rec.sudo().write({
                'state': 'cho_cap_so',
                'nguoi_ky_id': self.env.uid,
                'ngay_ky': fields.Datetime.now(),
            })

    def action_issue_vbd(self):
        """Văn thư cấp số ký hiệu → đóng dấu cơ quan PAdES → ban hành."""
        allowed_groups = ['aidt_org.group_van_thu', 'aidt_org.group_aidt_admin']
        if not any(self.env.user.has_group(g) for g in allowed_groups):
            raise UserError("Bạn không có quyền cấp số và ban hành văn bản.")

        for rec in self:
            if rec.direction != 'di':
                continue
            seq_code = ('aidt.vanban.di.mat'
                        if rec.secrecy != 'thuong'
                        else 'aidt.vanban.di.thuong')
            so_kh = rec.so_ky_hieu or self.env['ir.sequence'].next_by_code(seq_code)

            attachment = self.env['ir.attachment'].search([
                ('res_model', '=', 'aidt.document'),
                ('res_id', '=', rec.id)
            ], order='id desc', limit=1)

            if attachment and attachment.datas:
                file_bytes = base64.b64decode(attachment.datas)
                filename = attachment.name or 'document.docx'
                pdf_bytes = convert_to_pdf(file_bytes, filename)

                org_cert = self.env['aidt.sign.certificate'].sudo().search([
                    ('cert_type', '=', 'org'),
                    ('active', '=', True)
                ], limit=1)

                if not org_cert or not org_cert.cert_file:
                    raise UserError(
                        "Không thể đóng dấu ban hành: Hệ thống chưa được nạp Chứng thư số Cơ quan (Con dấu tổ chức).\n"
                        "Vui lòng vào menu 'Ký số PAdES -> Chứng thư số' để cấu hình chứng thư tổ chức trước khi ban hành."
                    )

                new_filename = f"{os.path.splitext(filename)[0]}.pdf"
                cert_bytes = base64.b64decode(org_cert.cert_file)
                org_seal_img = org_cert.seal_img
                img_bytes = base64.b64decode(org_seal_img) if org_seal_img else None
                signed_pdf = sign_pades_pdf(
                    pdf_bytes=pdf_bytes,
                    cert_bytes=cert_bytes,
                    password=org_cert.password or '',
                    img_bytes=img_bytes,
                    signer_name=self.env.company.name or "Cơ quan Ban hành",
                    is_org=True
                )
                self.env['aidt.sign.log'].sudo().create({
                    'res_model': 'aidt.document',
                    'res_id': rec.id,
                    'user_id': self.env.uid,
                    'sign_type': 'org',
                    'cert_name': org_cert.name,
                })

                attachment.sudo().write({
                    'datas': base64.b64encode(signed_pdf),
                    'name': new_filename,
                    'mimetype': 'application/pdf'
                })

            rec.sudo().write({
                'so_ky_hieu': so_kh,
                'state': 'da_ban_hanh',
                'date': fields.Date.today(),
            })

