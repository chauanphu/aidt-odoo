/** @odoo-module **/

import { Component } from "@odoo/owl";
import { widgetRegistry } from "../../services/widget_registry";

export class TableWidget extends Component {
    static template = "aidt_dashboard_builder.TableWidget";
    static props = {
        widget: Object,
        data: Object,
        onDrilldown: { type: Function, optional: true },
    };

    onViewDetailsClick() {
        if (this.props.onDrilldown) {
            this.props.onDrilldown(this.props.widget, this.props.data);
        }
    }
}

widgetRegistry.add("table", {
    component: TableWidget,
    name: "Bảng dữ liệu",
});
