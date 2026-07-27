import json
import logging
from odoo.exceptions import UserError
from .query_validator import QueryValidator
from .domain_compiler import DomainCompiler

_logger = logging.getLogger(__name__)


class QueryEngine:
    @classmethod
    def execute_widget_query(cls, env, widget, filter_values=None):
        """Thực thi truy vấn cho 1 Widget theo chuẩn bảo mật và hiệu năng ORM."""
        if not widget.model_id or not widget.model_name:
            return {'type': widget.widget_type, 'value': 0, 'data': []}

        # 1. Validation Model & Field Security
        model_obj = QueryValidator.validate_model_access(env, widget.model_name)

        # 2. Compile Domain
        domain = DomainCompiler.compile_domain(env, widget.domain_json, filter_values)

        # 3. Phân loại loại Widget và thực hiện tính toán
        w_type = widget.widget_type

        if w_type == 'kpi':
            return cls._execute_kpi_query(env, model_obj, widget, domain)
        elif w_type in ('line_chart', 'bar_chart', 'horizontal_bar', 'pie_chart', 'donut_chart', 'area_chart'):
            return cls._execute_chart_query(env, model_obj, widget, domain)
        elif w_type == 'table':
            return cls._execute_table_query(env, model_obj, widget, domain)
        else:
            return {'type': w_type, 'value': 0, 'data': []}

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

        if agg == 'count' or not field_name:
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
            return {'type': widget.widget_type, 'labels': [], 'datasets': []}

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

        for grp in groups:
            lbl = grp[0]
            if isinstance(lbl, tuple):
                lbl = lbl[1]
            elif hasattr(lbl, 'display_name'):
                lbl = lbl.display_name
            elif lbl is None or lbl is False:
                lbl = 'Chưa xác định'

            val = grp[1] if grp[1] is not None else 0
            labels.append(str(lbl))
            values.append(val)

        return {
            'type': widget.widget_type,
            'labels': labels,
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

        fields_to_read = [m.get('field') for m in measures if m.get('field')]
        if not fields_to_read:
            fields_to_read = ['id', 'display_name']
        else:
            if 'id' not in fields_to_read:
                fields_to_read.append('id')
            if 'display_name' not in fields_to_read and 'name' in model_obj._fields:
                fields_to_read.append('display_name')

        for fname in fields_to_read:
            QueryValidator.validate_field(model_obj, fname)

        limit_val = widget.limit or 5
        records = model_obj.search_read(domain, fields=fields_to_read, limit=limit_val)
        return {
            'type': 'table',
            'records': records,
            'fields': fields_to_read,
            'model_name': widget.model_name,
            'limit': limit_val,
            'drilldown_action_id': widget.drilldown_action_id.id if widget.drilldown_action_id else False
        }
