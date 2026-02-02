// --- Fecha y hora en tiempo real (sin segundos) ---
function updateDateTime() {
    const now = new Date();
    const time = now.toLocaleTimeString('es-ES', { hour: '2-digit', minute: '2-digit' });
    const date = now.toLocaleDateString('es-ES', { weekday:'long', day:'numeric', month:'long', year:'numeric' });
    document.getElementById('current-time').textContent = time;
    document.getElementById('current-date').textContent = date.charAt(0).toUpperCase() + date.slice(1);
}
updateDateTime();
setInterval(updateDateTime, 1000);

// --- Toggle techos ---
function toggleRoof(button) {
    const row = button.closest(".field-row");
    const status = row.querySelector(".field-status");

    if (row.dataset.state === "opening" || row.dataset.state === "closing") return;

    button.disabled = true;
    button.classList.add("disabled");

    let action, finalState, textDuring, textFinal;

    if (row.dataset.state === "open") {
        action = "closing"; finalState = "closed"; textDuring = "Cerrando..."; textFinal = "Cerrado";
    } else {
        action = "opening"; finalState = "open"; textDuring = "Abriendo..."; textFinal = "Abierto";
    }

    status.className = "field-status status-" + action;
    status.textContent = textDuring;
    row.dataset.state = action;

    setTimeout(() => {
        status.className = "field-status status-" + finalState;
        status.textContent = textFinal;
        row.dataset.state = finalState;
        button.textContent = finalState === "open" ? "Cierre manual" : "Apertura manual";
        button.disabled = false;
        button.classList.remove("disabled");
    }, 3000);
}

// --- Añadir nuevo campo ---
function addField() {
    const dashboard = document.querySelector(".dashboard");
    const count = document.querySelectorAll(".field-row").length + 1;
    const row = document.createElement("div");
    row.className = "field-row";
    row.dataset.state = "open";
    row.innerHTML = `
        <div class="field-info">
            <h3>Campo ${count}</h3>
            <span>Ubicación desconocida</span>
        </div>
        <div class="field-status status-open">Abierto</div>
        <div class="field-buttons">
            <button class="action-btn" onclick="toggleRoof(this)">Cierre manual</button>
            <button class="action-btn delete-btn" onclick="deleteField(this)">Eliminar campo</button>
        </div>
    `;
    dashboard.insertBefore(row, document.querySelector(".add-field-btn"));
}

// --- Eliminar campo ---
function deleteField(button) {
    const row = button.closest(".field-row");
    row.remove();
}
