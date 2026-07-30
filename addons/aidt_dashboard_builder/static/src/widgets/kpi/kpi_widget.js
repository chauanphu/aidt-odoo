/** @odoo-module **/

import { Component, onMounted, useRef } from "@odoo/owl";
import { widgetRegistry } from "../../services/widget_registry";

export class KpiWidget extends Component {
    static template = "aidt_dashboard_builder.KpiWidget";
    static props = {
        widget: Object,
        data: Object,
        onDrilldown: { type: Function, optional: true },
    };

    setup() {
        this.kpiValueRef = useRef("kpiValue");

        onMounted(() => {
            this.animateCountUp();
        });
    }

    /**
     * Animate KPI value from 0 → target with easeOutExpo curve.
     * Handles formatted numbers like "1,234", "56.78%", "₫1,200,000", "$12.5K"
     */
    animateCountUp() {
        const el = this.kpiValueRef.el;
        if (!el || !this.props.data) return;

        const formatted = this.props.data.formatted_value;
        if (!formatted && formatted !== 0) return;

        const text = String(formatted);
        // Extract the numeric part from the formatted string
        const numMatch = text.match(/[\d,.]+/);
        if (!numMatch) {
            // No numeric content (e.g. pure text), just show it
            el.textContent = text;
            return;
        }

        const numStr = numMatch[0];
        const prefix = text.substring(0, numMatch.index);
        const suffix = text.substring(numMatch.index + numStr.length);

        // Parse the actual number (remove thousand separators)
        const cleanNum = numStr.replace(/,/g, '');
        const targetValue = parseFloat(cleanNum);

        if (isNaN(targetValue) || targetValue === 0) {
            el.textContent = text;
            return;
        }

        // Determine decimal places from original format
        const dotIdx = numStr.lastIndexOf('.');
        const decimals = dotIdx >= 0 ? numStr.length - dotIdx - 1 : 0;

        // Check if original used thousand separators
        const useThousandSep = numStr.includes(',') && (dotIdx < 0 || numStr.indexOf(',') < dotIdx);

        const duration = 1200; // ms
        const startTime = performance.now();

        const formatNumber = (val) => {
            let result;
            if (decimals > 0) {
                result = val.toFixed(decimals);
            } else {
                result = Math.round(val).toString();
            }

            // Add thousand separators if original had them
            if (useThousandSep) {
                const parts = result.split('.');
                parts[0] = parts[0].replace(/\B(?=(\d{3})+(?!\d))/g, ',');
                result = parts.join('.');
            }

            return prefix + result + suffix;
        };

        // easeOutExpo for satisfying deceleration
        const easeOutExpo = (t) => t === 1 ? 1 : 1 - Math.pow(2, -10 * t);

        const animate = (currentTime) => {
            const elapsed = currentTime - startTime;
            const progress = Math.min(elapsed / duration, 1);
            const easedProgress = easeOutExpo(progress);
            const currentValue = targetValue * easedProgress;

            el.textContent = formatNumber(currentValue);

            if (progress < 1) {
                requestAnimationFrame(animate);
            } else {
                // Ensure final value matches exactly
                el.textContent = text;
            }
        };

        // Start from 0
        el.textContent = formatNumber(0);
        requestAnimationFrame(animate);
    }

    onClick() {
        if (this.props.onDrilldown) {
            this.props.onDrilldown(this.props.widget, this.props.data);
        }
    }
}

widgetRegistry.add("kpi", {
    component: KpiWidget,
    name: "Thẻ KPI",
});
