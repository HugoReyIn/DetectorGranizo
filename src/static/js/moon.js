// moon.js — Cálculo astronómico de fase lunar + visualización canvas

(function () {

    // ─────────────────────────────────────────────
    // CÁLCULO DE FASE LUNAR
    // Basado en algoritmo de Jean Meeus "Astronomical Algorithms"
    // ─────────────────────────────────────────────

    function getMoonAge(date) {
        const KNOWN_NEW_MOON = new Date(Date.UTC(2000, 0, 6, 18, 14, 0));
        const SYNODIC_MONTH  = 29.530588853;
        const diffDays = (date - KNOWN_NEW_MOON) / (1000 * 60 * 60 * 24);
        const age = ((diffDays % SYNODIC_MONTH) + SYNODIC_MONTH) % SYNODIC_MONTH;
        return age;
    }

    function getMoonFraction(age) {
        return (1 - Math.cos((2 * Math.PI * age) / 29.530588853)) / 2;
    }

    function getMoonPhaseInfo(age) {
        const f = age / 29.530588853;
        if (f < 0.025 || f >= 0.975) return { name: "Luna nueva",        emoji: "🌑", key: "nueva" };
        if (f < 0.225)                return { name: "Cuarto creciente",  emoji: "🌒", key: "creciente" };
        if (f < 0.275)                return { name: "Cuarto creciente",  emoji: "🌓", key: "creciente" };
        if (f < 0.475)                return { name: "Luna llena",        emoji: "🌕", key: "llena" };
        if (f < 0.525)                return { name: "Luna llena",        emoji: "🌕", key: "llena" };
        if (f < 0.725)                return { name: "Cuarto menguante",  emoji: "🌖", key: "menguante" };
        if (f < 0.775)                return { name: "Cuarto menguante",  emoji: "🌗", key: "menguante" };
        return                               { name: "Luna nueva",        emoji: "🌘", key: "nueva" };
    }

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

    function nextPhaseDate(fromDate, targetFraction) {
        const SYNODIC = 29.530588853;
        const age = getMoonAge(fromDate);
        const currentFrac = age / SYNODIC;
        let daysUntil = ((targetFraction - currentFrac) * SYNODIC + SYNODIC) % SYNODIC;
        if (daysUntil < 0.5) daysUntil += SYNODIC;
        const result = new Date(fromDate);
        result.setDate(result.getDate() + Math.round(daysUntil));
        return result;
    }

    function formatDate(date) {
        return date.toLocaleDateString("es-ES", { weekday: "short", day: "numeric", month: "short" });
    }

    // ─────────────────────────────────────────────
    // DIBUJO DEL CANVAS
    //
    // Método: path bezier directo, sin globalCompositeOperation.
    // La zona iluminada se traza como un path cerrado de dos curvas:
    //   1. LIMBO: semicírculo exterior (arco del borde de la luna)
    //   2. TERMINADOR: elipse aplastada (bezier) que separa luz/sombra
    //
    // Variable clave: k = cos(2π·frac)
    //   k =  1  → luna nueva      (ex = r, hoz = 0 area)
    //   k =  0  → cuartos         (ex = 0, terminador vertical)
    //   k = -1  → luna llena      (ex = r al otro lado, todo iluminado)
    //
    // Fases crecientes (frac 0..0.5): limbo en la DERECHA
    //   k > 0 → hoz creciente       (terminador convexo a la izquierda)
    //   k < 0 → gibosa creciente    (terminador cóncavo, bulge a la derecha)
    //
    // Fases menguantes (frac 0.5..1): limbo en la IZQUIERDA
    //   k > 0 → gibosa menguante    (terminador convexo a la derecha)  ← caso actual
    //   k < 0 → hoz menguante       (terminador cóncavo, bulge a la izquierda)
    // ─────────────────────────────────────────────

    function drawMoon(canvas, age) {
        const ctx     = canvas.getContext("2d");
        const W       = canvas.width;
        const H       = canvas.height;
        const cx      = W / 2;
        const cy      = H / 2;
        const r       = W / 2 - 6;
        const SYNODIC = 29.530588853;
        const frac    = age / SYNODIC; // [0,1)
        const illum   = (1 - Math.cos(2 * Math.PI * frac)) / 2;

        ctx.clearRect(0, 0, W, H);

        // Fondo oscuro
        ctx.fillStyle = "#1a1a2e";
        ctx.beginPath();
        ctx.arc(cx, cy, r + 6, 0, Math.PI * 2);
        ctx.fill();

        // Disco oscuro base
        ctx.fillStyle = "#2a2a3e";
        ctx.beginPath();
        ctx.arc(cx, cy, r, 0, Math.PI * 2);
        ctx.fill();

        // ── Zona iluminada ──
        if (illum > 0.001) {
            ctx.save();
            ctx.beginPath();
            ctx.arc(cx, cy, r, 0, Math.PI * 2);
            ctx.clip();

            ctx.fillStyle = "#f0e68c";

            const k   = Math.cos(2 * Math.PI * frac);
            // Asegurar que la hoz mínima sea visible (mín 2px de ancho visual)
            const minEx = 2 / r;
            const ex  = r * Math.max(Math.abs(k), minEx);
            const K   = 0.5523;
            const cpY = r * K;
            const cpX = ex * K;

            ctx.beginPath();

            if (frac < 0.5) {
                // CRECIENTE: limbo derecho
                ctx.moveTo(cx, cy - r);
                ctx.arc(cx, cy, r, -Math.PI / 2, Math.PI / 2);
                if (k > 0) {
                    ctx.bezierCurveTo(cx - cpX, cy + cpY, cx - cpX, cy - cpY, cx, cy - r);
                } else {
                    ctx.bezierCurveTo(cx + cpX, cy + cpY, cx + cpX, cy - cpY, cx, cy - r);
                }
            } else {
                // MENGUANTE: limbo izquierdo
                const fracM = frac - 0.5;
                const kM    = Math.cos(2 * Math.PI * fracM);
                const exM   = r * Math.max(Math.abs(kM), minEx);
                const cpXM  = exM * K;

                ctx.moveTo(cx, cy - r);
                ctx.arc(cx, cy, r, -Math.PI / 2, Math.PI / 2, true);
                if (kM > 0) {
                    ctx.bezierCurveTo(cx + cpXM, cy + cpY, cx + cpXM, cy - cpY, cx, cy - r);
                } else {
                    ctx.bezierCurveTo(cx - cpXM, cy + cpY, cx - cpXM, cy - cpY, cx, cy - r);
                }
            }

            ctx.closePath();
            ctx.fill();
            ctx.restore();
        }

        // Borde sutil
        ctx.strokeStyle = "rgba(255,255,255,0.15)";
        ctx.lineWidth = 1.5;
        ctx.beginPath();
        ctx.arc(cx, cy, r, 0, Math.PI * 2);
        ctx.stroke();

        // Brillo leve
        const gradient = ctx.createRadialGradient(cx + r * 0.3, cy - r * 0.3, 0, cx, cy, r);
        gradient.addColorStop(0, "rgba(255,255,240,0.08)");
        gradient.addColorStop(1, "rgba(0,0,0,0)");
        ctx.fillStyle = gradient;
        ctx.beginPath();
        ctx.arc(cx, cy, r, 0, Math.PI * 2);
        ctx.fill();

        // ── Indicador de % de iluminación como arco exterior ──
        // Arco fino alrededor del disco proporcional a la iluminación
        if (illum > 0.01) {
            ctx.strokeStyle = "rgba(240,230,140,0.45)";
            ctx.lineWidth = 3;
            ctx.beginPath();
            ctx.arc(cx, cy, r + 4, -Math.PI / 2, -Math.PI / 2 + 2 * Math.PI * illum);
            ctx.stroke();
        }
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

        const canvas = document.getElementById("moon-canvas");
        if (canvas) drawMoon(canvas, age);

        const nameEl  = document.getElementById("moon-phase-name");
        const illumEl = document.getElementById("moon-illumination");
        if (nameEl)  nameEl.textContent  = phase;
        if (illumEl) illumEl.textContent = Math.round(illum * 100) + " %";

        const list = document.getElementById("moon-phases-list");
        if (!list) return;

        const PHASES = [
            { frac: 0,    label: "Luna nueva",       icon: "🌑" },
            { frac: 0.25, label: "Cuarto creciente", icon: "🌓" },
            { frac: 0.5,  label: "Luna llena",       icon: "🌕" },
            { frac: 0.75, label: "Cuarto menguante", icon: "🌗" },
        ];

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

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", render);
    } else {
        render();
    }

})();   