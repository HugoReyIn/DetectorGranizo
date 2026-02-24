import { loadWeatherByCoords } from "./weather.js";

document.addEventListener("DOMContentLoaded", () => {
    // -----------------------
    // RELOJ Y FECHA
    // -----------------------
    updateDateTime();
    setInterval(updateDateTime, 1000);

    // -----------------------
    // WEATHER (NUEVO SISTEMA)
    // -----------------------
    if (navigator.geolocation) {
        navigator.geolocation.getCurrentPosition(
            (position) => {
                loadWeatherByCoords(
                    position.coords.latitude,
                    position.coords.longitude
                );
            },
            () => {},
            { enableHighAccuracy: true, timeout: 15000, maximumAge: 0 }
        );

        setInterval(() => {
            navigator.geolocation.getCurrentPosition(
                (position) => {
                    loadWeatherByCoords(
                        position.coords.latitude,
                        position.coords.longitude
                    );
                }
            );
        }, 60 * 60 * 1000);
    }

    // -----------------------
    // DASHBOARD CLICK
    // -----------------------
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

// ===============================
// RELOJ (SE MANTIENE IGUAL)
// ===============================
function updateDateTime() {
    const timeEl = document.getElementById("current-time");
    const dateEl = document.getElementById("current-date");
    if (!timeEl || !dateEl) return;

    const now = new Date();

    timeEl.textContent = now.toLocaleTimeString("es-ES", {
        hour: "2-digit",
        minute: "2-digit",
        hour12: false
    });

    const date = now.toLocaleDateString("es-ES", {
        weekday: "long",
        day: "numeric",
        month: "long",
        year: "numeric"
    });

    dateEl.textContent = date.charAt(0).toUpperCase() + date.slice(1);
}

// ===============================
// ESTADO TECHO (SE MANTIENE IGUAL)
// ===============================
function toggleRoof(row, button, fieldId) {
    const status = row.querySelector(".field-status");
    let currentState = row.dataset.state;
    if (currentState === "opening" || currentState === "closing") return;

    button.disabled = true;
    button.classList.add("disabled");

    let finalState, textDuring, textFinal, nextButtonText;

    if (currentState === "open") {
        currentState = "closing";
        finalState = "closed";
        textDuring = "Cerrando...";
        textFinal = "Cerrado";
        nextButtonText = "Apertura manual";
    } else {
        currentState = "opening";
        finalState = "open";
        textDuring = "Abriendo...";
        textFinal = "Abierto";
        nextButtonText = "Cierre manual";
    }

    status.className = `field-status status-${currentState}`;
    status.textContent = textDuring;
    row.dataset.state = currentState;

    setTimeout(async () => {
        try {
            await fetch(`/field/update-status/${fieldId}`, {
                method: "POST",
                headers: {"Content-Type":"application/json"},
                body: JSON.stringify({state: finalState})
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

    const weatherContainer = document.getElementById("weather-container");
    if (!weatherContainer) return;

    weatherContainer.addEventListener("click", (e) => {
        // Evitamos que se clique en un enlace interno
        if (e.target.tagName === "A") return;

        // Tomamos el primer campo
        const firstField = document.querySelector(".field-row");
        if (!firstField) return;

        const fieldId = firstField.dataset.id;
        if (!fieldId) return;

        window.location.href = `/weather/${fieldId}`;
    });
}