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

    onViewDetailsClick(ev) {
        if (ev) ev.stopPropagation();
        if (this.props.onDrilldown) {
            this.props.onDrilldown(this.props.widget, this.props.data);
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

            // ── Chart.js Animation Configuration ──
            const totalDuration = 1200;
            const delayBetweenPoints = rawData.length > 0 ? totalDuration / rawData.length : 100;

            // Delayed animation per-bar (grow from bottom)
            const delayedBarAnimation = {
                x: { duration: 0 },
                y: {
                    easing: 'easeOutQuart',
                    duration: (ctx) => ctx.type === 'data' ? delayBetweenPoints : 0,
                    delay: (ctx) => ctx.type === 'data' ? ctx.dataIndex * delayBetweenPoints * 0.6 : 0,
                    from: (ctx) => {
                        if (ctx.type === 'data') {
                            return ctx.chart.scales.y ? ctx.chart.scales.y.getPixelForValue(0) : ctx.chart.height;
                        }
                    }
                }
            };

            // Line/area draw-in animation
            const lineDrawAnimation = {
                x: {
                    easing: 'easeInOutQuart',
                    duration: (ctx) => ctx.type === 'data' ? delayBetweenPoints : 0,
                    delay: (ctx) => ctx.type === 'data' ? ctx.dataIndex * delayBetweenPoints * 0.5 : 0,
                    from: NaN,
                },
                y: {
                    easing: 'easeInOutQuart',
                    duration: (ctx) => ctx.type === 'data' ? delayBetweenPoints : 0,
                    delay: (ctx) => ctx.type === 'data' ? ctx.dataIndex * delayBetweenPoints * 0.5 : 0,
                    from: (ctx) => {
                        if (ctx.type === 'data') {
                            return ctx.chart.scales.y ? ctx.chart.scales.y.getPixelForValue(0) : ctx.chart.height;
                        }
                    }
                }
            };

            // Pie / Donut expand from center
            const pieExpandAnimation = {
                animateRotate: true,
                animateScale: true,
                duration: 1000,
                easing: 'easeOutQuart',
            };

            // Determine animation config by chart type
            let animationConfig;
            if (chartType === 'bar') {
                animationConfig = delayedBarAnimation;
            } else if (chartType === 'line') {
                animationConfig = lineDrawAnimation;
            } else {
                animationConfig = {};
            }

            // Dataset styling enhancements
            const datasetConfig = {
                label: labelName,
                data: rawData,
                backgroundColor: (chartType === 'pie' || chartType === 'doughnut')
                    ? pieColors
                    : (chartType === 'line' || fillArea)
                        ? this._createGradient(ctx, mainColor, fillArea)
                        : rawData.map((_, i) => {
                            const opacity = 0.6 + (0.4 * (i % 2 === 0 ? 1 : 0.7));
                            return this._hexToRgba(mainColor, opacity);
                          }),
                borderColor: (chartType === 'pie' || chartType === 'doughnut') ? '#ffffff' : mainColor,
                borderWidth: (chartType === 'pie' || chartType === 'doughnut') ? 2 : 2.5,
                borderRadius: chartType === 'bar' ? 6 : 0,
                fill: fillArea,
                tension: 0.4,
                pointRadius: chartType === 'line' || fillArea ? 4 : 0,
                pointBackgroundColor: '#ffffff',
                pointBorderColor: mainColor,
                pointBorderWidth: 2.5,
                pointHoverRadius: 7,
                pointHoverBackgroundColor: mainColor,
                pointHoverBorderColor: '#ffffff',
                pointHoverBorderWidth: 3,
                hoverOffset: (chartType === 'pie' || chartType === 'doughnut') ? 12 : 0,
            };

            this.chartInstance = new window.Chart(ctx, {
                type: chartType,
                data: {
                    labels: labels,
                    datasets: [datasetConfig]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    devicePixelRatio: window.devicePixelRatio || 2,
                    indexAxis: indexAxis,
                    animation: (chartType === 'pie' || chartType === 'doughnut') ? pieExpandAnimation : animationConfig,
                    transitions: {
                        active: {
                            animation: {
                                duration: 300
                            }
                        }
                    },
                    interaction: {
                        mode: 'index',
                        intersect: false,
                    },
                    onClick: (evt, activeElements) => {
                        if (activeElements && activeElements.length > 0) {
                            const index = activeElements[0].index;
                            const groupDomain = (this.props.data && this.props.data.group_domains) ? this.props.data.group_domains[index] : null;
                            if (this.props.onDrilldown) {
                                this.props.onDrilldown(this.props.widget, this.props.data, null, {
                                    group_domain: groupDomain,
                                    label: labels[index]
                                });
                            }
                        }
                    },
                    plugins: {
                        legend: {
                            display: (chartType === 'pie' || chartType === 'doughnut'),
                            position: 'bottom',
                            labels: {
                                padding: 16,
                                usePointStyle: true,
                                pointStyle: 'circle',
                                font: { size: 11, weight: '600' }
                            }
                        },
                        tooltip: {
                            backgroundColor: 'rgba(30, 41, 59, 0.92)',
                            titleFont: { size: 12, weight: '700' },
                            bodyFont: { size: 11 },
                            cornerRadius: 8,
                            padding: 10,
                            displayColors: true,
                            boxPadding: 4,
                        }
                    },
                    scales: (chartType === 'pie' || chartType === 'doughnut') ? {} : {
                        y: {
                            beginAtZero: true,
                            grid: {
                                color: 'rgba(226, 232, 240, 0.6)',
                                drawBorder: false,
                            },
                            ticks: {
                                font: { size: 11, weight: '500' },
                                color: '#64748b',
                                padding: 8,
                            },
                            border: { display: false }
                        },
                        x: {
                            grid: { display: false },
                            ticks: {
                                font: { size: 11, weight: '500' },
                                color: '#64748b',
                                padding: 4,
                                maxRotation: 45,
                            },
                            border: { display: false }
                        }
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

    /**
     * Create a vertical gradient for line/area chart fills.
     */
    _createGradient(ctx, hexColor, isFill) {
        try {
            const canvas = ctx.canvas || this.canvasRef.el;
            const gradient = ctx.createLinearGradient(0, 0, 0, canvas.height || 250);
            const rgb = this._hexToRgb(hexColor);
            if (isFill) {
                gradient.addColorStop(0, `rgba(${rgb}, 0.35)`);
                gradient.addColorStop(0.6, `rgba(${rgb}, 0.08)`);
                gradient.addColorStop(1, `rgba(${rgb}, 0.01)`);
            } else {
                gradient.addColorStop(0, `rgba(${rgb}, 0.1)`);
                gradient.addColorStop(1, `rgba(${rgb}, 0)`);
            }
            return gradient;
        } catch (e) {
            return hexColor;
        }
    }

    /**
     * Convert hex color to "r, g, b" string.
     */
    _hexToRgb(hex) {
        const result = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex);
        if (result) {
            return `${parseInt(result[1], 16)}, ${parseInt(result[2], 16)}, ${parseInt(result[3], 16)}`;
        }
        return '113, 75, 103'; // fallback purple
    }

    /**
     * Convert hex color to rgba string with given opacity.
     */
    _hexToRgba(hex, opacity) {
        return `rgba(${this._hexToRgb(hex)}, ${opacity})`;
    }
}

widgetRegistry.add("bar_chart", { component: ChartWidget, name: "Biểu đồ cột" });
widgetRegistry.add("horizontal_bar", { component: ChartWidget, name: "Biểu đồ thanh ngang" });
widgetRegistry.add("line_chart", { component: ChartWidget, name: "Biểu đồ đường" });
widgetRegistry.add("area_chart", { component: ChartWidget, name: "Biểu đồ miền" });
widgetRegistry.add("pie_chart", { component: ChartWidget, name: "Biểu đồ tròn" });
widgetRegistry.add("donut_chart", { component: ChartWidget, name: "Biểu đồ Donut" });
