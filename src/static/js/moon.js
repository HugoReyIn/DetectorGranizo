// moon.js — Cálculo astronómico de fase lunar + visualización canvas

(function () {

    // ─────────────────────────────────────────────
    // CÁLCULO DE FASE LUNAR
    // Basado en algoritmo de Jean Meeus "Astronomical Algorithms"
    // ─────────────────────────────────────────────

    /**
     * Devuelve la fracción del ciclo lunar [0, 1) para una fecha dada.
     * 0 = Luna nueva, 0.25 = Cuarto creciente, 0.5 = Luna llena, 0.75 = Cuarto menguante
     */
    function getMoonAge(date) {
        // Referencia: luna nueva conocida — 6 enero 2000 18:14 UTC
        const KNOWN_NEW_MOON = new Date(Date.UTC(2000, 0, 6, 18, 14, 0));
        const SYNODIC_MONTH  = 29.530588853; // días

        const diffDays = (date - KNOWN_NEW_MOON) / (1000 * 60 * 60 * 24);
        const age = ((diffDays % SYNODIC_MONTH) + SYNODIC_MONTH) % SYNODIC_MONTH;
        return age; // días desde última luna nueva
    }

    function getMoonFraction(age) {
        // Iluminación como fracción [0,1]
        return (1 - Math.cos((2 * Math.PI * age) / 29.530588853)) / 2;
    }

    function getMoonPhaseInfo(age) {
        const f = age / 29.530588853; // fracción del ciclo [0,1)
        if (f < 0.025 || f >= 0.975) return { name: "Luna nueva",        emoji: "🌑", key: "nueva" };
        if (f < 0.225)                return { name: "Cuarto creciente",  emoji: "🌒", key: "creciente" };
        if (f < 0.275)                return { name: "Cuarto creciente",  emoji: "🌓", key: "creciente" };
        if (f < 0.475)                return { name: "Luna llena",        emoji: "🌕", key: "llena" };
        if (f < 0.525)                return { name: "Luna llena",        emoji: "🌕", key: "llena" };
        if (f < 0.725)                return { name: "Cuarto menguante",  emoji: "🌖", key: "menguante" };
        if (f < 0.775)                return { name: "Cuarto menguante",  emoji: "🌗", key: "menguante" };
        return                               { name: "Luna nueva",        emoji: "🌘", key: "nueva" };
    }

    // Nombres precisos por fracción de ciclo
    function getExactPhaseName(f) {
        if (f < 0.025 || f >= 0.975) return "Luna nueva";
        if (f < 0.25)                 return "Creciente gibosa";
        if (f < 0.275)                return "Cuarto creciente";
        if (f < 0.5)                  return "Gibosa creciente";
        if (f < 0.525)                return "Luna llena";
        if (f < 0.75)                 return "Gibosa menguante";
        if (f < 0.775)                return "Cuarto menguante";
        return "Menguante gibosa";
    }

    /**
     * Encuentra la fecha de la próxima ocurrencia de una fase concreta.
     * targetFraction: 0=nueva, 0.25=creciente, 0.5=llena, 0.75=menguante
     */
    function nextPhaseDate(fromDate, targetFraction) {
        const SYNODIC = 29.530588853;
        const age = getMoonAge(fromDate);
        const currentFrac = age / SYNODIC;
        let daysUntil = ((targetFraction - currentFrac) * SYNODIC + SYNODIC) % SYNODIC;
        if (daysUntil < 0.5) daysUntil += SYNODIC; // evitar "ya pasó hace horas"
        const result = new Date(fromDate);
        result.setDate(result.getDate() + Math.round(daysUntil));
        return result;
    }

    function formatDate(date) {
        return date.toLocaleDateString("es-ES", { weekday: "short", day: "numeric", month: "short" });
    }

    // ─────────────────────────────────────────────
    // DIBUJO DEL CANVAS
    // ─────────────────────────────────────────────

    /**
     * Dibuja la luna en el canvas con la parte iluminada correcta.
     * age: días desde luna nueva
     */
    function drawMoon(canvas, age) {
        const ctx    = canvas.getContext("2d");
        const W      = canvas.width;
        const H      = canvas.height;
        const cx     = W / 2;
        const cy     = H / 2;
        const r      = W / 2 - 6;
        const SYNODIC = 29.530588853;
        const frac   = age / SYNODIC; // [0,1)

        ctx.clearRect(0, 0, W, H);

        // Fondo oscuro (cielo)
        ctx.fillStyle = "#1a1a2e";
        ctx.beginPath();
        ctx.arc(cx, cy, r + 6, 0, Math.PI * 2);
        ctx.fill();

        // Disco de la luna (lado oscuro base)
        ctx.fillStyle = "#2a2a3e";
        ctx.beginPath();
        ctx.arc(cx, cy, r, 0, Math.PI * 2);
        ctx.fill();

        // ── Parte iluminada ──
        // La luna crece por la derecha (hemisferio norte)
        // frac=0: nueva (todo oscuro), frac=0.5: llena (todo claro)
        // frac=0.25: cuarto creciente (mitad derecha iluminada)
        // frac=0.75: cuarto menguante (mitad izquierda iluminada)

        ctx.save();
        ctx.beginPath();
        ctx.arc(cx, cy, r, 0, Math.PI * 2);
        ctx.clip();

        if (frac < 0.5) {
            // Fase creciente: iluminado derecha → llena
            const t = frac * 2; // [0,1]: 0=nueva, 1=llena
            // Elipse que va de r (ancho) a 0 a medida que crece
            const ex = r * Math.abs(1 - 2 * t); // ancho del terminador
            const waxing = t <= 0.5;

            ctx.fillStyle = "#f0e68c";

            // Semicírculo iluminado (derecha)
            ctx.beginPath();
            ctx.arc(cx, cy, r, -Math.PI / 2, Math.PI / 2); // mitad derecha
            ctx.closePath();
            ctx.fill();

            // Elipse del terminador
            ctx.globalCompositeOperation = waxing ? "destination-out" : "source-over";
            ctx.fillStyle = waxing ? "rgba(0,0,0,1)" : "#f0e68c";
            ctx.beginPath();
            ctx.ellipse(cx, cy, ex, r, 0, -Math.PI / 2, Math.PI / 2);
            ctx.closePath();
            ctx.fill();

        } else {
            // Fase menguante: llena → iluminado izquierda → nueva
            const t = (frac - 0.5) * 2; // [0,1]: 0=llena, 1=nueva
            const ex = r * Math.abs(1 - 2 * t);
            const waning = t <= 0.5;

            ctx.fillStyle = "#f0e68c";

            // Semicírculo iluminado (izquierda)
            ctx.beginPath();
            ctx.arc(cx, cy, r, Math.PI / 2, -Math.PI / 2); // mitad izquierda
            ctx.closePath();
            ctx.fill();

            ctx.globalCompositeOperation = waning ? "destination-out" : "source-over";
            ctx.fillStyle = waning ? "rgba(0,0,0,1)" : "#f0e68c";
            ctx.beginPath();
            ctx.ellipse(cx, cy, ex, r, 0, Math.PI / 2, -Math.PI / 2, true);
            ctx.closePath();
            ctx.fill();
        }

        ctx.restore();

        // Borde sutil
        ctx.strokeStyle = "rgba(255,255,255,0.15)";
        ctx.lineWidth = 1.5;
        ctx.beginPath();
        ctx.arc(cx, cy, r, 0, Math.PI * 2);
        ctx.stroke();

        // Brillo leve en el limbo iluminado
        const gradient = ctx.createRadialGradient(cx + r * 0.3, cy - r * 0.3, 0, cx, cy, r);
        gradient.addColorStop(0, "rgba(255,255,240,0.08)");
        gradient.addColorStop(1, "rgba(0,0,0,0)");
        ctx.fillStyle = gradient;
        ctx.beginPath();
        ctx.arc(cx, cy, r, 0, Math.PI * 2);
        ctx.fill();
    }

    // ─────────────────────────────────────────────
    // RENDER DOM
    // ─────────────────────────────────────────────

    function render() {
        const now    = new Date();
        const age    = getMoonAge(now);
        const frac   = age / 29.530588853;
        const illum  = getMoonFraction(age);
        const phase  = getExactPhaseName(frac);

        // Canvas
        const canvas = document.getElementById("moon-canvas");
        if (canvas) drawMoon(canvas, age);

        // Nombre e iluminación
        const nameEl  = document.getElementById("moon-phase-name");
        const illumEl = document.getElementById("moon-illumination");
        if (nameEl)  nameEl.textContent  = phase;
        if (illumEl) illumEl.textContent = Math.round(illum * 100) + " %";

        // Próximas 4 fases
        const list = document.getElementById("moon-phases-list");
        if (!list) return;

        const PHASES = [
            { frac: 0,    label: "Luna nueva",       icon: "🌑" },
            { frac: 0.25, label: "Cuarto creciente", icon: "🌓" },
            { frac: 0.5,  label: "Luna llena",       icon: "🌕" },
            { frac: 0.75, label: "Cuarto menguante", icon: "🌗" },
        ];

        // Generar las próximas 4 ocurrencias en orden cronológico
        const upcoming = [];
        PHASES.forEach(p => {
            const d = nextPhaseDate(now, p.frac);
            upcoming.push({ ...p, date: d });
        });
        upcoming.sort((a, b) => a.date - b.date);
        const next4 = upcoming.slice(0, 4);

        list.innerHTML = next4.map(p => `
            <div class="moon-phase-row">
                <span class="moon-phase-icon">${p.icon}</span>
                <div class="moon-phase-info">
                    <span class="moon-phase-row-name">${p.label}</span>
                    <span class="moon-phase-row-date">${formatDate(p.date)}</span>
                </div>
            </div>
        `).join("");
    }

    // Esperar a que el DOM esté listo
    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", render);
    } else {
        render();
    }

})();