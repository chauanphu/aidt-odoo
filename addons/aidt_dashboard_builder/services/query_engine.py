import json
import logging
from odoo.exceptions import UserError, AccessError
from .query_validator import QueryValidator
from .domain_compiler import DomainCompiler

_logger = logging.getLogger(__name__)


class QueryEngine:
    @classmethod
    def execute_widget_query(cls, env, widget, filter_values=None):
        """Thực thi truy vấn cho 1 Widget theo chuẩn bảo mật và hiệu năng ORM."""
        if not widget.model_id or not widget.model_name:
            return {
                'type': widget.widget_type,
                'widget_type': widget.widget_type,
                'value': 0,
                'data': [],
                'icon': widget.icon or 'fa-line-chart'
            }

        try:
            # 1. Validation Model & Field Security
            model_obj = QueryValidator.validate_model_access(env, widget.model_name)

            # 2. Compile Domain
            domain = DomainCompiler.compile_domain(env, widget.domain_json, filter_values)

            # 3. Phân loại loại Widget và thực hiện tính toán
            w_type = widget.widget_type

            if w_type == 'kpi':
                res = cls._execute_kpi_query(env, model_obj, widget, domain)
            elif w_type in ('line_chart', 'bar_chart', 'horizontal_bar', 'pie_chart', 'donut_chart', 'area_chart'):
                res = cls._execute_chart_query(env, model_obj, widget, domain)
            elif w_type == 'table':
                res = cls._execute_table_query(env, model_obj, widget, domain)
            elif w_type == 'activity':
                res = cls._execute_activity_query(env, model_obj, widget, domain)
            else:
                res = {'type': w_type, 'value': 0, 'data': []}

            res['widget_type'] = w_type
            res['icon'] = widget.icon or cls._get_default_icon(w_type)
            res['model_name'] = widget.model_name
            res['domain'] = domain
            res['drilldown_action_id'] = widget.drilldown_action_id.id if widget.drilldown_action_id else False
            return res

        except Exception as e:
            _logger.exception("Lỗi khi thực thi QueryEngine cho widget %s (ID: %s)", widget.name, widget.id)
            return {
                'type': widget.widget_type,
                'widget_type': widget.widget_type,
                'error': True,
                'message': str(e),
                'icon': widget.icon or 'fa-exclamation-triangle'
            }

    @classmethod
    def _get_default_icon(cls, widget_type):
        icon_map = {
            'kpi': 'fa-tachometer',
            'line_chart': 'fa-line-chart',
            'bar_chart': 'fa-bar-chart',
            'horizontal_bar': 'fa-align-left',
            'pie_chart': 'fa-pie-chart',
            'donut_chart': 'fa-circle-o-notch',
            'area_chart': 'fa-area-chart',
            'table': 'fa-table',
            'activity': 'fa-history',
            'shortcut': 'fa-external-link',
        }
        return icon_map.get(widget_type, 'fa-cube')

    @classmethod
    def _execute_kpi_query(cls, env, model_obj, widget, domain):
        """Xử lý truy vấn cho KPI Card."""
        try:
            measures = json.loads(widget.measure_json) if widget.measure_json else []
        except Exception:
            measures = []

        if not measures:
            count = model_obj.search_count(domain)
            return {'type': 'kpi', 'value': count, 'formatted_value': f"{count:,}"}

        measure = measures[0]
        field_name = measure.get('field')
        agg = measure.get('aggregation', 'count')

        if agg == 'count' or not field_name or field_name == 'id':
            count = model_obj.search_count(domain)
            return {'type': 'kpi', 'value': count, 'formatted_value': f"{count:,}"}

        QueryValidator.validate_field(model_obj, field_name)

        groupby = []
        aggregates = [f"{field_name}:{agg}"]
        result = model_obj._read_group(domain, groupby=groupby, aggregates=aggregates)

        val = result[0][0] if result and result[0] and result[0][0] is not None else 0
        if isinstance(val, float):
            formatted_val = f"{val:,.2f}"
        else:
            formatted_val = f"{val:,}"

        return {'type': 'kpi', 'value': val, 'formatted_value': formatted_val}

    @classmethod
    def _execute_chart_query(cls, env, model_obj, widget, domain):
        """Xử lý truy vấn gom nhóm cho các loại Biểu đồ (Charts)."""
        try:
            dimensions = json.loads(widget.dimension_json) if widget.dimension_json else []
            measures = json.loads(widget.measure_json) if widget.measure_json else []
        except Exception:
            dimensions, measures = [], []

        if not dimensions:
            return {'type': widget.widget_type, 'labels': [], 'datasets': [], 'group_domains': []}

        groupby_field = dimensions[0].get('field')
        granularity = dimensions[0].get('granularity', 'month')

        QueryValidator.validate_field(model_obj, groupby_field)

        field_type = model_obj._fields[groupby_field].type if groupby_field in model_obj._fields else 'char'
        if field_type in ('date', 'datetime'):
            groupby_expr = f"{groupby_field}:{granularity}"
        else:
            groupby_expr = groupby_field

        measure_field = measures[0].get('field', 'id') if measures else 'id'
        agg = measures[0].get('aggregation', 'count') if measures else 'count'

        if measure_field != 'id':
            QueryValidator.validate_field(model_obj, measure_field)

        aggregate_expr = f"{measure_field}:{agg}"
        limit_val = widget.limit or 20
        groups = model_obj._read_group(domain, groupby=[groupby_expr], aggregates=[aggregate_expr], limit=limit_val)

        labels = []
        values = []
        group_domains = []

        for grp in groups:
            lbl = grp[0]
            val = grp[1] if grp[1] is not None else 0

            lbl_str = 'Chưa xác định'
            grp_domain_el = None

            if isinstance(lbl, tuple):
                grp_domain_el = (groupby_field, '=', lbl[0])
                lbl_str = lbl[1] if len(lbl) > 1 else str(lbl[0])
            elif hasattr(lbl, 'id'):
                grp_domain_el = (groupby_field, '=', lbl.id)
                lbl_str = getattr(lbl, 'display_name', str(lbl.id))
            elif lbl is None or lbl is False:
                grp_domain_el = (groupby_field, '=', False)
                lbl_str = 'Chưa xác định'
            else:
                grp_domain_el = (groupby_field, '=', lbl)
                lbl_str = str(lbl)

            labels.append(lbl_str)
            values.append(val)
            group_domains.append(grp_domain_el)

        return {
            'type': widget.widget_type,
            'labels': labels,
            'group_domains': group_domains,
            'datasets': [{
                'label': widget.name,
                'data': values
            }]
        }

    @classmethod
    def _execute_table_query(cls, env, model_obj, widget, domain):
        """Xử lý truy vấn danh sách dữ liệu cho Bảng (Table)."""
        try:
            measures = json.loads(widget.measure_json) if widget.measure_json else []
        except Exception:
            measures = []

        raw_fields = [m.get('field') for m in measures if m.get('field')]
        valid_fields = [f for f in raw_fields if f in model_obj._fields]

        if not valid_fields:
            valid_fields = ['id', 'display_name'] if 'display_name' in model_obj._fields else ['id', 'name']
            valid_fields = [f for f in valid_fields if f in model_obj._fields]
        else:
            if 'id' not in valid_fields and 'id' in model_obj._fields:
                valid_fields.append('id')
            if 'display_name' not in valid_fields and 'display_name' in model_obj._fields:
                valid_fields.append('display_name')

        for fname in valid_fields:
            QueryValidator.validate_field(model_obj, fname)

        limit_val = widget.limit or 5
        records = model_obj.search_read(domain, fields=valid_fields, limit=limit_val)

        # Xử lý tiêu đề cột có nhãn tiếng Việt / string từ Odoo Metadata
        field_headers = []
        for fname in valid_fields:
            if fname in model_obj._fields:
                field_headers.append({
                    'field': fname,
                    'string': model_obj._fields[fname].string or fname,
                    'type': model_obj._fields[fname].type,
                })

        # Format các giá trị (many2one, selection, date...) để hiển thị đẹp mắt
        formatted_records = []
        for r in records:
            row_data = {'id': r.get('id')}
            for fh in field_headers:
                fname = fh['field']
                val = r.get(fname)
                if isinstance(val, (list, tuple)) and len(val) == 2:
                    row_data[fname] = val[1]  # Lấy display_name của Many2one
                elif val is False or val is None:
                    row_data[fname] = '-'
                else:
                    row_data[fname] = str(val)
            formatted_records.append(row_data)

        return {
            'type': 'table',
            'records': formatted_records,
            'fields': [fh['field'] for fh in field_headers],
            'field_headers': field_headers,
            'model_name': widget.model_name,
            'limit': limit_val,
            'drilldown_action_id': widget.drilldown_action_id.id if widget.drilldown_action_id else False
        }

    @classmethod
    def _execute_activity_query(cls, env, model_obj, widget, domain):
        """Xử lý truy vấn Hoạt động Gần đây (Recent Activities)."""
        limit_val = widget.limit or 5
        records = model_obj.search(domain, limit=limit_val, order='id desc')

        activities = []
        for r in records:
            time_str = r.write_date.strftime('%H:%M %d/%m') if hasattr(r, 'write_date') and r.write_date else ''
            user_name = r.create_uid.name if hasattr(r, 'create_uid') and r.create_uid else 'Hệ thống'
            rec_title = r.display_name if hasattr(r, 'display_name') and r.display_name else (r.name if hasattr(r, 'name') else f"Bản ghi #{r.id}")

            activities.append({
                'id': r.id,
                'name': rec_title,
                'user': user_name,
                'time': time_str,
                'model_name': widget.model_name,
            })

        return {
            'type': 'activity',
            'activities': activities,
            'model_name': widget.model_name,
        }
