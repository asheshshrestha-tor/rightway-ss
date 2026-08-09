"use strict";

/* Enquiries-per-day area chart on the dashboard home page.
 *
 * Follows the Metronic widget convention: find the container by id, bail out
 * if it is absent, read colours from CSS custom properties (so the chart
 * matches whichever theme is active), size from the container's own CSS, and
 * rebuild on theme change.
 *
 * Data comes from a {{ ...|json_script }} block rather than inline template
 * interpolation, so nothing needs escaping by hand.
 */
var KTDashboardEnquiryChart = (function () {
    var chart = { self: null, rendered: false };

    function readData() {
        var node = document.getElementById("enquiry-chart-data");
        if (!node) {
            return null;
        }
        try {
            return JSON.parse(node.textContent);
        } catch (e) {
            return null;
        }
    }

    function initChart() {
        var element = document.getElementById("kt_dashboard_enquiries_chart");
        var data = readData();

        if (!element || !data || typeof ApexCharts === "undefined") {
            return;
        }

        var height = parseInt(KTUtil.css(element, "height"));
        var labelColor = KTUtil.getCssVariableValue("--bs-gray-500");
        var borderColor = KTUtil.getCssVariableValue("--bs-border-dashed-color");
        var baseColor = KTUtil.getCssVariableValue("--bs-primary");

        // An all-zero series makes ApexCharts pick a 0-1 axis; force a small
        // ceiling so an empty dashboard still renders a sensible grid.
        var peak = Math.max.apply(null, data.values.concat([0]));

        var options = {
            series: [{ name: "Enquiries", data: data.values }],
            chart: {
                fontFamily: "inherit",
                type: "area",
                height: height,
                toolbar: { show: false },
                zoom: { enabled: false }
            },
            legend: { show: false },
            dataLabels: { enabled: false },
            fill: {
                type: "gradient",
                gradient: { shadeIntensity: 1, opacityFrom: 0.35, opacityTo: 0, stops: [0, 80, 100] }
            },
            stroke: { curve: "smooth", show: true, width: 3, colors: [baseColor] },
            xaxis: {
                categories: data.labels,
                axisBorder: { show: false },
                axisTicks: { show: false },
                tickAmount: 7,
                labels: { style: { colors: labelColor, fontSize: "12px" } },
                crosshairs: {
                    position: "front",
                    stroke: { color: baseColor, width: 1, dashArray: 3 }
                }
            },
            yaxis: {
                min: 0,
                max: peak < 4 ? 4 : undefined,
                tickAmount: 4,
                labels: {
                    style: { colors: labelColor, fontSize: "12px" },
                    formatter: function (value) {
                        return Math.round(value);
                    }
                }
            },
            tooltip: {
                style: { fontSize: "12px" },
                y: {
                    formatter: function (value) {
                        return value + (value === 1 ? " enquiry" : " enquiries");
                    }
                }
            },
            colors: [baseColor],
            grid: {
                borderColor: borderColor,
                strokeDashArray: 4,
                yaxis: { lines: { show: true } }
            },
            markers: { strokeColor: baseColor, strokeWidth: 3 }
        };

        chart.self = new ApexCharts(element, options);

        // Deferred so the flex parent has settled on a width first.
        setTimeout(function () {
            chart.self.render();
            chart.rendered = true;
        }, 100);
    }

    return {
        init: function () {
            initChart();

            if (typeof KTThemeMode !== "undefined") {
                KTThemeMode.on("kt.thememode.change", function () {
                    if (chart.rendered) {
                        chart.self.destroy();
                        chart.rendered = false;
                    }
                    initChart();
                });
            }
        }
    };
})();

KTUtil.onDOMContentLoaded(function () {
    KTDashboardEnquiryChart.init();
});
