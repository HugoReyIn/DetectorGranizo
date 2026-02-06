/**
 * Lógica del Dashboard - Detector de Granizo
 */

document.addEventListener("DOMContentLoaded", () => {
    // Inicializar el reloj al cargar la página
    updateDateTime();
    setInterval(updateDateTime, 1000);
});

// --- 1. Fecha y hora en tiempo real ---
function updateDateTime() {
    const timeEl = document.getElementById('current-time');
    const dateEl = document.getElementById('current-date');
    
    if (!timeEl || !dateEl) return;

    const now = new Date();
    
    // Formato: 14:30
    const time = now.toLocaleTimeString('es-ES', { 
        hour: '2-digit', 
        minute: '2-digit',
        hour12: false 
    });
    
    // Formato: Viernes, 6 de febrero de 2026
    const date = now.toLocaleDateString('es-ES', { 
        weekday: 'long', 
        day: 'numeric', 
        month: 'long', 
        year: 'numeric' 
    });
    
    timeEl.textContent = time;
    dateEl.textContent = date.charAt(0).toUpperCase() + date.slice(1);
}

// --- 2. Control de Techos (Toggle) ---
function toggleRoof(button) {
    const row = button.closest(".field-row");
    const status = row.querySelector(".field-status");
    const currentState = row.dataset.state;

    // Bloquear si ya está en proceso de movimiento
    if (currentState === "opening" || currentState === "closing") return;

    // Desactivar botón durante la animación
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

    // Fase 1: En movimiento
    status.className = `field-status status-${action}`;
    status.textContent = textDuring;
    row.dataset.state = action;

    // Fase 2: Estado final tras simulación de 3 segundos
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

// --- 3. Añadir nuevo campo (Quick Add) ---
/**
 * Esta función añade una fila rápida al dashboard. 
 * Todos los campos nuevos nacen con estado "open".
 */
function addField() {
    const dashboard = document.querySelector(".dashboard");
    const addButton = document.querySelector(".add-field-btn");
    const count = document.querySelectorAll(".field-row").length + 1;
    
    const row = document.createElement("div");
    row.className = "field-row";
    row.dataset.state = "open"; // Estado inicial: Abierto
    
    row.innerHTML = `
        <div class="field-info">
            <h3>Campo ${count}</h3>
            <span>Ubicación por definir</span>
        </div>
        <div class="field-status status-open">Abierto</div>
        <div class="field-buttons" style="display: flex; gap: 10px;">
            <button class="action-btn" onclick="toggleRoof(this)">Cierre manual</button>
            <button class="action-btn delete-btn" onclick="deleteField(this)" style="background-color: #ff4d4d; color: white;">Eliminar</button>
        </div>
    `;
    
    // Insertar antes del botón de "Añadir campo"
    dashboard.insertBefore(row, addButton);
}

// --- 4. Eliminar campo ---
function deleteField(button) {
    if (confirm("¿Estás seguro de que deseas eliminar este campo?")) {
        const row = button.closest(".field-row");
        row.style.opacity = "0";
        row.style.transform = "translateX(20px)";
        row.style.transition = "all 0.3s ease";
        
        setTimeout(() => {
            row.remove();
        }, 300);
    }
}