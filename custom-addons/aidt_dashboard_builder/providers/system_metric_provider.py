from .base_provider import BaseProvider


class SystemMetricProvider(BaseProvider):
    """Provider cho các chỉ số hệ thống (Active Users, Departments, System Status)."""

    def fetch_data(self, env, widget, filter_values=None):
        metric_key = widget.name.lower()

        if 'user' in metric_key or 'người dùng' in metric_key:
            count = env['res.users'].search_count([('active', '=', True)])
            return {'type': 'kpi', 'value': count, 'formatted_value': f"{count:,}"}
        elif 'department' in metric_key or 'đơn vị' in metric_key or 'phòng ban' in metric_key:
            count = env['hr.department'].search_count([])
            return {'type': 'kpi', 'value': count, 'formatted_value': f"{count:,}"}
        else:
            return {'type': 'kpi', 'value': 1, 'formatted_value': 'Hoạt động'}
