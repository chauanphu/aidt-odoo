import json
from odoo import api, fields, models


class DynamicDashboardWidget(models.Model):
    _name = 'dynamic.dashboard.widget'
    _description = 'Dynamic Dashboard Widget'
    _order = 'sequence, id'

    name = fields.Char(string='Tên Widget', required=True)
    sequence = fields.Integer(string='Thứ tự', default=10)
    col_size = fields.Selection([
        ('3', '1/4 Hàng (Col-3)'),
        ('4', '1/3 Hàng (Col-4)'),
        ('6', '1/2 Hàng (Col-6)'),
        ('8', '2/3 Hàng (Col-8)'),
        ('12', 'Tràn Hàng (Col-12)')
    ], string='Độ rộng hiển thị', default='4', required=True)
    dashboard_id = fields.Many2one(
        'dynamic.dashboard', string='Dashboard', required=True, ondelete='cascade', index=True
    )
    page_id = fields.Many2one(
        'dynamic.dashboard.page', string='Trang/Tab', ondelete='cascade', index=True
    )

    widget_type = fields.Selection([
        ('kpi', 'Thẻ KPI'),
        ('line_chart', 'Biểu đồ đường (Line)'),
        ('bar_chart', 'Biểu đồ cột (Bar)'),
        ('horizontal_bar', 'Biểu đồ thanh ngang (Horizontal Bar)'),
        ('pie_chart', 'Biểu đồ tròn (Pie)'),
        ('donut_chart', 'Biểu đồ Donut'),
        ('area_chart', 'Biểu đồ miền (Area)'),
        ('table', 'Bảng dữ liệu (Table)'),
        ('activity', 'Hoạt động gần đây (Activity)'),
        ('shortcut', 'Phím tắt (Shortcut)')
    ], string='Loại Widget', required=True, default='kpi')

    provider_type = fields.Selection([
        ('odoo_model', 'Odoo Model ORM'),
        ('static', 'Dữ liệu tĩnh / Shortcut'),
        ('system_metric', 'Thông số hệ thống')
    ], string='Nguồn dữ liệu', default='odoo_model', required=True)

    model_id = fields.Many2one('ir.model', string='Model dữ liệu', ondelete='set null')
    model_name = fields.Char(string='Tên Model kỹ thuật', related='model_id.model', store=True)

    # Các trường cấu hình Giao diện & Màu sắc (Widget Color Themes)
    color_theme = fields.Selection([
        ('primary', 'Tím Indigo (Chủ đạo)'),
        ('success', 'Xanh Lá (Thành công)'),
        ('info', 'Xanh Dương (Thông tin)'),
        ('warning', 'Vàng Hổ phách (Cảnh báo)'),
        ('danger', 'Đỏ San hô (Báo động)'),
        ('teal', 'Xanh Ngọc (Teal)'),
        ('rose', 'Hồng Đào (Rose)'),
        ('dark', 'Đen Đá Slate (Tối sang trọng)')
    ], string='Màu chủ đề Widget', default='primary')
    custom_color = fields.Char(string='Mã màu tùy chỉnh (Hex)', help='Ví dụ: #6366f1 hoặc #10b981')
    icon = fields.Char(string='Biểu tượng (Icon FontAwesome)', default='fa-line-chart', help='Ví dụ: fa-file-text-o, fa-users, fa-dollar, fa-tachometer')

    # Các trường cấu hình Trực quan (No-code / Visual Controls)
    limit = fields.Integer(string='Số bản ghi hiển thị (Limit)', default=5)

    measure_field_id = fields.Many2one(
        'ir.model.fields', string='Trường tính chỉ số (Measure)',
        domain="[('model_id', '=', model_id)]", ondelete='set null'
    )
    aggregation_type = fields.Selection([
        ('count', 'Đếm số bản ghi (Count)'),
        ('sum', 'Tính tổng (Sum)'),
        ('avg', 'Trung bình (Average)'),
        ('min', 'Giá trị nhỏ nhất (Min)'),
        ('max', 'Giá trị lớn nhất (Max)')
    ], string='Phép tính (Aggregation)', default='count')

    group_by_field_id = fields.Many2one(
        'ir.model.fields', string='Trường gom nhóm (GroupBy)',
        domain="[('model_id', '=', model_id)]", ondelete='set null'
    )
    group_by_field_type = fields.Selection(related='group_by_field_id.ttype', string='Loại trường GroupBy')

    date_granularity = fields.Selection([
        ('day', 'Theo Ngày'),
        ('week', 'Theo Tuần'),
        ('month', 'Theo Tháng'),
        ('quarter', 'Theo Quý'),
        ('year', 'Theo Năm')
    ], string='Chu kỳ thời gian (GroupBy Date)', default='month')

    # Cấu hình So sánh Cùng kỳ (MoM / YoY Comparison)
    enable_comparison = fields.Boolean(
        string='So sánh cùng kỳ (MoM / YoY)', default=False,
        help='So sánh chỉ số chỉ tiêu với cùng kỳ trước đó (tháng trước/năm trước)'
    )
    comparison_type = fields.Selection([
        ('previous_period', 'Kỳ trước liền kề (Previous Period)'),
        ('previous_year', 'Cùng kỳ năm trước (Previous Year)')
    ], string='Loại so sánh', default='previous_period')
    comparison_date_field_id = fields.Many2one(
        'ir.model.fields', string='Trường Ngày so sánh',
        domain="[('model_id', '=', model_id), ('ttype', 'in', ['date', 'datetime'])]",
        ondelete='set null', help='Trường ngày dùng để tính toán khoảnh thời gian kỳ trước. Nếu để trống sẽ mặc định dùng create_date.'
    )

    table_field_ids = fields.Many2many(
        'ir.model.fields', 'dashboard_widget_field_rel', 'widget_id', 'field_id',
        string='Các cột hiển thị trong Bảng',
        domain="[('model_id', '=', model_id)]"
    )

    # Các trường lưu JSON nâng cao
    domain_json = fields.Text(string='Cấu hình Domain (JSON)', default='[]')
    measure_json = fields.Text(string='Cấu hình Chỉ số Measures (JSON)', default='[]')
    dimension_json = fields.Text(string='Cấu hình Nhóm GroupBy (JSON)', default='[]')
    filter_json = fields.Text(string='Bộ lọc riêng (JSON)', default='{}')
    style_json = fields.Text(string='Style & Theme (JSON)', default='{}')
    interaction_json = fields.Text(string='Cấu hình Tương tác (JSON)', default='{}')
    position_json = fields.Text(
        string='Vị trí Layout Grid (JSON)',
        default='{"desktop":{"x":0,"y":0,"w":4,"h":2}}'
    )

    refresh_interval = fields.Integer(string='Tự động làm mới (giây)', default=0)
    drilldown_action_id = fields.Many2one('ir.actions.act_window', string='Action khi nhấp chuột (Drilldown)')
    active = fields.Boolean(string='Hoạt động', default=True)

    @api.onchange('model_id')
    def _onchange_model_id(self):
        if not self.model_id:
            self.measure_field_id = False
            self.group_by_field_id = False
            self.table_field_ids = False
            self.domain_json = '[]'
            self.measure_json = '[]'
            self.dimension_json = '[]'

    @api.onchange('measure_field_id', 'aggregation_type', 'widget_type')
    def _onchange_measure_visual(self):
        if self.widget_type != 'table':
            field_name = self.measure_field_id.name if self.measure_field_id else 'id'
            agg = self.aggregation_type or 'count'
            self.measure_json = json.dumps([{"field": field_name, "aggregation": agg}])

    @api.onchange('table_field_ids')
    def _onchange_table_fields(self):
        if self.widget_type == 'table' and self.table_field_ids:
            field_names = [f.name for f in self.table_field_ids if getattr(f, 'name', False)]
            if field_names:
                self.measure_json = json.dumps([{"field": name} for name in field_names])

    @api.onchange('group_by_field_id', 'date_granularity')
    def _onchange_dimension_visual(self):
        if self.group_by_field_id and getattr(self.group_by_field_id, 'name', False):
            field_name = self.group_by_field_id.name
            f_type = self.group_by_field_id.ttype
            granularity = self.date_granularity or 'month'
            self.dimension_json = json.dumps([{
                "field": field_name,
                "type": f_type,
                "granularity": granularity
            }])
        else:
            self.dimension_json = '[]'
