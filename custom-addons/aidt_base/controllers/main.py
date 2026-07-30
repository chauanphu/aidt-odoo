from odoo import http
from odoo.http import request

try:
    from odoo.addons.website.controllers.main import Website
except ImportError:
    Website = object


class RootRedirectController(Website if Website != object else http.Controller):

    @http.route('/', auth="public", website=True, sitemap=True)
    def index(self, **kw):
        if not request.session.uid:
            return request.redirect('/web/login')
        return request.redirect('/odoo')
