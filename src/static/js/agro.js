// agro.js — Datos agronómicos completos para field.html

const LEVEL_ORDER = { verde: 0, amarillo: 1, naranja: 2, rojo: 3 };

// ─────────────────────────────────────────────
// RECOMENDACIONES POR CULTIVO
// ─────────────────────────────────────────────
const CROP_TIPS = {
    trigo:       { et0_threshold: 4, cold_optimal: [300, 600], frost_risk: -2 },
    cebada:      { et0_threshold: 3.5, cold_optimal: [400, 700], frost_risk: -3 },
    maiz:        { et0_threshold: 6, cold_optimal: null, frost_risk: 0 },
    arroz:       { et0_threshold: 7, cold_optimal: null, frost_risk: 5 },
    vid:         { et0_threshold: 4, cold_optimal: [200, 600], frost_risk: -1 },
    olivo:       { et0_threshold: 3, cold_optimal: [200, 400], frost_risk: -5 },
    tomate:      { et0_threshold: 5, cold_optimal: null, frost_risk: 2 },
    patata:      { et0_threshold: 4.5, cold_optimal: null, frost_risk: -1 },
    almendro:    { et0_threshold: 3.5, cold_optimal: [300, 500], frost_risk: -2 },
    girasol:     { et0_threshold: 5, cold_optimal: null, frost_risk: 0 },
    alfalfa:     { et0_threshold: 7, cold_optimal: null, frost_risk: -4 },
    default:     { et0_threshold: 4, cold_optimal: null, frost_risk: -1 }
};

function getCropConfig(cropType) {
    return CROP_TIPS[cropType] || CROP_TIPS.default;
}

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
// RECOMENDACIONES VÍA CLAUDE API
// ─────────────────────────────────────────────

function buildContextPrompt(data, cropType, alerts, moonPhase) {
    const now = new Date();
    const month = now.toLocaleString("es-ES", { month: "long" });
    const crop = cropType || "cultivo no especificado";

    const alertLines = alerts ? ["calor", "lluvia", "nieve", "granizo"]
        .filter(t => alerts[t]?.nivel && alerts[t].nivel !== "verde")
        .map(t => `- Alerta AEMET ${alerts[t].nivel.toUpperCase()} por ${t}`)
        .join("\n") : "";

    return `Eres un agrónomo experto. Analiza los datos actuales del terreno y genera recomendaciones precisas para el agricultor.

CULTIVO: ${crop}
MES: ${month}
FASE LUNAR: ${moonPhase || "no disponible"}

DATOS METEOROLÓGICOS Y DEL SUELO:
- Temperatura actual: ${data.temp ?? "—"}°C (máx ${data.temp_max ?? "—"}°C / mín ${data.temp_min_today ?? "—"}°C)
- ET₀ hoy: ${data.et0_today ?? "—"} mm/día (demanda evapotranspirativa)
- Lluvia prevista hoy: ${data.rain_today ?? "—"} mm
- Humedad del suelo superficie (0-1cm): ${data.soil_moisture_0 !== null && data.soil_moisture_0 !== undefined ? (data.soil_moisture_0 * 100).toFixed(0) + "%" : "—"}
- Humedad suelo 1-3cm: ${data.soil_moisture_1 !== null && data.soil_moisture_1 !== undefined ? (data.soil_moisture_1 * 100).toFixed(0) + "%" : "—"}
- Temperatura suelo superficie: ${data.soil_temp_surface ?? "—"}°C
- Índice UV máx. hoy: ${data.uv_max_today ?? "—"}
- Presión atmosférica: ${data.pressure ?? "—"} hPa
- VPD (déficit presión vapor): ${data.vpd ?? "—"} kPa
- Radiación solar: ${data.solar_radiation ?? "—"} W/m²
- Horas de frío (últimas 24h, 0-7°C): ${data.cold_hours_24h ?? "—"}h
- Riesgo de granizo próximas 6h (IA): ${data.hail_risk_6h !== undefined ? data.hail_risk_6h.toFixed(0) + "%" : "—"}
- Humedad relativa del aire: ${data.humidity ?? "—"}%
${alertLines ? "\nALERTAS AEMET ACTIVAS:\n" + alertLines : "\nSin alertas AEMET activas."}

Genera entre 4 y 7 recomendaciones agronómicas. Mezcla acciones urgentes del día con tareas semanales propias del cultivo en esta época del año.

Responde ÚNICAMENTE con un array JSON válido, sin markdown ni texto adicional. Cada elemento tiene:
- "icon": emoji relevante
- "level": "danger" | "warning" | "info" | "ok"
- "type": "urgente" | "semanal"  
- "title": título corto (máx 6 palabras)
- "text": explicación concreta y accionable (1-2 frases)

Criterios de nivel: danger=riesgo inmediato para el cultivo, warning=acción recomendada hoy, info=tarea de la semana, ok=condición favorable.`;
}

async function fetchClaudeRecommendations(data, cropType, alerts, moonPhase) {
    const prompt = buildContextPrompt(data, cropType, alerts, moonPhase);

    const response = await fetch("/get-ai-recommendations", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ prompt })
    });

    if (!response.ok) throw new Error(`HTTP ${response.status}`);

    const recos = await response.json();
    if (recos.error) throw new Error(recos.error);
    return recos;
}

// ─────────────────────────────────────────────
// RENDER RECOMENDACIONES — UI RICA
// ─────────────────────────────────────────────
function renderRecommendations(recos) {
    const list = document.getElementById("agro-reco-list");
    if (!list) return;

    const urgentes  = recos.filter(r => r.type === "urgente");
    const semanales = recos.filter(r => r.type === "semanal");
    const resto     = recos.filter(r => !r.type);

    const renderGroup = (items, groupLabel) => {
        if (!items.length) return "";
        return `
            <div class="agro-reco-group-label">${groupLabel}</div>
            ${items.map(r => `
                <div class="agro-reco-item agro-reco-${r.level}">
                    <span class="agro-reco-icon">${r.icon}</span>
                    <div class="agro-reco-body">
                        ${r.title ? `<span class="agro-reco-title">${r.title}</span>` : ""}
                        <span class="agro-reco-text">${r.text}</span>
                    </div>
                </div>
            `).join("")}
        `;
    };

    list.innerHTML =
        renderGroup(urgentes,  "🔴 Acciones urgentes — hoy") +
        renderGroup(semanales, "📅 Tareas de la semana") +
        renderGroup(resto, "📋 Recomendaciones");
}

function renderRecommendationsLoading() {
    const list = document.getElementById("agro-reco-list");
    if (!list) return;
    list.innerHTML = `
        <div class="agro-reco-loading-wrap">
            <div class="agro-reco-spinner"></div>
            <span>Analizando datos del campo con IA...</span>
        </div>
        ${[1,2,3,4].map(() => `<div class="agro-reco-skeleton"></div>`).join("")}
    `;
}

function renderRecommendationsError(fallbackRecos) {
    const list = document.getElementById("agro-reco-list");
    if (!list) return;
    const fallbackHtml = fallbackRecos.map(r => `
        <div class="agro-reco-item agro-reco-${r.level}">
            <span class="agro-reco-icon">${r.icon}</span>
            <div class="agro-reco-body">
                <span class="agro-reco-text">${r.text}</span>
            </div>
        </div>
    `).join("");
    list.innerHTML = `
        <div class="agro-reco-item agro-reco-info" style="margin-bottom:8px;">
            <span class="agro-reco-icon">ℹ️</span>
            <div class="agro-reco-body">
                <span class="agro-reco-text">Recomendaciones básicas (IA no disponible).</span>
            </div>
        </div>
        ${fallbackHtml}
    `;
}

// ─────────────────────────────────────────────
// RENDER ALERTAS AEMET EN FIELD
// ─────────────────────────────────────────────
function renderAgroAlerts(data) {
    const TIPOS = ["calor", "lluvia", "nieve", "granizo"];
    let worst = "verde";

    TIPOS.forEach(tipo => {
        const el = document.getElementById(`agro-alert-${tipo}`);
        if (!el) return;
        const nivel = data && data[tipo] ? (data[tipo].nivel || "verde") : "verde";
        el.className = `agro-alert-item nivel-${nivel}`;
        if (LEVEL_ORDER[nivel] > LEVEL_ORDER[worst]) worst = nivel;
    });

    const bar = document.getElementById("agro-alert-bar");
    if (bar) bar.className = `agro-alert-bar-inline alert-bar-${worst}`;

    const ticker = document.getElementById("agro-alert-ticker");
    if (ticker) {
        const msgs = data && data.ticker && data.ticker.length ? data.ticker : ["No hay alertas activas"];
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
// MAIN: CARGA DATOS AGRONÓMICOS
// ─────────────────────────────────────────────

// ─────────────────────────────────────────────
// RECOMENDACIONES ESTÁTICAS (fallback)
// ─────────────────────────────────────────────
function buildRecommendations(data, cropType) {
    const cfg = getCropConfig(cropType);
    const recos = [];

    if (data.et0_today !== null && data.et0_today !== undefined) {
        if (data.et0_today >= cfg.et0_threshold) {
            recos.push({ icon: "💧", level: "warning", type: "urgente",
                text: `ET₀ alta (${data.et0_today} mm/día). Se recomienda regar hoy para evitar estrés hídrico.` });
        } else if (data.rain_today && data.rain_today >= data.et0_today) {
            recos.push({ icon: "✅", level: "ok", type: "semanal",
                text: `La lluvia prevista (${data.rain_today} mm) cubre la demanda ET₀ (${data.et0_today} mm). No es necesario regar.` });
        } else {
            recos.push({ icon: "💧", level: "info", type: "semanal",
                text: `ET₀ moderada (${data.et0_today} mm/día). Monitoriza la humedad del suelo.` });
        }
    }

    if (data.hail_risk_6h !== undefined) {
        if (data.hail_risk_6h >= 70)
            recos.push({ icon: "🧊", level: "danger", type: "urgente",
                text: `Riesgo alto de granizo en las próximas 6h (${data.hail_risk_6h}%). Activa protecciones.` });
        else if (data.hail_risk_6h >= 40)
            recos.push({ icon: "🧊", level: "warning", type: "urgente",
                text: `Riesgo moderado de granizo (${data.hail_risk_6h}%). Mantente atento a las alertas.` });
    }

    if (data.temp_min_today !== null && data.temp_min_today !== undefined) {
        if (data.temp_min_today <= cfg.frost_risk)
            recos.push({ icon: "🥶", level: "danger", type: "urgente",
                text: `Temperatura mínima prevista: ${data.temp_min_today}°C. Riesgo de helada. Protege el cultivo.` });
        else if (data.temp_min_today <= cfg.frost_risk + 3)
            recos.push({ icon: "❄️", level: "warning", type: "urgente",
                text: `Temperatura mínima (${data.temp_min_today}°C) próxima al umbral de helada. Vigilancia recomendada.` });
    }

    if (data.uv_max_today >= 7)
        recos.push({ icon: "☀️", level: "warning", type: "semanal",
            text: `Índice UV muy alto (${data.uv_max_today}). Evita tratamientos fitosanitarios en horas centrales.` });

    if (data.soil_moisture_0 !== null && data.soil_moisture_0 !== undefined) {
        const pct = (data.soil_moisture_0 * 100).toFixed(0);
        if (data.soil_moisture_0 < 0.1)
            recos.push({ icon: "🏜️", level: "danger", type: "urgente",
                text: `Suelo muy seco en superficie (${pct}%). Riego urgente recomendado.` });
        else if (data.soil_moisture_0 > 0.45)
            recos.push({ icon: "🌊", level: "warning", type: "semanal",
                text: `Suelo saturado (${pct}%). Riesgo de asfixia radicular o enfermedades fúngicas.` });
    }

    if (data.vpd !== null && data.vpd > 2.0)
        recos.push({ icon: "🌬️", level: "warning", type: "semanal",
            text: `VPD alto (${data.vpd} kPa). Condiciones de estrés hídrico. Considera riego de apoyo.` });

    if (recos.length === 0)
        recos.push({ icon: "✅", level: "ok", type: "semanal",
            text: "Condiciones agronómicas favorables. No hay recomendaciones urgentes." });

    return recos;
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
                }
            });
        }

        // ── RECOMENDACIONES IA ──
        const allData = { ...agro, hail_risk_6h: hailMax };
        const fallbackRecos = buildRecommendations(allData, cropType);

        // Obtener fase lunar del DOM si está disponible
        const moonPhase = document.getElementById("moon-phase-name")?.textContent || "";

        renderRecommendationsLoading();

        try {
            const aiRecos = await fetchClaudeRecommendations(allData, cropType, alerts, moonPhase);
            renderRecommendations(aiRecos);
        } catch (aiErr) {
            console.warn("[AgroIA] Claude no disponible, usando fallback:", aiErr);
            renderRecommendationsError(fallbackRecos);
        }

        // Botón regenerar
        const regenBtn = document.getElementById("agro-reco-regen");
        if (regenBtn) {
            regenBtn.addEventListener("click", async () => {
                regenBtn.disabled = true;
                regenBtn.textContent = "⏳ Regenerando...";
                renderRecommendationsLoading();
                try {
                    const moonPhaseNow = document.getElementById("moon-phase-name")?.textContent || "";
                    const aiRecos = await fetchClaudeRecommendations(allData, cropType, alerts, moonPhaseNow);
                    renderRecommendations(aiRecos);
                } catch {
                    renderRecommendationsError(fallbackRecos);
                } finally {
                    regenBtn.disabled = false;
                    regenBtn.textContent = "🔄 Regenerar";
                }
            });
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