import json
from datetime import datetime, date
from dateutil.relativedelta import relativedelta
from odoo.tools import DEFAULT_SERVER_DATE_FORMAT, DEFAULT_SERVER_DATETIME_FORMAT


class DomainCompiler:
    @staticmethod
    def resolve_dynamic_value(env, value):
        """Giải mã các biến động như $user_id, $company_id, $start_of_month, $today..."""
        if not isinstance(value, str):
            return value

        today = date.today()
        now = datetime.now()
        start_of_week = today - relativedelta(days=today.weekday())

        # Xác định quý hiện tại
        quarter_month = 3 * ((today.month - 1) // 3) + 1
        start_of_quarter = today.replace(month=quarter_month, day=1)

        dynamic_map = {
            '$user_id': env.user.id,
            '$company_id': env.company.id,
            '$today': today.strftime(DEFAULT_SERVER_DATE_FORMAT),
            '$now': now.strftime(DEFAULT_SERVER_DATETIME_FORMAT),
            '$start_of_week': start_of_week.strftime(DEFAULT_SERVER_DATE_FORMAT),
            '$start_of_month': today.replace(day=1).strftime(DEFAULT_SERVER_DATE_FORMAT),
            '$end_of_month': (today.replace(day=1) + relativedelta(months=1, days=-1)).strftime(DEFAULT_SERVER_DATE_FORMAT),
            '$start_of_quarter': start_of_quarter.strftime(DEFAULT_SERVER_DATE_FORMAT),
            '$start_of_year': today.replace(month=1, day=1).strftime(DEFAULT_SERVER_DATE_FORMAT),
            '$end_of_year': today.replace(month=12, day=31).strftime(DEFAULT_SERVER_DATE_FORMAT),
            '$last_30_days': (today - relativedelta(days=30)).strftime(DEFAULT_SERVER_DATE_FORMAT),
        }

        return dynamic_map.get(value, value)

    @classmethod
    def compile_domain(cls, env, domain_raw, filter_values=None):
        """Biến đổi JSON Domain thành Odoo Domain chuẩn hợp lệ."""
        if not domain_raw:
            return []

        if isinstance(domain_raw, str):
            try:
                domain_list = json.loads(domain_raw)
            except Exception:
                return []
        else:
            domain_list = domain_raw

        if not isinstance(domain_list, list):
            return []

        compiled_domain = []

        for item in domain_list:
            if isinstance(item, (list, tuple)) and len(item) == 3:
                field, op, val = item
                resolved_val = cls.resolve_dynamic_value(env, val)
                compiled_domain.append((field, op, resolved_val))
            elif isinstance(item, str) and item in ('|', '&', '!'):
                compiled_domain.append(item)

        if filter_values and isinstance(filter_values, dict):
            for fname, val in filter_values.items():
                if val is not None and val != '':
                    resolved_val = cls.resolve_dynamic_value(env, val)
                    if isinstance(resolved_val, list):
                        compiled_domain.append((fname, 'in', resolved_val))
                    else:
                        compiled_domain.append((fname, '=', resolved_val))

        return compiled_domain
