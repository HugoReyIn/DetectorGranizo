/**
 * Lógica del Dashboard - Detector de Granizo
 */

document.addEventListener("DOMContentLoaded", () => {
    // Inicializar el reloj al cargar la página
    updateDateTime();
    setInterval(updateDateTime, 1000);

    // Delegación de eventos para toggles y eliminaciones dinámicas
    document.querySelector(".dashboard").addEventListener("click", e => {
        if (e.target.classList.contains("action-btn")) {
            toggleRoof(e.target);
        } else if (e.target.classList.contains("delete-btn")) {
            deleteField(e.target);
        }
    });

    // Botón añadir campo
    const addBtn = document.querySelector(".add-field-btn");
    if (addBtn) {
        addBtn.addEventListener("click", addField);
    }
});

// --- 1. Fecha y hora en tiempo real ---
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

// --- 2. Toggle de techos ---
function toggleRoof(button) {
    const row = button.closest(".field-row");
    const status = row.querySelector(".field-status");
    const currentState = row.dataset.state;

    if (!row || !status) return;

    // Bloquear si está en movimiento
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

    // Simulación de 3 segundos de movimiento
    setTimeout(() => {
        status.className = `field-status status-${finalState}`;
        status.textContent = textFinal;
        row.dataset.state = finalState;
        
        button.textContent = nextButtonText;
        button.disabled = false;
        button.classList.remove("disabled");

        // Aquí podrías hacer fetch para actualizar BD
        console.log(`Campo actualizado: ${finalState}`);
    }, 3000);
}

// --- 3. Añadir campo rápido ---
function addField() {
    const dashboard = document.querySelector(".dashboard");
    const addButton = document.querySelector(".add-field-btn");
    if (!dashboard || !addButton) return;

    const count = dashboard.querySelectorAll(".field-row").length + 1;

    const row = document.createElement("div");
    row.className = "field-row";
    row.dataset.state = "open";

    row.innerHTML = `
        <div class="field-info">
            <h3>Campo ${count}</h3>
            <span>Ubicación por definir</span>
        </div>
        <div class="field-status status-open">Abierto</div>
        <div class="field-buttons" style="display: flex; gap: 10px;">
            <button class="action-btn">Cierre manual</button>
            <button class="action-btn delete-btn" style="background-color: #ff4d4d; color: white;">Eliminar</button>
        </div>
    `;

    dashboard.insertBefore(row, addButton);
}

// --- 4. Eliminar campo ---
function deleteField(button) {
    const row = button.closest(".field-row");
    if (!row) return;

    if (!confirm("¿Estás seguro de que deseas eliminar este campo?")) return;

    row.style.opacity = "0";
    row.style.transform = "translateX(20px)";
    row.style.transition = "all 0.3s ease";

    setTimeout(() => {
        row.remove();
    }, 300);
}
