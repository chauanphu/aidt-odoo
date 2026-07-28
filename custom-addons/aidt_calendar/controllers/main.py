from odoo import http
from odoo.http import request


class AppointmentController(http.Controller):
    @http.route('/dang-ky-lich-lam-viec', type='http', auth='public', website=True, sitemap=True, methods=['GET', 'POST'])
    def appointment_form(self, **kw):
        if request.httprequest.method == 'POST':
            name = kw.get('name')
            phone = kw.get('phone')
            content = kw.get('content')
            preferred_date_str = kw.get('preferred_date')

            if not (name and phone and content and preferred_date_str):
                return request.render('aidt_calendar.appointment_page', {
                    'error': 'Vui lòng điền đầy đủ các thông tin bắt buộc.',
                })

            try:
                preferred_date = preferred_date_str.replace('T', ' ')
                if len(preferred_date) == 16:
                    preferred_date += ':00'

                request.env['aidt.appointment.registration'].sudo().create({
                    'name': name,
                    'phone': phone,
                    'identity_card': kw.get('identity_card'),
                    'email': kw.get('email'),
                    'organization': kw.get('organization'),
                    'content': content,
                    'preferred_date': preferred_date,
                })
                return request.render('aidt_calendar.appointment_page', {'submitted': True})
            except Exception as e:
                return request.render('aidt_calendar.appointment_page', {
                    'error': f'Có lỗi xảy ra: {str(e)}',
                })

        return request.render('aidt_calendar.appointment_page', {})
