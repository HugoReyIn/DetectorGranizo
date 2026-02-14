document.addEventListener("DOMContentLoaded", () => {
    updateDateTime();
    setInterval(updateDateTime, 1000);

    const dashboard = document.querySelector(".dashboard");

    dashboard.addEventListener("click", async (e) => {

        const row = e.target.closest(".field-row");
        if (!row) return;

        const fieldId = row.dataset.id;

        // =========================
        // BOTÓN CIERRE / APERTURA
        // =========================
        if (e.target.classList.contains("action-btn")) {
            e.stopPropagation();
            await toggleRoof(row, e.target);
            return;
        }

        // =========================
        // CLICK EN STATUS
        // =========================
        if (e.target.classList.contains("field-status")) {
            e.stopPropagation();
            console.log("Click en estado");
            return;
        }

        // =========================
        // CLICK EN FILA → EDITAR
        // =========================
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

// =========================
// RELOJ Y FECHA
// =========================
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

// =========================
// ABRIR / CERRAR TECHO
// =========================
async function toggleRoof(row, button) {
    const status = row.querySelector(".field-status");
    let currentState = row.dataset.state;

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

    // Animación local
    status.className = `field-status status-${action}`;
    status.textContent = textDuring;
    row.dataset.state = action;

    // =========================
    // Guardar en DB
    // =========================
    try {
        const res = await fetch(`/field/update-state/${row.dataset.id}`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ state: finalState })
        });

        if (!res.ok) throw new Error("Error al actualizar estado en DB");

        // Después de 3s, mostrar estado final
        setTimeout(() => {
            status.className = `field-status status-${finalState}`;
            status.textContent = textFinal;
            row.dataset.state = finalState;

            button.textContent = nextButtonText;
            button.disabled = false;
            button.classList.remove("disabled");
        }, 3000);

    } catch (err) {
        alert("No se pudo actualizar el estado en el servidor");
        // revertir estado local si falla
        status.className = `field-status status-${currentState}`;
        status.textContent = currentState === "open" ? "Abierto" : "Cerrado";
        row.dataset.state = currentState;
        button.disabled = false;
        button.classList.remove("disabled");
    }
}
