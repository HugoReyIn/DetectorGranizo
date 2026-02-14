document.addEventListener("DOMContentLoaded", () => {
    updateDateTime();
    setInterval(updateDateTime, 1000);

    const dashboard = document.querySelector(".dashboard");

    dashboard.addEventListener("click", (e) => {

        const row = e.target.closest(".field-row");
        if (!row) return;

        const fieldId = row.dataset.id;

        /* =========================
           BOTÓN CIERRE / APERTURA
        ========================== */
        if (e.target.classList.contains("action-btn")) {
            e.stopPropagation();
            toggleRoof(e.target);
            return;
        }

        /* =========================
           CLICK EN STATUS
        ========================== */
        if (e.target.classList.contains("field-status")) {
            e.stopPropagation();
            console.log("Click en estado");
            return;
        }

        /* =========================
           CLICK EN FILA → EDITAR
        ========================== */
        if (!e.target.closest(".field-buttons")) {
            window.location.href = `/field/edit/${fieldId}`;
        }
    });

    const addBtn = document.querySelector(".add-field-btn");
    if (addBtn) {
        addBtn.addEventListener("click", () => {
            window.location.href = "/field/new";
        });
    }
});


/* =========================
   RELOJ Y FECHA
========================= */
function updateDateTime() {
    const timeEl = document.getElementById('current-time');
    const dateEl = document.getElementById('current-date');

    if (!timeEl || !dateEl) return;

    const now = new Date();

    const time = now.toLocaleTimeString('es-ES', {
        hour: '2-digit',
        minute: '2-digit',
        hour12: false
    });

    const date = now.toLocaleDateString('es-ES', {
        weekday: 'long',
        day: 'numeric',
        month: 'long',
        year: 'numeric'
    });

    timeEl.textContent = time;
    dateEl.textContent = date.charAt(0).toUpperCase() + date.slice(1);
}


/* =========================
   ABRIR / CERRAR TECHO
========================= */
function toggleRoof(button) {

    const row = button.closest(".field-row");
    const status = row.querySelector(".field-status");
    const currentState = row.dataset.state;

    if (!row || !status) return;

    if (currentState === "opening" || currentState === "closing") return;

    button.disabled = true;
    button.classList.add("disabled");

    let action, finalState, textDuring, textFinal, nextButtonText;

    if (currentState === "open") {
        action = "closing";
        finalState = "closed";
        textDuring = "Cerrando...";
        textFinal = "Cerrado";
        nextButtonText = "Apertura manual";
    } else {
        action = "opening";
        finalState = "open";
        textDuring = "Abriendo...";
        textFinal = "Abierto";
        nextButtonText = "Cierre manual";
    }

    status.className = `field-status status-${action}`;
    status.textContent = textDuring;
    row.dataset.state = action;

    setTimeout(() => {

        status.className = `field-status status-${finalState}`;
        status.textContent = textFinal;
        row.dataset.state = finalState;

        button.textContent = nextButtonText;
        button.disabled = false;
        button.classList.remove("disabled");

        console.log(`Campo actualizado: ${finalState}`);

    }, 3000);
}
