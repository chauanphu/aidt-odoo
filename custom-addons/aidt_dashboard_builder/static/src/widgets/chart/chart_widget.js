/** @odoo-module **/

import { Component, onMounted, onWillUnmount, useRef } from "@odoo/owl";
import { widgetRegistry } from "../../services/widget_registry";

function ensureChartJSLoaded() {
    if (window.Chart) {
        return Promise.resolve();
    }
    return new Promise((resolve) => {
        const existingScript = document.querySelector('script[src*="chart.js"]');
        if (existingScript) {
            existingScript.addEventListener('load', () => resolve());
            setTimeout(resolve, 1500);
            return;
        }
        const script = document.createElement("script");
        script.src = "https://cdn.jsdelivr.net/npm/chart.js";
        script.onload = () => resolve();
        script.onerror = () => resolve();
        document.head.appendChild(script);
        setTimeout(resolve, 2000);
    });
}

export class ChartWidget extends Component {
    static template = "aidt_dashboard_builder.ChartWidget";
    static props = {
        widget: Object,
        data: Object,
        onDrilldown: { type: Function, optional: true },
    };

    setup() {
        this.canvasRef = useRef("chartCanvas");
        this.chartInstance = null;
        this.resizeObserver = null;

        onMounted(async () => {
            await ensureChartJSLoaded();
            this.renderChart();
            this.setupResizeObserver();
        });

        onWillUnmount(() => {
            if (this.resizeObserver) {
                this.resizeObserver.disconnect();
                this.resizeObserver = null;
            }
            if (this.chartInstance && typeof this.chartInstance.destroy === 'function') {
                this.chartInstance.destroy();
                this.chartInstance = null;
            }
        });
    }

    setupResizeObserver() {
        if (this.canvasRef.el && this.canvasRef.el.parentElement && window.ResizeObserver) {
            this.resizeObserver = new ResizeObserver(() => {
                if (this.chartInstance && typeof this.chartInstance.resize === 'function') {
                    this.chartInstance.resize();
                }
            });
            this.resizeObserver.observe(this.canvasRef.el.parentElement);
        }
    }

    renderChart() {
        if (!this.canvasRef.el || !this.props.data) {
            return;
        }

        const labels = this.props.data.labels || [];
        const datasets = this.props.data.datasets || [];
        const rawData = (datasets[0] && datasets[0].data) ? datasets[0].data : [];
        const labelName = (datasets[0] && datasets[0].label) ? datasets[0].label : this.props.widget.name;

        const wType = (this.props.widget.widget_type || 'bar_chart');

        const themeColors = {
            primary: '#714B67',
            success: '#28a745',
            info: '#00A09D',
            warning: '#f0ad4e',
            danger: '#dc3545',
            teal: '#00A09D',
            rose: '#e83e8c',
            dark: '#343a40',
        };

        const mainColor = this.props.data.custom_color || themeColors[this.props.data.color_theme || 'primary'] || '#714B67';

        if (window.Chart) {
            const ctx = this.canvasRef.el.getContext('2d');
            if (this.chartInstance) {
                this.chartInstance.destroy();
            }

            let chartType = 'bar';
            let indexAxis = 'x';
            let fillArea = false;

            if (wType === 'horizontal_bar') {
                chartType = 'bar';
                indexAxis = 'y';
            } else if (wType === 'line_chart') {
                chartType = 'line';
            } else if (wType === 'area_chart') {
                chartType = 'line';
                fillArea = true;
            } else if (wType === 'pie_chart') {
                chartType = 'pie';
            } else if (wType === 'donut_chart') {
                chartType = 'doughnut';
            }

            const pieColors = [
                mainColor,
                '#00A09D',
                '#28a745',
                '#f0ad4e',
                '#dc3545',
                '#e83e8c',
                '#17a2b8',
                '#6c757d'
            ];

            this.chartInstance = new window.Chart(ctx, {
                type: chartType,
                data: {
                    labels: labels,
                    datasets: [{
                        label: labelName,
                        data: rawData,
                        backgroundColor: (chartType === 'pie' || chartType === 'doughnut') ? pieColors : mainColor,
                        borderColor: mainColor,
                        borderWidth: 2,
                        borderRadius: chartType === 'bar' ? 4 : 0,
                        fill: fillArea,
                        tension: 0.3,
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    devicePixelRatio: window.devicePixelRatio || 2,
                    indexAxis: indexAxis,
                    plugins: {
                        legend: {
                            display: (chartType === 'pie' || chartType === 'doughnut'),
                            position: 'bottom'
                        }
                    },
                    scales: (chartType === 'pie' || chartType === 'doughnut') ? {} : {
                        y: { beginAtZero: true, grid: { color: 'rgba(233, 236, 239, 1)' } },
                        x: { grid: { display: false } }
                    }
                }
            });
            return;
        }

        const canvas = this.canvasRef.el;
        const ctx = canvas.getContext('2d');
        const dpr = window.devicePixelRatio || 2;
        const width = canvas.offsetWidth || 300;
        const height = canvas.offsetHeight || 220;

        canvas.width = width * dpr;
        canvas.height = height * dpr;
        canvas.style.width = `${width}px`;
        canvas.style.height = `${height}px`;

        ctx.scale(dpr, dpr);
        ctx.imageSmoothingEnabled = true;
        ctx.imageSmoothingQuality = 'high';

        ctx.clearRect(0, 0, width, height);

        if (labels.length === 0 || rawData.length === 0) {
            ctx.fillStyle = "#6c757d";
            ctx.font = "14px sans-serif";
            ctx.textAlign = "center";
            ctx.fillText("Chưa có dữ liệu thống kê", width / 2, height / 2);
            return;
        }

        const maxVal = Math.max(...rawData, 1);
        const padding = 40;
        const chartW = width - padding * 2;
        const chartH = height - padding * 2;
        const barW = chartW / labels.length;

        ctx.strokeStyle = "#dee2e6";
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.moveTo(padding, height - padding);
        ctx.lineTo(width - padding, height - padding);
        ctx.stroke();

        rawData.forEach((val, i) => {
            const barH = (val / maxVal) * chartH;
            const x = padding + i * barW + barW * 0.15;
            const y = height - padding - barH;
            const w = barW * 0.7;

            ctx.fillStyle = mainColor;
            ctx.beginPath();
            if (typeof ctx.roundRect === 'function') {
                ctx.roundRect(x, y, w, barH, [4, 4, 0, 0]);
            } else {
                ctx.rect(x, y, w, barH);
            }
            ctx.fill();

            ctx.fillStyle = "#6c757d";
            ctx.font = "11px sans-serif";
            ctx.textAlign = "center";
            ctx.fillText(String(labels[i]), x + w / 2, height - padding + 15);

            ctx.fillStyle = "#212529";
            ctx.font = "bold 11px sans-serif";
            ctx.fillText(String(val), x + w / 2, y - 5);
        });
    }
}

widgetRegistry.add("bar_chart", { component: ChartWidget, name: "Biểu đồ cột" });
widgetRegistry.add("horizontal_bar", { component: ChartWidget, name: "Biểu đồ thanh ngang" });
widgetRegistry.add("line_chart", { component: ChartWidget, name: "Biểu đồ đường" });
widgetRegistry.add("area_chart", { component: ChartWidget, name: "Biểu đồ miền" });
widgetRegistry.add("pie_chart", { component: ChartWidget, name: "Biểu đồ tròn" });
widgetRegistry.add("donut_chart", { component: ChartWidget, name: "Biểu đồ Donut" });
