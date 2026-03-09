import { loadWeatherByCoords } from "./weather.js";

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

    // Cargar alertas AEMET para cada campo
    document.querySelectorAll(".field-alerts[data-lat]").forEach(panel => {
        const lat = parseFloat(panel.dataset.lat);
        const lon = parseFloat(panel.dataset.lon);
        if (!lat || !lon) { setAlertPanel(panel, null); return; }
        loadAemetAlerts(panel, lat, lon);
    });

    // Click en filas del dashboard
    const dashboard = document.querySelector(".dashboard");
    dashboard.addEventListener("click", (e) => {
        const row = e.target.closest(".field-row");
        if (!row) return;
        const fieldId = row.dataset.id;

        if (e.target.classList.contains("action-btn")) {
            e.stopPropagation();
            toggleRoof(row, e.target, fieldId);
            return;
        }
        if (!e.target.closest(".field-buttons") && !e.target.closest(".field-alerts")) {
            window.location.href = `/field/edit/${fieldId}`;
        }
    });

    const addBtn = document.querySelector(".add-field-btn");
    if (addBtn) {
        addBtn.addEventListener("click", () => { window.location.href = "/field/new"; });
    }

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

    // ── ALERTAS AEMET ──
    const NIVEL_ORDER = { verde: 0, amarillo: 1, naranja: 2, rojo: 3 };

    async function loadAemetAlerts(panel, lat, lon) {
        try {
            const res = await fetch(`/get-aemet-alerts?lat=${lat}&lon=${lon}`);
            if (!res.ok) throw new Error("HTTP " + res.status);
            const data = await res.json();
            setAlertPanel(panel, data);
        } catch (e) {
            console.warn("AEMET no disponible:", e);
            setAlertPanel(panel, null);
        }
    }

    function setAlertPanel(panel, data) {
        const TIPOS = ["calor", "lluvia", "nieve", "granizo"];
        let peorNivel = "verde";

        TIPOS.forEach(tipo => {
            const iconEl = panel.querySelector(`[id^="alert-${tipo}-"]`);
            if (!iconEl) return;
            const nivel = (data && data[tipo]) ? (data[tipo].nivel || "verde") : "verde";
            iconEl.className = `alert-icon-item nivel-${nivel}`;
            if (NIVEL_ORDER[nivel] > NIVEL_ORDER[peorNivel]) peorNivel = nivel;
        });

        // Barra de color
        const bar = panel.querySelector(".alert-bar");
        if (bar) bar.className = `alert-bar alert-bar-${peorNivel}`;

        // Ticker con fade: un solo span visible, rotando mensajes con CSS animation
        const tickerWrap = panel.querySelector(".alert-ticker-mini");
        const tickerSpan = panel.querySelector(".alert-ticker-mini-text");
        if (!tickerWrap || !tickerSpan) return;

        tickerWrap.className = `alert-ticker-mini ticker-${peorNivel}`;

        const mensajes = (data && data.ticker && data.ticker.length)
            ? data.ticker : ["No hay alertas activas"];

        // Eliminar el segundo span (ya no se usa para scroll)
        const spans = panel.querySelectorAll(".alert-ticker-mini-text");
        spans.forEach((s, i) => { if (i > 0) s.remove(); });

        if (mensajes.length === 1) {
            tickerSpan.textContent = mensajes[0];
            tickerSpan.style.animationDuration = "5s";
        } else {
            // Rotar mensajes cambiando el texto en cada ciclo de animación
            let idx = 0;
            tickerSpan.textContent = mensajes[0];
            // Escuchar el fin de animación para cambiar al siguiente mensaje
            tickerSpan.addEventListener("animationiteration", () => {
                idx = (idx + 1) % mensajes.length;
                tickerSpan.textContent = mensajes[idx];
            });
            // Duración por mensaje: 6s base
            tickerSpan.style.animationDuration = "6s";
        }
    }
});