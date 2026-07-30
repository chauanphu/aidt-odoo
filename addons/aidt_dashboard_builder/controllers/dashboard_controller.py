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
        filters = []
        for f in dashboard.filter_ids:
            f_item = {
                'id': f.id,
                'name': f.name,
                'type': f.filter_type,
                'required': f.required,
                'target_model': f.target_model_id.model if f.target_model_id else False,
                'options': []
            }
            if f.filter_type == 'company':
                f_item['options'] = [{'id': c.id, 'name': c.name} for c in env['res.company'].search([])]
            elif f.filter_type == 'department':
                if 'hr.department' in env:
                    f_item['options'] = [{'id': d.id, 'name': d.name} for d in env['hr.department'].search([])]
            elif f.filter_type == 'many2one' and f.target_model_id and f.target_model_id.model in env:
                try:
                    recs = env[f.target_model_id.model].search([], limit=100)
                    f_item['options'] = [{'id': r.id, 'name': r.display_name} for r in recs]
                except Exception:
                    pass
            elif f.filter_type == 'selection' and f.default_value_json:
                try:
                    f_item['options'] = json.loads(f.default_value_json)
                except Exception:
                    pass
            filters.append(f_item)

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

    @http.route('/dashboard/api/export/excel', type='jsonrpc', auth='user', methods=['POST'], csrf=True)
    def export_dashboard_excel(self, dashboard_id, filter_values=None):
        """Xuất Báo cáo Dashboard ra file Excel (.xlsx) đa sheet chuyên nghiệp chứa TẤT CẢ Widgets."""
        import io
        import base64
        import xlsxwriter

        env = request.env
        dashboard = env['dynamic.dashboard'].browse(int(dashboard_id))
        if not dashboard.exists():
            return {'status': 'error', 'message': 'Dashboard không tồn tại.'}

        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})

        # Style Formats
        title_fmt = workbook.add_format({
            'bold': True, 'font_size': 14, 'font_color': '#ffffff', 'bg_color': '#005b9a',
            'align': 'center', 'valign': 'vcenter'
        })
        section_fmt = workbook.add_format({
            'bold': True, 'font_size': 11, 'font_color': '#005b9a', 'bg_color': '#e6f0f7',
            'align': 'left', 'valign': 'vcenter', 'border': 1
        })
        header_fmt = workbook.add_format({
            'bold': True, 'font_size': 10, 'font_color': '#ffffff', 'bg_color': '#005b9a',
            'align': 'center', 'valign': 'vcenter', 'border': 1
        })
        cell_fmt = workbook.add_format({'font_size': 10, 'border': 1, 'valign': 'vcenter'})
        num_fmt = workbook.add_format({'font_size': 10, 'border': 1, 'align': 'right', 'num_format': '#,##0'})

        # Collect all active widgets across direct dashboard and all dashboard pages
        all_widgets = (dashboard.widget_ids | dashboard.page_ids.widget_ids).filtered(lambda w: w.active).sorted(key=lambda w: (w.sequence, w.id))

        # 1. SHEET 1: Tổng hợp Chỉ số KPI
        kpi_widgets = all_widgets.filtered(lambda w: w.widget_type == 'kpi')
        if kpi_widgets:
            ws_kpi = workbook.add_worksheet('Thẻ chỉ số KPI')
            ws_kpi.merge_range('A1:E1', f'BÁO CÁO CHỈ SỐ KPI: {dashboard.name.upper()}', title_fmt)
            ws_kpi.set_row(0, 32)
            ws_kpi.write_row(2, 0, ['STT', 'Tên Chỉ số / KPI', 'Model dữ liệu', 'Giá trị Hiển thị', 'So sánh Cùng kỳ'], header_fmt)
            ws_kpi.set_row(2, 24)
            ws_kpi.set_column('A:A', 8)
            ws_kpi.set_column('B:B', 34)
            ws_kpi.set_column('C:C', 24)
            ws_kpi.set_column('D:D', 22)
            ws_kpi.set_column('E:E', 28)

            for row, widget in enumerate(kpi_widgets, start=3):
                try:
                    w_data = ProviderRegistry.get_provider(widget.provider_type).fetch_data(env, widget, filter_values or {})
                except Exception:
                    w_data = {}
                val = w_data.get('formatted_value', '0')
                comp = w_data.get('comparison', {})
                comp_text = comp.get('text', 'N/A') if comp.get('enable') else 'N/A'

                ws_kpi.write(row, 0, row - 2, cell_fmt)
                ws_kpi.write(row, 1, widget.name, cell_fmt)
                ws_kpi.write(row, 2, widget.model_name or 'N/A', cell_fmt)
                ws_kpi.write(row, 3, val, num_fmt)
                ws_kpi.write(row, 4, comp_text, cell_fmt)

        # 2. SHEET 2: Dữ liệu Biểu đồ (Charts)
        chart_types = ('line_chart', 'bar_chart', 'horizontal_bar', 'pie_chart', 'donut_chart', 'area_chart')
        chart_widgets = all_widgets.filtered(lambda w: w.widget_type in chart_types)
        if chart_widgets:
            ws_chart = workbook.add_worksheet('Dữ liệu Biểu đồ')
            ws_chart.merge_range('A1:C1', f'DỮ LIỆU BIỂU ĐỒ & ĐỒ THỊ: {dashboard.name.upper()}', title_fmt)
            ws_chart.set_row(0, 32)
            ws_chart.set_column('A:A', 8)
            ws_chart.set_column('B:B', 38)
            ws_chart.set_column('C:C', 22)

            c_row = 2
            for widget in chart_widgets:
                try:
                    w_data = ProviderRegistry.get_provider(widget.provider_type).fetch_data(env, widget, filter_values or {})
                except Exception:
                    w_data = {}

                labels = w_data.get('labels', [])
                datasets = w_data.get('datasets', [])
                values = datasets[0].get('data', []) if datasets else []

                type_label = widget.widget_type.replace('_chart', '').replace('_', ' ').title()
                ws_chart.merge_range(c_row, 0, c_row, 2, f'📊 [{type_label}] {widget.name}', section_fmt)
                ws_chart.set_row(c_row, 22)
                c_row += 1

                ws_chart.write_row(c_row, 0, ['STT', 'Nhóm / Nhãn (Label)', 'Giá trị (Value)'], header_fmt)
                ws_chart.set_row(c_row, 24)
                c_row += 1

                if labels and values:
                    for i, (lbl, val) in enumerate(zip(labels, values), start=1):
                        ws_chart.write(c_row, 0, i, cell_fmt)
                        ws_chart.write(c_row, 1, str(lbl), cell_fmt)
                        ws_chart.write(c_row, 2, val, num_fmt)
                        c_row += 1
                else:
                    ws_chart.merge_range(c_row, 0, c_row, 2, 'Không có dữ liệu', cell_fmt)
                    c_row += 1
                c_row += 1

        # 3. SHEET 3..N: Bảng dữ liệu Chi tiết (Table Widgets)
        table_widgets = all_widgets.filtered(lambda w: w.widget_type == 'table')
        used_names = set()
        for widget in table_widgets:
            try:
                w_data = ProviderRegistry.get_provider(widget.provider_type).fetch_data(env, widget, filter_values or {})
            except Exception:
                w_data = {}

            clean_name = (widget.name or 'Bảng Dữ Liệu').replace(':', '_').replace('/', '_').replace('\\', '_')
            sheet_name = clean_name[:28]
            if sheet_name in used_names:
                sheet_name = f"{sheet_name[:24]}_{widget.id}"
            used_names.add(sheet_name)

            ws_tbl = workbook.add_worksheet(sheet_name)

            field_headers = w_data.get('field_headers') or [{'field': f, 'string': f} for f in w_data.get('fields', [])]
            records = w_data.get('records', [])

            col_count = max(len(field_headers), 4)
            ws_tbl.merge_range(0, 0, 0, col_count - 1, f'BẢNG DỮ LIỆU CHI TIẾT: {widget.name.upper()}', title_fmt)
            ws_tbl.set_row(0, 32)

            if field_headers:
                header_titles = ['STT'] + [h.get('string') or h.get('field') for h in field_headers]
                ws_tbl.write_row(2, 0, header_titles, header_fmt)
                ws_tbl.set_row(2, 24)
                ws_tbl.set_column(0, 0, 8)
                for c_idx, h in enumerate(field_headers, start=1):
                    lbl = h.get('string') or h.get('field')
                    ws_tbl.set_column(c_idx, c_idx, max(18, len(str(lbl)) + 4))

                if records:
                    for r_idx, r_data in enumerate(records, start=3):
                        ws_tbl.write(r_idx, 0, r_idx - 2, cell_fmt)
                        for c_idx, h in enumerate(field_headers, start=1):
                            fname = h.get('field')
                            val = r_data.get(fname, '')
                            ws_tbl.write(r_idx, c_idx, str(val) if val is not None else '', cell_fmt)
                else:
                    ws_tbl.merge_range(3, 0, 3, col_count - 1, 'Chưa có bản ghi dữ liệu', cell_fmt)

        # 4. SHEET N+1: Hoạt động & Phím tắt
        other_widgets = all_widgets.filtered(lambda w: w.widget_type in ('activity', 'shortcut'))
        if other_widgets:
            ws_other = workbook.add_worksheet('Hoạt động & Phím tắt')
            ws_other.merge_range('A1:D1', f'DANH SÁCH HOẠT ĐỘNG & PHÍM TẮT: {dashboard.name.upper()}', title_fmt)
            ws_other.set_row(0, 32)
            ws_other.set_column('A:A', 8)
            ws_other.set_column('B:B', 35)
            ws_other.set_column('C:C', 25)
            ws_other.set_column('D:D', 20)

            o_row = 2
            for widget in other_widgets:
                try:
                    w_data = ProviderRegistry.get_provider(widget.provider_type).fetch_data(env, widget, filter_values or {})
                except Exception:
                    w_data = {}

                type_label = 'Hoạt Động Gần Đây' if widget.widget_type == 'activity' else 'Phím Tắt Mở Nhanh'
                ws_other.merge_range(o_row, 0, o_row, 3, f'📌 [{type_label}] {widget.name}', section_fmt)
                ws_other.set_row(o_row, 22)
                o_row += 1

                if widget.widget_type == 'activity':
                    activities = w_data.get('activities', [])
                    if activities:
                        ws_other.write_row(o_row, 0, ['STT', 'Tiêu đề Hoạt động / Bản ghi', 'Người thực hiện', 'Thời gian'], header_fmt)
                        ws_other.set_row(o_row, 24)
                        o_row += 1
                        for idx, act in enumerate(activities, start=1):
                            ws_other.write(o_row, 0, idx, cell_fmt)
                            ws_other.write(o_row, 1, str(act.get('name', '')), cell_fmt)
                            ws_other.write(o_row, 2, str(act.get('user', 'Hệ thống')), cell_fmt)
                            ws_other.write(o_row, 3, str(act.get('time', '')), cell_fmt)
                            o_row += 1
                    else:
                        ws_other.merge_range(o_row, 0, o_row, 3, 'Chưa có hoạt động mới', cell_fmt)
                        o_row += 1
                else:  # shortcut
                    action_name = w_data.get('action_name') or 'Mở ứng dụng'
                    ws_other.write_row(o_row, 0, ['STT', 'Tên Phím Tắt', 'Hành động mở', 'Icon'], header_fmt)
                    ws_other.set_row(o_row, 24)
                    o_row += 1
                    ws_other.write(o_row, 0, 1, cell_fmt)
                    ws_other.write(o_row, 1, widget.name, cell_fmt)
                    ws_other.write(o_row, 2, action_name, cell_fmt)
                    ws_other.write(o_row, 3, widget.icon or 'fa-external-link', cell_fmt)
                    o_row += 1

                o_row += 1

        workbook.close()
        output.seek(0)
        file_base64 = base64.b64encode(output.read()).decode('utf-8')

        return {
            'status': 'success',
            'filename': f"Dashboard_{dashboard.name.replace(' ', '_')}.xlsx",
            'file_base64': file_base64
        }

