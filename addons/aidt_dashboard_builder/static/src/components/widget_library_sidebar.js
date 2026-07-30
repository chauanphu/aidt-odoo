/** @odoo-module **/

import { Component } from "@odoo/owl";

export class WidgetLibrarySidebar extends Component {
    static template = "aidt_dashboard_builder.WidgetLibrarySidebar";
    static props = {
        isOpen: Boolean,
        onClose: Function,
        onAddWidget: Function,
    };

    get presetWidgets() {
        return [
            {
                id: 'kpi',
                type: 'kpi',
                name: 'Thẻ chỉ số KPI',
                desc: 'Hiển thị tổng đếm hoặc giá trị chỉ số quan trọng',
                icon: 'fa-tachometer',
                color: '#714B67',
                defaultW: 3,
                defaultH: 2
            },
            {
                id: 'bar_chart',
                type: 'bar_chart',
                name: 'Biểu đồ cột (Bar)',
                desc: 'So sánh chỉ số giữa các danh mục hoặc phòng ban',
                icon: 'fa-bar-chart',
                color: '#00A09D',
                defaultW: 6,
                defaultH: 3
            },
            {
                id: 'line_chart',
                type: 'line_chart',
                name: 'Biểu đồ đường (Line)',
                desc: 'Theo dõi xu hướng biến động theo thời gian',
                icon: 'fa-line-chart',
                color: '#28a745',
                defaultW: 6,
                defaultH: 3
            },
            {
                id: 'pie_chart',
                type: 'pie_chart',
                name: 'Biểu đồ tròn (Pie)',
                desc: 'Tỷ lệ phần trăm phân bổ dữ liệu',
                icon: 'fa-pie-chart',
                color: '#f0ad4e',
                defaultW: 4,
                defaultH: 3
            },
            {
                id: 'table',
                type: 'table',
                name: 'Bảng dữ liệu chi tiết',
                desc: 'Hiển thị danh sách bản ghi và các thuộc tính',
                icon: 'fa-table',
                color: '#343a40',
                defaultW: 8,
                defaultH: 4
            },
            {
                id: 'activity',
                type: 'activity',
                name: 'Hoạt động gần đây',
                desc: 'Nhật ký các thao tác hoặc tài liệu mới nhất',
                icon: 'fa-history',
                color: '#e83e8c',
                defaultW: 4,
                defaultH: 3
            },
            {
                id: 'shortcut',
                type: 'shortcut',
                name: 'Phím tắt truy cập nhanh',
                desc: 'Nút bấm chuyển nhanh đến màn hình chức năng',
                icon: 'fa-external-link',
                color: '#17a2b8',
                defaultW: 3,
                defaultH: 2
            }
        ];
    }

    onWidgetClick(preset) {
        if (this.props.onAddWidget) {
            this.props.onAddWidget(preset);
        }
    }
}
