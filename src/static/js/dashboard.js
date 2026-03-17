import { loadWeatherByCoords } from "./weather.js";

const NIVEL_ORDER = { verde: 0, amarillo: 1, naranja: 2, rojo: 3 };

// ─────────────────────────────────────────────
// WEATHER CODE → DESCRIPCIÓN CORTA
// ─────────────────────────────────────────────
function weatherShort(code) {
    const map = {
        0: "Soleado", 1: "Despejado", 2: "Parcialmente nublado", 3: "Nublado",
        45: "Niebla", 48: "Niebla con escarcha",
        51: "Llovizna ligera", 53: "Llovizna", 55: "Llovizna intensa",
        61: "Lluvia ligera", 63: "Lluvia", 65: "Lluvia intensa",
        71: "Nevada ligera", 73: "Nevada", 75: "Nevada intensa",
        77: "Granizo fino",
        80: "Chubascos", 81: "Chubascos mod.", 82: "Chubascos fuertes",
        95: "Tormenta", 96: "Tormenta c/ granizo", 99: "Tormenta c/ granizo fuerte"
    };
    return map[code] || "—";
}

// ─────────────────────────────────────────────
// UV NIVEL
// ─────────────────────────────────────────────
function uvLabel(uv) {
    if (uv === null || uv === undefined) return "—";
    if (uv <= 2) return `${uv} Bajo`;
    if (uv <= 5) return `${uv} Moderado`;
    if (uv <= 7) return `${uv} Alto`;
    if (uv <= 10) return `${uv} Muy alto`;
    return `${uv} Extremo`;
}

// ─────────────────────────────────────────────
// RENDER PANEL DETALLES CAMPO
// ─────────────────────────────────────────────
function renderFieldPanel(container, summary, alerts) {
    const wc = summary.weathercode ?? 0;

    // Riesgo granizo color
    const hailPct = summary.hail_risk_6h ?? 0;
    const hailColor = hailPct >= 70 ? "#e53935" : hailPct >= 40 ? "#ff9800" : "#4caf50";

    // Humedad suelo en %
    const soilPct = summary.soil_moisture !== null && summary.soil_moisture !== undefined
        ? `${(summary.soil_moisture * 100).toFixed(0)}%` : "—";

    // ET₀ interpretación
    let et0Tip = "";
    if (summary.et0_today !== null && summary.et0_today !== undefined) {
        if (summary.et0_today >= 5) et0Tip = "💧 Regar hoy";
        else if (summary.et0_today >= 3) et0Tip = "💧 Monitorizar";
        else et0Tip = "✅ Sin riego urgente";
    }

    // Alertas
    const TIPOS  = ["calor", "helada", "lluvia", "nieve", "viento", "tormenta", "granizo", "niebla"];
    const LABELS = {
        calor:    "🌡️ Calor",
        helada:   "🥶 Helada",
        lluvia:   "🌧️ Lluvia",
        nieve:    "❄️ Nieve",
        viento:   "💨 Viento",
        tormenta: "⛈️ Tormenta",
        granizo:  "🧊 Granizo",
        niebla:   "🌫️ Niebla",
    };
    let worstNivel = "verde";
    const alertsHTML = alerts ? TIPOS.map(tipo => {
        const nivel = alerts[tipo]?.nivel || "verde";
        const valor = alerts[tipo]?.valor || "";
        if (NIVEL_ORDER[nivel] > NIVEL_ORDER[worstNivel]) worstNivel = nivel;
        return `<div class="fdp-alert-item nivel-${nivel}" title="${valor}">${LABELS[tipo]}</div>`;
    }).join("") : `<div class="fdp-alert-item nivel-verde">Sin alertas activas</div>`;

    const tickerMsg = alerts?.ticker?.length ? alerts.ticker.join(" · ") : "No hay alertas activas";

    // Clase de fondo para el bloque según nivel máximo
    const bloqueClass = worstNivel !== "verde" ? ` bloque-${worstNivel}` : "";

    container.innerHTML = `
        <!-- ALERTAS -->
        <div class="fdp-alerts agro-alerts-block${bloqueClass}">
            <div class="fdp-alerts-title">🚨 Alertas meteorológicas</div>
            <div class="fdp-alert-icons">${alertsHTML}</div>
            <div class="fdp-ticker">${tickerMsg}</div>
        </div>

        <!-- GRID TARJETAS -->
        <div class="fdp-grid">

            <div class="fdp-card">
                <div class="fdp-card-icon">🌤️</div>
                <div class="fdp-label">Tiempo</div>
                <div class="fdp-value" style="font-size:15px;">${weatherShort(wc)}</div>
                <div class="fdp-sub">${summary.temp ?? "—"} ºC · ${summary.wind ?? "—"} km/h</div>
            </div>

            <div class="fdp-card">
                <div class="fdp-card-icon">🌡️</div>
                <div class="fdp-label">Temp. hoy</div>
                <div class="fdp-value">${summary.temp ?? "—"} ºC</div>
                <div class="fdp-sub">↑${summary.temp_max ?? "—"}° ↓${summary.temp_min ?? "—"}°</div>
            </div>

            <div class="fdp-card">
                <div class="fdp-card-icon">💧</div>
                <div class="fdp-label">ET₀ hoy</div>
                <div class="fdp-value">${summary.et0_today !== null && summary.et0_today !== undefined ? summary.et0_today + " mm" : "—"}</div>
                <div class="fdp-sub">${et0Tip}</div>
            </div>

            <div class="fdp-card">
                <div class="fdp-card-icon">🌍</div>
                <div class="fdp-label">Hum. suelo</div>
                <div class="fdp-value">${soilPct}</div>
                <div class="fdp-sub">Capa 0–1 cm</div>
            </div>

            <div class="fdp-card">
                <div class="fdp-card-icon">☀️</div>
                <div class="fdp-label">Índice UV</div>
                <div class="fdp-value">${uvLabel(summary.uv_index)}</div>
                <div class="fdp-sub">${summary.humidity !== null ? `Hum. aire: ${summary.humidity}%` : ""}</div>
            </div>

            <div class="fdp-card">
                <div class="fdp-card-icon">🌀</div>
                <div class="fdp-label">Presión</div>
                <div class="fdp-value">${summary.pressure !== null && summary.pressure !== undefined ? summary.pressure + " hPa" : "—"}</div>
                <div class="fdp-sub">${summary.pressure < 1005 ? "⚠️ Baja — posible mal tiempo" : summary.pressure > 1020 ? "☀️ Alta — tiempo estable" : "Normal"}</div>
            </div>

            <div class="fdp-card">
                <div class="fdp-card-icon">🧊</div>
                <div class="fdp-label">Granizo 6h</div>
                <div class="fdp-value" style="color:${hailColor};">${hailPct.toFixed(0)}%</div>
                <div class="fdp-sub">Riesgo próx. 6 horas</div>
            </div>

            <div class="fdp-card">
                <div class="fdp-card-icon">❄️</div>
                <div class="fdp-label">Horas frío</div>
                <div class="fdp-value">${summary.cold_hours_24h ?? "—"}</div>
                <div class="fdp-sub">últimas 24h (0–7°C)</div>
            </div>

        </div><!-- /fdp-grid -->

        <!-- LINK AL CAMPO -->
        <div style="text-align:center; margin-top:4px;">
            <button class="fdp-goto-btn" id="fdp-goto-${container.id}">Ver campo completo →</button>
        </div>
    `;
}

// ─────────────────────────────────────────────
// CARGAR DATOS DEL PANEL
// ─────────────────────────────────────────────
async function loadFieldPanel(fieldId, lat, lon, container) {
    try {
        const [summaryRes, alertsRes, hailRes] = await Promise.allSettled([
            fetch(`/get-field-summary?lat=${lat}&lon=${lon}`).then(r => r.json()),
            fetch(`/get-aemet-alerts?lat=${lat}&lon=${lon}`).then(r => r.json()),
            fetch(`/get-hail-prediction?lat=${lat}&lon=${lon}`).then(r => r.json()),
        ]);

        const summary = summaryRes.status === "fulfilled" ? summaryRes.value : {};
        const alerts = alertsRes.status === "fulfilled" ? alertsRes.value : null;
        const hail = hailRes.status === "fulfilled" ? hailRes.value : [];

        // Granizo próximas 6h
        const now = new Date();
        const in6h = new Date(now.getTime() + 6 * 3600 * 1000);
        summary.hail_risk_6h = Array.isArray(hail)
            ? Math.max(0, ...hail.filter(h => { const t = new Date(h.time); return t >= now && t <= in6h; }).map(h => h.hail_probability))
            : 0;

        renderFieldPanel(container, summary, alerts);

        const gotoBtn = container.querySelector(`#fdp-goto-${container.id}`);
        if (gotoBtn) {
            gotoBtn.addEventListener("click", (e) => {
                e.stopPropagation();
                window.location.href = `/field/edit/${fieldId}`;
            });
        }

    } catch (e) {
        container.innerHTML = `<div class="fdp-loading" style="color:#e53935;">⚠️ Error cargando datos del campo.</div>`;
        console.error("[FieldPanel]", e);
    }
}

// ─────────────────────────────────────────────
// INIT
// ─────────────────────────────────────────────
document.addEventListener("DOMContentLoaded", () => {

    updateDateTime();
    setInterval(updateDateTime, 1000);

    // Weather por geolocalización
    if (navigator.geolocation) {
        navigator.geolocation.getCurrentPosition(
            (position) => {
                loadWeatherByCoords(position.coords.latitude, position.coords.longitude);
            },
            () => {},
            { enableHighAccuracy: true, timeout: 15000, maximumAge: 0 }
        );
        setInterval(() => {
            navigator.geolocation.getCurrentPosition(pos => {
                loadWeatherByCoords(pos.coords.latitude, pos.coords.longitude);
            });
        }, 60 * 60 * 1000);
    }

    const dashboard = document.querySelector(".dashboard") || document.querySelector(".main-content") || document;

    // Estado de paneles cargados (por fieldId)
    const panelLoaded = {};

    // ── CLICK EN FILAS ──
    dashboard.addEventListener("click", (e) => {
        const row = e.target.closest(".field-row");
        if (!row) return;
        const fieldId = row.dataset.id;

        // Botón techo
        if (e.target.closest(".action-btn")) {
            toggleRoof(row, row.querySelector(".action-btn"), fieldId);
            return;
        }

        // Botón detalles
        const detailBtn = e.target.closest(".field-detail-btn");
        if (detailBtn) {
            const lat = parseFloat(detailBtn.dataset.lat);
            const lon = parseFloat(detailBtn.dataset.lon);
            const panel = document.getElementById(`field-panel-${fieldId}`);
            const inner = document.getElementById(`field-panel-inner-${fieldId}`);

            if (!panel || !inner || !lat || !lon) return;

            const isOpen = panel.classList.toggle("open");
            detailBtn.classList.toggle("open", isOpen);

            if (isOpen && !panelLoaded[fieldId]) {
                panelLoaded[fieldId] = true;
                loadFieldPanel(fieldId, lat, lon, inner);
            }
            return;
        }

        // Click en el resto de la fila → ir al campo
        if (!e.target.closest(".field-buttons")) {
            window.location.href = `/field/edit/${fieldId}`;
        }
    });

    // ── AÑADIR CAMPO ──
    const addBtn = document.querySelector(".add-field-btn");
    if (addBtn) {
        addBtn.addEventListener("click", () => { window.location.href = "/field/new"; });
    }

    // ── ACTUALIZAR SIDEBAR con datos en vivo ──
    function updateSidebarAlerts(fieldId) {
        const hailEl = document.getElementById(`alerts-${fieldId}`);
        const sidebarHail = document.getElementById("sidebar-hail-pct");
        const sidebarAemet = document.getElementById("sidebar-aemet-level");
        if (sidebarHail) {
            const hailSpan = document.getElementById(`hail-${fieldId}`) || document.querySelector("[id^='hail-']");
            if (hailSpan) sidebarHail.textContent = hailSpan.textContent;
        }
        if (sidebarAemet) {
            const bar = document.getElementById(`alert-bar-${fieldId}`);
            if (bar) {
                const level = [...bar.classList].find(c => c.startsWith("alert-bar-"))?.replace("alert-bar-", "") || "verde";
                const labels = { verde: "Sin alertas", amarillo: "Amarilla", naranja: "Naranja", rojo: "Roja" };
                sidebarAemet.textContent = labels[level] || level;
                sidebarAemet.style.color = level === "verde" ? "#7FB069" : level === "amarillo" ? "#D4A853" : level === "naranja" ? "#E87040" : "#E53935";
            }
        }
    }

    // Actualizar sidebar tras cargar alertas (3s delay)
    setTimeout(() => {
        const firstField = document.querySelector(".field-row");
        if (firstField) updateSidebarAlerts(firstField.dataset.id);
    }, 3000);

    // ── RELOJ ──
    function updateDateTime() {
        const timeEl = document.getElementById("current-time");
        const dateEl = document.getElementById("current-date");
        if (!timeEl || !dateEl) return;
        const now = new Date();
        timeEl.textContent = now.toLocaleTimeString("es-ES", { hour: "2-digit", minute: "2-digit", hour12: false });
        const date = now.toLocaleDateString("es-ES", { weekday: "long", day: "numeric", month: "long", year: "numeric" });
        dateEl.textContent = date.charAt(0).toUpperCase() + date.slice(1);
    }

    // ── TECHO ──
    function toggleRoof(row, button, fieldId) {
        const status = row.querySelector(".field-status");
        let currentState = row.dataset.state;
        if (currentState === "opening" || currentState === "closing") return;

        button.disabled = true;
        button.classList.add("disabled");

        let finalState, textDuring, textFinal, nextButtonText;
        if (currentState === "open") {
            currentState = "closing"; finalState = "closed";
            textDuring = "Cerrando..."; textFinal = "Cerrado"; nextButtonText = "Apertura manual";
        } else {
            currentState = "opening"; finalState = "open";
            textDuring = "Abriendo..."; textFinal = "Abierto"; nextButtonText = "Cierre manual";
        }

        status.className = `field-status status-${currentState}`;
        status.textContent = textDuring;
        row.dataset.state = currentState;

        setTimeout(async () => {
            try {
                await fetch(`/field/update-status/${fieldId}`, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ state: finalState })
                });
                row.dataset.state = finalState;
                status.className = `field-status status-${finalState}`;
                status.textContent = textFinal;
                button.textContent = nextButtonText;
                button.disabled = false;
                button.classList.remove("disabled");
            } catch {
                alert("Error al actualizar estado.");
                button.disabled = false;
                button.classList.remove("disabled");
            }
        }, 3000);
    }
});