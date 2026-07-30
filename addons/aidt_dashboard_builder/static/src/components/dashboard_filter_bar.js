/** @odoo-module **/

import { Component, useState } from "@odoo/owl";

export class DashboardFilterBar extends Component {
    static template = "aidt_dashboard_builder.DashboardFilterBar";
    static props = {
        activeFilterPill: { type: String, optional: true },
        filters: { type: Array, optional: true },
        onDatePillChange: { type: Function, optional: true },
        onFilterChange: { type: Function, optional: true },
    };

    setup() {
        this.state = useState({
            activePill: this.props.activeFilterPill || 'all',
            filterValues: {},
        });
    }

    datePills = [
        { id: 'all', label: 'Tất cả' },
        { id: 'today', label: 'Hôm nay' },
        { id: 'this_week', label: 'Tuần này' },
        { id: 'this_month', label: 'Tháng này' },
        { id: 'this_quarter', label: 'Quý này' },
        { id: 'this_year', label: 'Năm nay' }
    ];

    get hasActiveFilters() {
        if (this.state.activePill && this.state.activePill !== 'all') return true;
        return Object.values(this.state.filterValues).some(v => v !== "" && v !== null && v !== undefined);
    }

    selectPill(pillId) {
        this.state.activePill = pillId;
        if (this.props.onDatePillChange) {
            this.props.onDatePillChange(pillId);
        }
    }

    onCustomFilterChange(filter, ev) {
        const val = ev.target.value;
        this.state.filterValues[filter.id] = val;
        if (this.props.onFilterChange) {
            this.props.onFilterChange(filter.id, val);
            this.props.onFilterChange(filter.name, val);
        }
    }

    resetAllFilters() {
        this.state.activePill = 'all';
        this.state.filterValues = {};

        const selects = document.querySelectorAll('.dash-filter-select');
        selects.forEach(s => s.value = "");

        if (this.props.onDatePillChange) {
            this.props.onDatePillChange('all');
        }
        if (this.props.onFilterChange) {
            (this.props.filters || []).forEach(f => {
                this.props.onFilterChange(f.id, "");
                this.props.onFilterChange(f.name, "");
            });
        }
    }
}
