// weatherChart.js
import { loadWeatherByCoords, getHourlyWeather, updateGeneralWeatherDOM } from "./weather.js";

function getWindDirectionLabel(degrees) {
    if (degrees === undefined || degrees === null) return "";
    const adjusted = (degrees + 180) % 360;
    const directions = ["N", "NE", "E", "SE", "S", "SO", "O", "NO"];
    return directions[Math.round(adjusted / 45) % 8];
}

function formatDateLabel(dateStr) {
    const date = new Date(dateStr + "T00:00:00");
    const name = date.toLocaleDateString("es-ES", { weekday: "long", day: "numeric", month: "long" });
    return name.charAt(0).toUpperCase() + name.slice(1);
}

document.addEventListener("DOMContentLoaded", async () => {
    let lat, lon;

    if (window.fieldCoords) {
        lat = window.fieldCoords.lat;
        lon = window.fieldCoords.lon;
    } else if (navigator.geolocation) {
        await new Promise(resolve => {
            navigator.geolocation.getCurrentPosition(
                pos => {
                    lat = pos.coords.latitude;
                    lon = pos.coords.longitude;
                    resolve();
                },
                () => resolve()
            );
        });
    }

    if (!lat || !lon) return;

    try {
        // Si window.chartsOnly está activo (field.html), el clima ya lo carga field.js
        if (!window.chartsOnly) {
            const data = await loadWeatherByCoords(lat, lon);
            updateGeneralWeatherDOM(data);
        }

        const hourlyData = await getHourlyWeather(lat, lon);
        setupCharts(hourlyData);

    } catch (e) {
        console.error("[weatherChart] Error cargando datos:", e);
    }
});

// ─────────────────────────────────────────────
// SETUP CHARTS
// ─────────────────────────────────────────────
function setupCharts(grouped) {
    const days = Object.keys(grouped).sort();
    if (days.length === 0) return;

    const today = days[0];
    const nowHour = new Date().getHours();

    const todayFiltered = grouped[today].filter(h => {
        const hour = parseInt(h.time.split(":")[0]);
        return hour >= nowHour;
    });

    // ── HOY ──
    const todayToggleRow = document.getElementById("today-chart-toggle");
    const todayPanel     = document.getElementById("today-chart-panel");
    const todayCanvas    = document.getElementById("today-chart-canvas");

    if (todayToggleRow && todayPanel && todayCanvas) {
        let todayChartInstance = null;
        let todayMode = "temp";

        todayToggleRow.addEventListener("click", () => {
            const isOpen = todayPanel.classList.toggle("open");
            const arrow = todayToggleRow.querySelector(".chart-arrow");
            if (arrow) arrow.classList.toggle("rotated", isOpen);
            if (isOpen && !todayChartInstance) {
                todayChartInstance = drawChart(todayCanvas, todayFiltered, todayMode);
            }
        });

        document.getElementById("today-btn-temp")?.addEventListener("click", (e) => {
            e.stopPropagation();
            todayMode = "temp";
            setActiveTab("today-btn-temp", "today-btn-humidity");
            if (todayChartInstance) {
                todayChartInstance.destroy();
                todayChartInstance = drawChart(todayCanvas, todayFiltered, todayMode);
            }
        });

        document.getElementById("today-btn-humidity")?.addEventListener("click", (e) => {
            e.stopPropagation();
            todayMode = "humidity";
            setActiveTab("today-btn-humidity", "today-btn-temp");
            if (todayChartInstance) {
                todayChartInstance.destroy();
                todayChartInstance = drawChart(todayCanvas, todayFiltered, todayMode);
            }
        });
    }

    // ── PRÓXIMOS 4 DÍAS ──
    const forecastToggleRow = document.getElementById("forecast-charts-toggle");
    const forecastPanel     = document.getElementById("forecast-charts-panel");

    if (forecastToggleRow && forecastPanel) {
        let forecastRendered = false;

        forecastToggleRow.addEventListener("click", () => {
            const isOpen = forecastPanel.classList.toggle("open");
            const arrow = forecastToggleRow.querySelector(".chart-arrow");
            if (arrow) arrow.classList.toggle("rotated", isOpen);

            if (isOpen && !forecastRendered) {
                forecastRendered = true;
                days.slice(1, 5).forEach((day, i) => {
                    const canvas    = document.getElementById(`forecast-canvas-${i}`);
                    const dateLabel = document.getElementById(`forecast-chart-date-${i}`);
                    const btnTemp   = document.getElementById(`forecast-btn-temp-${i}`);
                    const btnHum    = document.getElementById(`forecast-btn-humidity-${i}`);
                    if (!canvas) return;

                    if (dateLabel) dateLabel.textContent = formatDateLabel(day);
                    let mode = "temp";
                    let chartInst = drawChart(canvas, grouped[day], mode);

                    btnTemp?.addEventListener("click", (e) => {
                        e.stopPropagation();
                        mode = "temp";
                        setActiveTab(`forecast-btn-temp-${i}`, `forecast-btn-humidity-${i}`);
                        chartInst.destroy();
                        chartInst = drawChart(canvas, grouped[day], mode);
                    });
                    btnHum?.addEventListener("click", (e) => {
                        e.stopPropagation();
                        mode = "humidity";
                        setActiveTab(`forecast-btn-humidity-${i}`, `forecast-btn-temp-${i}`);
                        chartInst.destroy();
                        chartInst = drawChart(canvas, grouped[day], mode);
                    });
                });
            }
        });
    }
}

function setActiveTab(activeId, inactiveId) {
    document.getElementById(activeId)?.classList.add("active");
    document.getElementById(inactiveId)?.classList.remove("active");
}

// ─────────────────────────────────────────────
// PLUGIN: etiquetas encima de los puntos
// ─────────────────────────────────────────────
const dataLabelsPlugin = {
    id: "dataLabels",
    afterDatasetsDraw(chart) {
        const { ctx, data } = chart;
        const meta = chart.getDatasetMeta(0);
        const isTemp = chart._isTemp;
        data.labels.forEach((_, i) => {
            const point = meta.data[i];
            if (!point) return;
            const value = data.datasets[0].data[i];
            ctx.save();
            ctx.font = "bold 11px 'Segoe UI', Arial, sans-serif";
            ctx.fillStyle = isTemp ? "#b07d00" : "#1565c0";
            ctx.textAlign = "center";
            ctx.textBaseline = "bottom";
            ctx.fillText(isTemp ? `${value}°` : `${value}%`, point.x, point.y - 7);
            ctx.restore();
        });
    }
};

// ─────────────────────────────────────────────
// DIBUJAR GRÁFICA
// ─────────────────────────────────────────────
function drawChart(canvas, hourlyData, mode = "temp") {
    const isTemp = mode === "temp";
    const values = isTemp
        ? hourlyData.map(h => h.temp)
        : hourlyData.map(h => h.prob_rain ?? 0);

    const color      = isTemp ? "#e0a800" : "#2196f3";
    const colorLight = isTemp ? "rgba(224,168,0,0.13)" : "rgba(33,150,243,0.13)";

    const chart = new Chart(canvas, {
        type: "line",
        data: {
            labels: hourlyData.map(h => h.time),
            datasets: [{
                data: values,
                borderColor: color,
                backgroundColor: colorLight,
                pointBackgroundColor: color,
                pointBorderColor: "#fff",
                pointBorderWidth: 1.5,
                pointRadius: 5,
                pointHoverRadius: 7,
                fill: true,
                tension: 0.4,
                borderWidth: 2.5
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            layout: { padding: { top: 26 } },
            interaction: { mode: "index", intersect: false },
            plugins: {
                legend: { display: false },
                tooltip: {
                    backgroundColor: "rgba(240,240,240,0.97)",
                    titleColor: "#111",
                    bodyColor: "#333",
                    padding: 12,
                    cornerRadius: 8,
                    borderColor: "transparent",
                    borderWidth: 0,
                    titleFont: { weight: "bold", size: 13 },
                    bodyFont: { weight: "normal", size: 12 },
                    displayColors: false,
                    callbacks: {
                        title: (items) => `${items[0].label}`,
                        label: (item) => {
                            const h = hourlyData[item.dataIndex];
                            const windDir = getWindDirectionLabel(h.wind_dir);
                            return [
                                `Viento: ${h.wind_speed} km/h (${windDir})`,
                                `Lluvia estimada: ${h.rain} mm`,
                                `Granizo: ${h.hail}%`
                            ];
                        },
                        labelColor: () => ({ borderColor: "transparent", backgroundColor: "transparent" })
                    }
                }
            },
            scales: {
                x: {
                    grid: { display: false },
                    border: { display: true, color: "#ccc" },
                    ticks: {
                        color: "#666",
                        font: { size: 11, family: "'Segoe UI', Arial, sans-serif" },
                        maxRotation: 0
                    }
                },
                y: {
                    display: !isTemp,
                    min: isTemp ? (Math.min(...values) >= 0 ? 0 : undefined) : 0,
                    max: isTemp ? undefined : 100,
                    grid: { display: !isTemp, color: "rgba(0,0,0,0.06)" },
                    border: { display: false },
                    ticks: {
                        display: !isTemp,
                        color: "#1565c0",
                        font: { size: 10 },
                        callback: v => v + "%",
                        stepSize: 25,
                    }
                }
            }
        },
        plugins: [dataLabelsPlugin]
    });

    chart._isTemp = isTemp;
    return chart;
}