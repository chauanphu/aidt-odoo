import json
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
                    'sequence': 10,
                    'col_size': '3',
                    'position_json': '{"x":3,"y":0,"w":3,"h":2}',
                    'widget_type': 'kpi',
                    'color_theme': 'primary',
                    'provider_type': 'odoo_model',
                    'model_id': doc_model.id,
                    'measure_json': '[{"field": "id", "aggregation": "count"}]',
                })
                env['dynamic.dashboard.widget'].sudo().create({
                    'name': 'Văn bản Mật trở lên',
                    'dashboard_id': dashboard.id,
                    'sequence': 0,
                    'col_size': '3',
                    'position_json': '{"x":0,"y":0,"w":3,"h":2}',
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
                    'sequence': 6,
                    'col_size': '6',
                    'position_json': '{"x":6,"y":0,"w":6,"h":4}',
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
                    'sequence': 24,
                    'col_size': '6',
                    'position_json': '{"x":0,"y":2,"w":6,"h":4}',
                    'widget_type': 'table',
                    'color_theme': 'info',
                    'provider_type': 'odoo_model',
                    'model_id': doc_model.id,
                    'measure_json': '[{"field": "name"}, {"field": "reference"}, {"field": "doc_type"}, {"field": "state"}]',
                })

            env['dynamic.dashboard.widget'].sudo().create({
                'name': 'Người dùng Hoạt động',
                'dashboard_id': dashboard.id,
                'sequence': 72,
                'col_size': '12',
                'position_json': '{"x":0,"y":6,"w":12,"h":2}',
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

        try:
            is_manager = user.has_group('aidt_dashboard_builder.group_dashboard_manager') or user.has_group('aidt_dashboard_builder.group_dashboard_admin') or user._is_admin()
            dashboards = env['dynamic.dashboard'].sudo().search([])
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
        except Exception as e:
            _logger.warning("Không thể tải danh sách Dashboard cho user %s: %s", user.id, e)
            return {'status': 'access_denied', 'message': 'Tài khoản của bạn chưa được phân quyền xem Dashboard.', 'dashboards': []}

    @http.route('/dashboard/api/data', type='jsonrpc', auth='user', methods=['POST'], csrf=True)
    def get_dashboard_data(self, dashboard_id=0, filter_values=None, force_refresh=False):
        """Batch loading endpoint cho toàn bộ Widgets của 1 Dashboard."""
        env = request.env
        user = env.user
        company_id = env.company.id

        try:
            dashboard = None
            if dashboard_id:
                dashboard = env['dynamic.dashboard'].sudo().search([('id', '=', dashboard_id)], limit=1)

            if not dashboard:
                dashboard = self._get_or_create_default_dashboard(env)

            if not dashboard:
                return {'status': 'access_denied', 'message': 'Chưa có Dashboard nào được khởi tạo hoặc xuất bản.'}
        except Exception as e:
            _logger.warning("Lỗi truy cập Dashboard cho user %s: %s", user.id, e)
            return {'status': 'access_denied', 'message': 'Tài khoản của bạn chưa được phân quyền xem Dashboard.'}

        # Nạp cấu hình User Custom Layout nếu có
        user_layout_map = {}
        user_layout_rec = env['dynamic.dashboard.user.layout'].search([
            ('user_id', '=', user.id),
            ('dashboard_id', '=', dashboard.id)
        ], limit=1)

        if user_layout_rec and user_layout_rec.layout_json:
            try:
                user_layout_map = json.loads(user_layout_rec.layout_json)
            except Exception:
                user_layout_map = {}

        cache_key = CacheService.generate_cache_key(dashboard.id, user.id, company_id, filter_values)

        if not force_refresh and dashboard.refresh_interval > 0:
            cached_data = CacheService.get_cache(env, cache_key)
            if cached_data:
                return {
                    'status': 'success',
                    'from_cache': True,
                    'dashboard_id': dashboard.id,
                    'dashboard_name': dashboard.name,
                    'has_custom_layout': bool(user_layout_rec),
                    'pages': [{'id': p.id, 'name': p.name, 'icon': p.icon} for p in dashboard.page_ids],
                    'filters': [{'id': f.id, 'name': f.name, 'type': f.filter_type, 'required': f.required} for f in dashboard.filter_ids],
                    'data': cached_data
                }

        widget_results = {}
        widgets = dashboard.widget_ids.filtered(lambda w: w.active)

        for widget in widgets:
            w_custom = user_layout_map.get(str(widget.id)) or user_layout_map.get(widget.id) or {}
            seq = int(w_custom.get('sequence')) if w_custom.get('sequence') is not None else widget.sequence
            col = str(w_custom.get('col_size')) if w_custom.get('col_size') is not None else str(widget.col_size or '4')
            pos = w_custom.get('position_json') if w_custom.get('position_json') is not None else (widget.position_json or '{}')

            if isinstance(pos, dict):
                pos = json.dumps(pos)

            try:
                provider = ProviderRegistry.get_provider(widget.provider_type)
                res = provider.fetch_data(env, widget, filter_values)
                res['name'] = widget.name
                res['widget_type'] = widget.widget_type
                res['type'] = widget.widget_type
                res['sequence'] = seq
                res['col_size'] = col
                res['position_json'] = pos
                res['color_theme'] = widget.color_theme or 'primary'
                res['custom_color'] = widget.custom_color or False
                res['icon'] = widget.icon or res.get('icon') or 'fa-cube'
                res['page_id'] = widget.page_id.id if widget.page_id else False
                res['model_name'] = res.get('model_name') or widget.model_name
                res['drilldown_action_id'] = res.get('drilldown_action_id') or (widget.drilldown_action_id.id if widget.drilldown_action_id else False)
                widget_results[widget.id] = res
            except Exception as e:
                _logger.exception("Lỗi khi tải dữ liệu cho Widget %s (ID: %s)", widget.name, widget.id)
                widget_results[widget.id] = {
                    'name': widget.name,
                    'type': widget.widget_type,
                    'widget_type': widget.widget_type,
                    'sequence': seq,
                    'col_size': col,
                    'position_json': pos,
                    'color_theme': widget.color_theme or 'primary',
                    'custom_color': widget.custom_color or False,
                    'icon': widget.icon or 'fa-exclamation-triangle',
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
            'has_custom_layout': bool(user_layout_rec),
            'pages': pages,
            'filters': filters,
            'data': widget_results
        }

    @http.route('/dashboard/api/layout/save', type='jsonrpc', auth='user', methods=['POST'], csrf=True)
    def save_dashboard_layout(self, dashboard_id, widgets_layout, is_global=False):
        """Lưu thứ tự & độ rộng Widget (cho User cá nhân hoặc Global Admin)."""
        env = request.env
        user = env.user

        if not dashboard_id or not isinstance(widgets_layout, list):
            return {'status': 'error', 'message': 'Tham số dữ liệu không hợp lệ.'}

        dashboard = env['dynamic.dashboard'].search([('id', '=', dashboard_id)], limit=1)
        if not dashboard:
            return {'status': 'error', 'message': 'Không tìm thấy Dashboard.'}

        is_designer = user.has_group('aidt_dashboard_builder.group_dashboard_designer') or user.has_group('aidt_dashboard_builder.group_dashboard_manager') or user._is_admin()

        if is_global and is_designer:
            for w_item in widgets_layout:
                w_id = w_item.get('id')
                seq = int(w_item.get('sequence', 10))
                col = str(w_item.get('col_size', '4'))
                pos = w_item.get('position_json', '{}')

                widget = env['dynamic.dashboard.widget'].search([
                    ('id', '=', w_id), ('dashboard_id', '=', dashboard.id)
                ], limit=1)

                if widget:
                    widget.write({
                        'sequence': seq,
                        'col_size': col,
                        'position_json': pos if isinstance(pos, str) else json.dumps(pos)
                    })
            # Clear all user layout overrides so everyone sees the updated global master layout
            user_layouts = env['dynamic.dashboard.user.layout'].search([('dashboard_id', '=', dashboard.id)])
            if user_layouts:
                user_layouts.unlink()

            CacheService.invalidate_dashboard_cache(env, dashboard.id)
            return {'status': 'success', 'message': 'Đã lưu cấu hình Layout chung thành công cho tất cả người dùng.'}

        else:
            layout_data = {}
            for w_item in widgets_layout:
                w_id = str(w_item.get('id'))
                pos = w_item.get('position_json', '{}')
                layout_data[w_id] = {
                    'sequence': int(w_item.get('sequence', 10)),
                    'col_size': str(w_item.get('col_size', '4')),
                    'position_json': pos if isinstance(pos, str) else json.dumps(pos)
                }

            user_layout = env['dynamic.dashboard.user.layout'].search([
                ('user_id', '=', user.id),
                ('dashboard_id', '=', dashboard.id)
            ], limit=1)

            if user_layout:
                user_layout.write({'layout_json': json.dumps(layout_data)})
            else:
                env['dynamic.dashboard.user.layout'].create({
                    'user_id': user.id,
                    'dashboard_id': dashboard.id,
                    'layout_json': json.dumps(layout_data)
                })

            CacheService.invalidate_dashboard_cache(env, dashboard.id)
            return {'status': 'success', 'message': 'Đã lưu cấu hình Layout cá nhân thành công.'}

    @http.route('/dashboard/api/layout/reset', type='jsonrpc', auth='user', methods=['POST'], csrf=True)
    def reset_dashboard_layout(self, dashboard_id):
        """Khôi phục Layout cá nhân về mặc định của Admin."""
        env = request.env
        user = env.user

        user_layout = env['dynamic.dashboard.user.layout'].search([
            ('user_id', '=', user.id),
            ('dashboard_id', '=', dashboard_id)
        ], limit=1)

        if user_layout:
            user_layout.unlink()

        CacheService.invalidate_dashboard_cache(env, dashboard_id)
        return {'status': 'success', 'message': 'Đã khôi phục Layout về mặc định.'}

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
