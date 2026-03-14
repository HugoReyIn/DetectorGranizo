// agro.js — Datos agronómicos completos para field.html

const LEVEL_ORDER = { verde: 0, amarillo: 1, naranja: 2, rojo: 3 };

// ─────────────────────────────────────────────
// CATEGORÍAS UV
// ─────────────────────────────────────────────
function uvCategory(uv) {
    if (uv === null || uv === undefined) return { label: "—", cls: "" };
    if (uv <= 2) return { label: "Bajo", cls: "uv-low" };
    if (uv <= 5) return { label: "Moderado", cls: "uv-moderate" };
    if (uv <= 7) return { label: "Alto", cls: "uv-high" };
    if (uv <= 10) return { label: "Muy alto", cls: "uv-veryhigh" };
    return { label: "Extremo", cls: "uv-extreme" };
}

// ─────────────────────────────────────────────
// RENDER ALERTAS AEMET EN FIELD
// ─────────────────────────────────────────────
const ALERT_EMOJI = {
    calor:    "🌡️",
    helada:   "🥶",
    lluvia:   "🌧️",
    nieve:    "❄️",
    viento:   "💨",
    tormenta: "⛈️",
    granizo:  "🧊",
    niebla:   "🌫️",
};

const ALERT_LABEL = {
    calor:    "Calor",
    helada:   "Helada",
    lluvia:   "Lluvia",
    nieve:    "Nieve",
    viento:   "Viento",
    tormenta: "Tormenta",
    granizo:  "Granizo",
    niebla:   "Niebla",
};

function renderAgroAlerts(data) {
    const TIPOS = ["calor", "helada", "lluvia", "nieve", "viento", "tormenta", "granizo", "niebla"];
    let worst = "verde";

    TIPOS.forEach(tipo => {
        const el = document.getElementById(`agro-alert-${tipo}`);
        if (!el) return;

        const nivel = data?.[tipo]?.nivel || "verde";
        const valor = data?.[tipo]?.valor || null;

        // Actualizar clase de nivel
        el.className = `agro-alert-item nivel-${nivel}`;

        // Reconstruir contenido para evitar bugs de DOM incremental
        el.innerHTML = `
            <span class="agro-alert-emoji">${ALERT_EMOJI[tipo]}</span>
            <span class="agro-alert-name">${ALERT_LABEL[tipo]}</span>
            ${nivel !== "verde" && valor ? `<span class="agro-alert-valor">${valor}</span>` : ""}
        `;

        if (LEVEL_ORDER[nivel] > LEVEL_ORDER[worst]) worst = nivel;
    });

    // Barra de nivel máximo
    const bar = document.getElementById("agro-alert-bar");
    if (bar) bar.className = `agro-alert-bar-inline alert-bar-${worst}`;

    // Ticker
    const ticker = document.getElementById("agro-alert-ticker");
    if (ticker) {
        const msgs = data?.ticker?.length ? data.ticker : ["No hay alertas activas"];
        ticker.textContent = msgs.join(" · ");
        ticker.className = `agro-alert-ticker ticker-text-${worst}`;
    }
}

// ─────────────────────────────────────────────
// RENDER ET₀ FORECAST 4 DÍAS
// ─────────────────────────────────────────────
function renderEt0Forecast(forecast) {
    const container = document.getElementById("agro-et0-forecast");
    if (!container || !forecast) return;

    container.innerHTML = forecast.map(d => {
        const date = d.date ? new Date(d.date + "T12:00:00") : null;
        const dayName = date ? date.toLocaleDateString("es-ES", { weekday: "short", day: "numeric" }) : "—";
        const et0 = d.et0 !== null ? `${d.et0} mm` : "—";
        const rain = d.rain !== null ? `${d.rain} mm` : "—";
        const uv = d.uv_max !== null ? d.uv_max : "—";
        const uvCat = uvCategory(d.uv_max);
        return `
            <div class="agro-et0-day">
                <div class="agro-et0-day-name">${dayName}</div>
                <div class="agro-et0-day-et0">💧 ET₀: <strong>${et0}</strong></div>
                <div class="agro-et0-day-rain">🌧️ Lluvia: <strong>${rain}</strong></div>
                <div class="agro-et0-day-uv ${uvCat.cls}">☀️ UV: <strong>${uv}</strong> <span class="uv-label">${uvCat.label}</span></div>
                <div class="agro-et0-day-range">🌡️ ${d.tmin ?? "—"}° / ${d.tmax ?? "—"}°</div>
            </div>
        `;
    }).join("");
}

// ─────────────────────────────────────────────
// GRÁFICA ET₀ HORARIA
// ─────────────────────────────────────────────
function renderEt0Chart(hourlyData) {
    const canvas = document.getElementById("agro-et0-canvas");
    if (!canvas || !hourlyData || hourlyData.length === 0) return;

    const labels = hourlyData.map(h => h.time);
    const et0vals = hourlyData.map(h => h.et0 ?? 0);
    const radvals = hourlyData.map(h => h.radiation ?? 0);

    if (window._agroEt0Chart) window._agroEt0Chart.destroy();

    window._agroEt0Chart = new Chart(canvas, {
        type: "bar",
        data: {
            labels,
            datasets: [
                {
                    label: "ET₀ (mm/h)",
                    data: et0vals,
                    backgroundColor: "rgba(33,150,243,0.65)",
                    borderRadius: 4,
                    yAxisID: "y"
                },
                {
                    label: "Radiación (W/m²)",
                    data: radvals,
                    type: "line",
                    borderColor: "#ff9800",
                    backgroundColor: "rgba(255,152,0,0.1)",
                    pointRadius: 2,
                    fill: true,
                    tension: 0.4,
                    yAxisID: "y2"
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: { mode: "index", intersect: false },
            plugins: {
                legend: { display: true, position: "top", labels: { font: { size: 11 } } },
                tooltip: { backgroundColor: "rgba(240,240,240,0.97)", titleColor: "#111", bodyColor: "#333" }
            },
            scales: {
                x: { grid: { display: false }, ticks: { maxRotation: 45, font: { size: 10 } } },
                y: {
                    position: "left",
                    title: { display: true, text: "ET₀ mm/h", font: { size: 10 } },
                    ticks: { color: "#1565c0", font: { size: 10 } }
                },
                y2: {
                    position: "right",
                    grid: { drawOnChartArea: false },
                    title: { display: true, text: "W/m²", font: { size: 10 } },
                    ticks: { color: "#ff9800", font: { size: 10 } }
                }
            }
        }
    });
}

// ─────────────────────────────────────────────
// RENDER SUELO
// ─────────────────────────────────────────────
function renderSoilBars(data) {
    const layers = [
        { id: "agro-soil-0", barId: "soil-bar-0", val: data.soil_moisture_0 },
        { id: "agro-soil-1", barId: "soil-bar-1", val: data.soil_moisture_1 },
        { id: "agro-soil-3", barId: "soil-bar-3", val: data.soil_moisture_3 },
    ];
    layers.forEach(l => {
        const el = document.getElementById(l.id);
        const bar = document.getElementById(l.barId);
        if (l.val !== null && l.val !== undefined) {
            const pct = Math.min(100, (l.val * 100)).toFixed(0);
            if (el) el.textContent = `${pct}%`;
            if (bar) {
                bar.style.width = `${pct}%`;
                bar.style.background = pct < 20 ? "#ff5722" : pct > 70 ? "#2196f3" : "#4caf50";
            }
        } else {
            if (el) el.textContent = "—";
        }
    });

    // Tip suelo
    const tip = document.getElementById("agro-soil-tip");
    if (tip && data.soil_moisture_0 !== null) {
        const pct = (data.soil_moisture_0 * 100).toFixed(0);
        if (pct < 20) tip.textContent = "⚠️ Suelo muy seco — riego urgente recomendado";
        else if (pct < 35) tip.textContent = "🟡 Suelo con humedad baja — monitorizar";
        else if (pct < 65) tip.textContent = "✅ Humedad del suelo óptima";
        else tip.textContent = "💦 Suelo con exceso de humedad";
    }
}

// ─────────────────────────────────────────────
// EXPLICACIÓN DINÁMICA DEL GRÁFICO ET₀
// ─────────────────────────────────────────────
function renderEt0ChartTip(hourlyData, et0Today, cropType) {
    const tipEl = document.getElementById("et0-chart-tip");
    if (!tipEl || !hourlyData || !hourlyData.length) return;

    const peak = hourlyData.reduce((a, b) => (b.et0 ?? 0) > (a.et0 ?? 0) ? b : a, hourlyData[0]);
    const peakHour = peak.time || "—";
    const peakVal  = peak.et0 !== null ? peak.et0.toFixed(2) : "—";
    const activeHours = hourlyData.filter(h => (h.et0 ?? 0) > 0.05).length;

    let advice = "";
    if (!et0Today || et0Today <= 1.5)
        advice = "La demanda hídrica de hoy es baja — no es necesario regar.";
    else if (et0Today <= 3.5)
        advice = "Demanda moderada. Riega preferiblemente al amanecer o al atardecer, fuera del pico.";
    else if (et0Today <= 5.5)
        advice = `Demanda alta. Programa el riego antes de las ${peakHour}h o después de las 18:00h para reducir pérdidas.`;
    else
        advice = "Demanda muy alta. Riega en dos turnos: madrugada y tarde. Evita el mediodía solar.";

    const crop = cropType ? ` para ${cropType}` : "";
    tipEl.innerHTML = `📊 <strong>Pico${crop}:</strong> ${peakVal} mm/h a las ${peakHour}h (${activeHours}h de demanda activa). ${advice}`;
}

async function loadAgroData(lat, lon, cropType) {
    try {
        const [agroRes, alertRes, hailRes] = await Promise.allSettled([
            fetch(`/get-agronomic-data?lat=${lat}&lon=${lon}`).then(r => r.json()),
            fetch(`/get-aemet-alerts?lat=${lat}&lon=${lon}`).then(r => r.json()),
            fetch(`/get-hail-prediction?lat=${lat}&lon=${lon}`).then(r => r.json()),
        ]);

        const agro = agroRes.status === "fulfilled" ? agroRes.value : {};
        const alerts = alertRes.status === "fulfilled" ? alertRes.value : null;
        const hail = hailRes.status === "fulfilled" ? hailRes.value : [];

        // Máx granizo próximas 6h
        const now = new Date();
        const in6h = new Date(now.getTime() + 6 * 3600 * 1000);
        const hailMax = Array.isArray(hail)
            ? Math.max(0, ...hail.filter(h => { const t = new Date(h.time); return t >= now && t <= in6h; }).map(h => h.hail_probability))
            : 0;
        agro.hail_risk_6h = hailMax;

        // ── ALERTAS AEMET ──
        renderAgroAlerts(alerts);

        // ── ET₀ ──
        const et0El = document.getElementById("agro-et0-today");
        const et0Sub = document.getElementById("agro-et0-current");
        const et0Tip = document.getElementById("agro-et0-tip");
        if (et0El) et0El.textContent = agro.et0_today !== null ? `${agro.et0_today} mm` : "—";
        if (et0Sub) et0Sub.textContent = `Actual: ${agro.et0_current !== null ? `${agro.et0_current} mm/h` : "—"}`;
        if (et0Tip) {
            if (agro.et0_today >= 5) et0Tip.textContent = "⚠️ Demanda hídrica alta — considera regar";
            else if (agro.et0_today >= 3) et0Tip.textContent = "🟡 Demanda hídrica moderada";
            else et0Tip.textContent = "✅ Demanda hídrica baja";
        }

        // ── UV ──
        const uvEl = document.getElementById("agro-uv");
        const uvMax = document.getElementById("agro-uv-max");
        const uvTip = document.getElementById("agro-uv-tip");
        const uvCat = uvCategory(agro.uv_index);
        if (uvEl) { uvEl.textContent = agro.uv_index ?? "—"; uvEl.className = `agro-card-value ${uvCat.cls}`; }
        if (uvMax) uvMax.textContent = `Máx. hoy: ${agro.uv_max_today ?? "—"}`;
        if (uvTip) uvTip.textContent = uvCat.label ? `Nivel ${uvCat.label.toLowerCase()} — ${agro.uv_index >= 6 ? "evita tratamientos en horas centrales" : "condiciones adecuadas para trabajos"}` : "";

        // ── PRESIÓN ──
        const pressEl = document.getElementById("agro-pressure");
        const vpdEl = document.getElementById("agro-vpd");
        const pressTip = document.getElementById("agro-pressure-tip");
        if (pressEl) pressEl.textContent = agro.pressure !== null ? `${agro.pressure} hPa` : "—";
        if (vpdEl) vpdEl.textContent = `VPD: ${agro.vpd !== null ? `${agro.vpd} kPa` : "—"}`;
        if (pressTip) {
            if (agro.pressure < 1000) pressTip.textContent = "⛈️ Presión muy baja — frente activo probable";
            else if (agro.pressure < 1010) pressTip.textContent = "🌧️ Presión baja — posible inestabilidad";
            else if (agro.pressure > 1020) pressTip.textContent = "☀️ Presión alta — tiempo estable";
            else pressTip.textContent = "🟡 Presión normal";
        }

        // ── RADIACIÓN ──
        const radEl = document.getElementById("agro-radiation");
        const radTip = document.getElementById("agro-radiation-tip");
        if (radEl) radEl.textContent = agro.solar_radiation !== null ? `${agro.solar_radiation} W/m²` : "—";
        if (radTip) {
            if (agro.solar_radiation > 600) radTip.textContent = "⚡ Radiación alta — fotosíntesis máxima";
            else if (agro.solar_radiation > 200) radTip.textContent = "🌤️ Radiación moderada";
            else radTip.textContent = "☁️ Radiación baja — fotosíntesis limitada";
        }

        // ── SUELO ──
        renderSoilBars(agro);

        // ── TEMPERATURA SUELO ──
        const s0 = document.getElementById("agro-soiltemp-0");
        const s6 = document.getElementById("agro-soiltemp-6");
        const s18 = document.getElementById("agro-soiltemp-18");
        const stTip = document.getElementById("agro-soiltemp-tip");
        if (s0) s0.textContent = agro.soil_temp_surface !== null ? `${agro.soil_temp_surface} ºC` : "—";
        if (s6) s6.textContent = agro.soil_temp_6cm !== null ? `${agro.soil_temp_6cm} ºC` : "—";
        if (s18) s18.textContent = agro.soil_temp_18cm !== null ? `${agro.soil_temp_18cm} ºC` : "—";
        if (stTip && agro.soil_temp_surface !== null) {
            if (agro.soil_temp_surface < 5) stTip.textContent = "❄️ Suelo frío — actividad biológica baja";
            else if (agro.soil_temp_surface < 15) stTip.textContent = "🌱 Temperatura adecuada para germinación";
            else if (agro.soil_temp_surface < 28) stTip.textContent = "✅ Temperatura óptima para actividad microbiana";
            else stTip.textContent = "🔥 Suelo muy caliente — estrés térmico posible";
        }

        // ── HORAS DE FRÍO ──
        const coldEl = document.getElementById("agro-cold-hours");
        const coldTip = document.getElementById("agro-cold-tip");
        if (coldEl) coldEl.textContent = agro.cold_hours_24h ?? "—";
        if (coldTip) {
            const ch = agro.cold_hours_24h;
            if (ch >= 12) coldTip.textContent = "✅ Buena acumulación de frío invernal";
            else if (ch >= 5) coldTip.textContent = "🟡 Acumulación moderada de frío";
            else coldTip.textContent = "⚠️ Pocas horas de frío — monitoriza la vernalización";
        }

        // ── GRANIZO ──
        const hailEl = document.getElementById("agro-hail-risk");
        const hailBar = document.getElementById("agro-hail-bar");
        if (hailEl) hailEl.textContent = `${hailMax.toFixed(0)}%`;
        if (hailBar) {
            hailBar.style.width = `${hailMax}%`;
            hailBar.style.background = hailMax >= 70 ? "#e53935" : hailMax >= 40 ? "#ff9800" : "#4caf50";
        }

        // ── CIERRE AUTOMÁTICO si riesgo >= 35% ──
        if (hailMax >= 35) {
            const fieldId = document.getElementById("field-id-hidden")?.value;
            const statusEl = document.querySelector(".field-status");
            const currentState = statusEl?.dataset?.state || statusEl?.className;
            const alreadyClosed = currentState?.includes("closed") || currentState?.includes("closing");

            if (fieldId && !alreadyClosed) {
                console.warn(`[AgroAgent] Granizo ${hailMax.toFixed(0)}% — cerrando techo`);
                fetch(`/field/update-status/${fieldId}`, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ state: "closed" })
                }).then(() => {
                    if (statusEl) {
                        statusEl.className = "field-status status-closed";
                        statusEl.textContent = "Cerrado";
                    }
                });

                // Banner de aviso
                if (!document.getElementById("hail-auto-close-banner")) {
                    const banner = document.createElement("div");
                    banner.id = "hail-auto-close-banner";
                    banner.innerHTML = `🧊 <strong>Riesgo de granizo ${hailMax.toFixed(0)}%</strong> — Techo cerrado automáticamente`;
                    banner.style.cssText = "position:fixed;top:0;left:0;right:0;z-index:9999;background:#e53935;color:#fff;text-align:center;padding:12px 20px;font-size:14px;font-weight:600;box-shadow:0 2px 8px rgba(0,0,0,0.3);";
                    document.body.prepend(banner);
                    setTimeout(() => banner.remove(), 10000);
                }
            }
        }

        // ── FORECAST ET₀ ──
        renderEt0Forecast(agro.et0_forecast);

        // ── GRÁFICA ET₀ ──
        const toggle = document.getElementById("agro-et0-chart-toggle");
        const panel = document.getElementById("agro-et0-chart-panel");
        if (toggle && panel) {
            toggle.addEventListener("click", () => {
                const isOpen = panel.classList.toggle("open");
                const arrow = toggle.querySelector(".chart-arrow");
                if (arrow) arrow.classList.toggle("rotated", isOpen);
                if (isOpen && !window._agroChartRendered) {
                    window._agroChartRendered = true;
                    renderEt0Chart(agro.et0_hourly_today);
                    renderEt0ChartTip(agro.et0_hourly_today, agro.et0_today, cropType);
                }
            });
        }

        // ── INSIGHTS POR TARJETA (agente local) ──
        const allData = { ...agro, hail_risk_6h: hailMax };
        if (cropType) {
            fetchCardInsights(allData, cropType)
                .then(insights => applyCardInsights(insights))
                .catch(err => console.warn("[CardInsights] error:", err));
        }

    } catch (e) {
        console.error("[AgroData] Error:", e);
    }
}

// ─────────────────────────────────────────────
// INIT
// ─────────────────────────────────────────────
document.addEventListener("DOMContentLoaded", () => {
    const coords = window.fieldCoords;
    const cropType = window.fieldCropType || "";
    if (!coords) return;
    loadAgroData(coords.lat, coords.lon, cropType);

    // Crop type tip inline
    const sel = document.getElementById("crop-type-select");
    const tipEl = document.getElementById("crop-tip");
    if (sel && tipEl) {
        const tips = {
            trigo: "Cereal de invierno. Sensible a la roya y al encamado.", cebada: "Resistente a la sequía.",
            maiz: "Requiere mucho riego en verano.", arroz: "Necesita encharcamiento.", vid: "Control de hongos clave.",
            olivo: "Muy resistente a la sequía.", tomate: "Vigilar Botrytis y trips.", patata: "Riesgo de mildiu en humedad alta.",
            almendro: "Sensible a heladas en floración.", girasol: "Poco exigente en agua.", alfalfa: "Alto consumo hídrico.",
        };
        sel.addEventListener("change", () => {
            tipEl.textContent = tips[sel.value] || "";
        });
        if (tips[sel.value]) tipEl.textContent = tips[sel.value];
    }
});