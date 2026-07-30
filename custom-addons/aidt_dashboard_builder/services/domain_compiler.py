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
    def compile_domain(cls, env, domain_raw, filter_values=None, widget=None):
        """Biến đổi JSON Domain thành Odoo Domain chuẩn hợp lệ."""
        if not domain_raw:
            domain_list = []
        elif isinstance(domain_raw, str):
            try:
                domain_list = json.loads(domain_raw)
            except Exception:
                domain_list = []
        else:
            domain_list = domain_raw

        if not isinstance(domain_list, list):
            domain_list = []

        compiled_domain = []

        for item in domain_list:
            if isinstance(item, (list, tuple)) and len(item) == 3:
                field, op, val = item
                resolved_val = cls.resolve_dynamic_value(env, val)
                compiled_domain.append((field, op, resolved_val))
            elif isinstance(item, str) and item in ('|', '&', '!'):
                compiled_domain.append(item)

        if filter_values and isinstance(filter_values, dict):
            # Process date_pill master filter
            date_pill = filter_values.get('date_pill')
            if date_pill and date_pill != 'all':
                today = date.today()
                if date_pill == 'today':
                    compiled_domain.extend([('create_date', '>=', today.strftime(DEFAULT_SERVER_DATE_FORMAT))])
                elif date_pill == 'this_week':
                    start_w = today - relativedelta(days=today.weekday())
                    compiled_domain.extend([('create_date', '>=', start_w.strftime(DEFAULT_SERVER_DATE_FORMAT))])
                elif date_pill == 'this_month':
                    start_m = today.replace(day=1)
                    compiled_domain.extend([('create_date', '>=', start_m.strftime(DEFAULT_SERVER_DATE_FORMAT))])
                elif date_pill == 'this_quarter':
                    q_month = 3 * ((today.month - 1) // 3) + 1
                    start_q = today.replace(month=q_month, day=1)
                    compiled_domain.extend([('create_date', '>=', start_q.strftime(DEFAULT_SERVER_DATE_FORMAT))])
                elif date_pill == 'this_year':
                    start_y = today.replace(month=1, day=1)
                    compiled_domain.extend([('create_date', '>=', start_y.strftime(DEFAULT_SERVER_DATE_FORMAT))])

            for f_key, val in filter_values.items():
                if f_key == 'date_pill' or val is None or val == '':
                    continue

                resolved_val = cls.resolve_dynamic_value(env, val)
                if isinstance(resolved_val, str) and resolved_val.isdigit():
                    resolved_val = int(resolved_val)

                target_field = None

                # 1. Check explicit filter binding
                if widget and hasattr(widget, 'dashboard_id') and widget.dashboard_id:
                    filter_domain = [('dashboard_id', '=', widget.dashboard_id.id)]
                    if str(f_key).isdigit():
                        filter_domain.append(('id', '=', int(f_key)))
                    else:
                        filter_domain.append(('name', '=', str(f_key)))

                    filter_rec = env['dynamic.dashboard.filter'].search(filter_domain, limit=1)
                    if filter_rec:
                        binding = env['dynamic.dashboard.filter.binding'].search([
                            ('filter_id', '=', filter_rec.id),
                            ('widget_id', '=', widget.id)
                        ], limit=1)
                        if binding and binding.field_name:
                            target_field = binding.field_name
                        elif filter_rec.filter_type == 'company':
                            target_field = 'company_id'
                        elif filter_rec.filter_type == 'department':
                            target_field = 'department_id'

                # 2. Smart fallback if no binding was configured
                if not target_field:
                    if f_key in ('company_id', 'company'):
                        target_field = 'company_id'
                    elif f_key in ('department_id', 'department'):
                        target_field = 'department_id'
                    else:
                        target_field = str(f_key)

                # 3. Append to domain if model has field
                if widget and widget.model_name and widget.model_name in env:
                    model_fields = env[widget.model_name]._fields
                    if target_field in model_fields:
                        if isinstance(resolved_val, list):
                            compiled_domain.append((target_field, 'in', resolved_val))
                        else:
                            compiled_domain.append((target_field, '=', resolved_val))
                elif not widget:
                    if isinstance(resolved_val, list):
                        compiled_domain.append((target_field, 'in', resolved_val))
                    else:
                        compiled_domain.append((target_field, '=', resolved_val))

        return compiled_domain
