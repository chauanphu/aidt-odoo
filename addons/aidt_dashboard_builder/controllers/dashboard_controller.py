import logging
from odoo import http
from odoo.http import request
from ..providers.provider_registry import ProviderRegistry
from ..services.cache_service import CacheService
from ..services.metadata_service import MetadataService

_logger = logging.getLogger(__name__)


class DashboardController(http.Controller):

    def _get_or_create_default_dashboard(self, env):
        """Tự động tìm hoặc tạo mới Dashboard mặc định kèm Widgets mẫu."""
        dashboard = env['dynamic.dashboard'].search([
            ('state', '=', 'published'), ('is_default', '=', True)
        ], limit=1)

        if not dashboard:
            dashboard = env['dynamic.dashboard'].search([('state', '=', 'published')], limit=1)

        if not dashboard:
            dashboard = env['dynamic.dashboard'].search([], limit=1)

        if not dashboard:
            dashboard = env['dynamic.dashboard'].sudo().create({
                'name': 'Dashboard Quản lý Văn bản & Hệ thống',
                'state': 'published',
                'is_default': True,
                'refresh_interval': 60,
            })

            doc_model = env['ir.model'].search([('model', '=', 'aidt.document')], limit=1)

            if doc_model:
                env['dynamic.dashboard.widget'].sudo().create({
                    'name': 'Tổng số Văn bản',
                    'dashboard_id': dashboard.id,
                    'widget_type': 'kpi',
                    'color_theme': 'primary',
                    'provider_type': 'odoo_model',
                    'model_id': doc_model.id,
                    'measure_json': '[{"field": "id", "aggregation": "count"}]',
                })
                env['dynamic.dashboard.widget'].sudo().create({
                    'name': 'Văn bản Mật trở lên',
                    'dashboard_id': dashboard.id,
                    'widget_type': 'kpi',
                    'color_theme': 'danger',
                    'provider_type': 'odoo_model',
                    'model_id': doc_model.id,
                    'domain_json': '[["secrecy", "!=", "thuong"]]',
                    'measure_json': '[{"field": "id", "aggregation": "count"}]',
                })
                env['dynamic.dashboard.widget'].sudo().create({
                    'name': 'Văn bản Theo Đơn vị',
                    'dashboard_id': dashboard.id,
                    'widget_type': 'bar_chart',
                    'color_theme': 'teal',
                    'provider_type': 'odoo_model',
                    'model_id': doc_model.id,
                    'dimension_json': '[{"field": "department_id", "type": "many2one"}]',
                    'measure_json': '[{"field": "id", "aggregation": "count"}]',
                })
                env['dynamic.dashboard.widget'].sudo().create({
                    'name': 'Danh sách Văn bản Mới nhất',
                    'dashboard_id': dashboard.id,
                    'widget_type': 'table',
                    'color_theme': 'info',
                    'provider_type': 'odoo_model',
                    'model_id': doc_model.id,
                    'measure_json': '[{"field": "name"}, {"field": "reference"}, {"field": "doc_type"}, {"field": "state"}]',
                })

            env['dynamic.dashboard.widget'].sudo().create({
                'name': 'Người dùng Hoạt động',
                'dashboard_id': dashboard.id,
                'widget_type': 'kpi',
                'color_theme': 'success',
                'provider_type': 'system_metric',
            })

        return dashboard

    @http.route('/dashboard/api/list', type='jsonrpc', auth='user', methods=['POST'], csrf=True)
    def get_user_dashboards(self):
        """Lấy danh sách các Dashboard mà người dùng hiện tại có quyền truy cập."""
        env = request.env
        user = env.user

        is_manager = user.has_group('aidt_dashboard_builder.group_dashboard_manager') or user._is_admin()

        dashboards = env['dynamic.dashboard'].search([])
        result = []

        for d in dashboards:
            is_owner = (d.owner_id.id == user.id)
            is_designer = (user.id in d.designer_ids.ids)
            is_published = (d.state == 'published')

            if is_manager or is_owner or is_designer:
                has_access = True
            elif is_published:
                if not (d.group_ids or d.viewer_ids):
                    has_access = True
                else:
                    has_access = (user.id in d.viewer_ids.ids) or bool(d.group_ids & user.groups_id)
            else:
                has_access = False

            if has_access:
                status_suffix = " (Dự thảo)" if d.state == 'draft' else ""
                result.append({
                    'id': d.id,
                    'name': f"{d.name}{status_suffix}",
                    'is_default': d.is_default,
                    'state': d.state,
                })

        return {
            'status': 'success',
            'dashboards': result
        }

    @http.route('/dashboard/api/data', type='jsonrpc', auth='user', methods=['POST'], csrf=True)
    def get_dashboard_data(self, dashboard_id=0, filter_values=None, force_refresh=False):
        """Batch loading endpoint cho toàn bộ Widgets của 1 Dashboard."""
        env = request.env
        user = env.user
        company_id = env.company.id

        dashboard = None
        if dashboard_id:
            dashboard = env['dynamic.dashboard'].search([('id', '=', dashboard_id)], limit=1)

        if not dashboard:
            dashboard = self._get_or_create_default_dashboard(env)

        if not dashboard:
            return {'status': 'error', 'message': 'Không thể khởi tạo Dashboard.'}

        cache_key = CacheService.generate_cache_key(dashboard.id, user.id, company_id, filter_values)

        if not force_refresh and dashboard.refresh_interval > 0:
            cached_data = CacheService.get_cache(env, cache_key)
            if cached_data:
                return {
                    'status': 'success',
                    'from_cache': True,
                    'dashboard_id': dashboard.id,
                    'dashboard_name': dashboard.name,
                    'pages': [{'id': p.id, 'name': p.name, 'icon': p.icon} for p in dashboard.page_ids],
                    'filters': [{'id': f.id, 'name': f.name, 'type': f.filter_type, 'required': f.required} for f in dashboard.filter_ids],
                    'data': cached_data
                }

        widget_results = {}
        widgets = dashboard.widget_ids.filtered(lambda w: w.active)

        for widget in widgets:
            try:
                provider = ProviderRegistry.get_provider(widget.provider_type)
                res = provider.fetch_data(env, widget, filter_values)
                res['name'] = widget.name
                res['widget_type'] = widget.widget_type
                res['color_theme'] = widget.color_theme or 'primary'
                res['custom_color'] = widget.custom_color or False
                res['page_id'] = widget.page_id.id if widget.page_id else False
                widget_results[widget.id] = res
            except Exception as e:
                _logger.exception("Lỗi khi tải dữ liệu cho Widget %s (ID: %s)", widget.name, widget.id)
                widget_results[widget.id] = {
                    'name': widget.name,
                    'type': widget.widget_type,
                    'color_theme': widget.color_theme or 'primary',
                    'custom_color': widget.custom_color or False,
                    'page_id': widget.page_id.id if widget.page_id else False,
                    'error': True,
                    'message': str(e)
                }

        if dashboard.refresh_interval > 0:
            CacheService.set_cache(
                env, cache_key, user.id, company_id, widget_results, ttl_seconds=dashboard.refresh_interval
            )

        pages = [{'id': p.id, 'name': p.name, 'icon': p.icon} for p in dashboard.page_ids]
        filters = [{'id': f.id, 'name': f.name, 'type': f.filter_type, 'required': f.required} for f in dashboard.filter_ids]

        return {
            'status': 'success',
            'from_cache': False,
            'dashboard_id': dashboard.id,
            'dashboard_name': dashboard.name,
            'pages': pages,
            'filters': filters,
            'data': widget_results
        }

    @http.route('/dashboard/api/metadata/models', type='jsonrpc', auth='user', methods=['POST'], csrf=True)
    def get_allowed_models(self):
        """Endpoint lấy danh sách models được phép truy cập cho UI Query Builder."""
        return {
            'status': 'success',
            'models': MetadataService.get_allowed_models(request.env)
        }

    @http.route('/dashboard/api/metadata/fields', type='jsonrpc', auth='user', methods=['POST'], csrf=True)
    def get_model_fields(self, model_name):
        """Endpoint lấy danh sách fields của model cho UI Query Builder."""
        return {
            'status': 'success',
            'model': model_name,
            'fields': MetadataService.get_model_fields(request.env, model_name)
        }
