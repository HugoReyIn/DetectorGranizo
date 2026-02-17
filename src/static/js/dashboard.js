document.addEventListener("DOMContentLoaded", () => {
    updateDateTime();
    setInterval(updateDateTime, 1000);

    loadWeather();
    setInterval(loadWeather, 5 * 60 * 1000); // Cada 5 minutos

    const dashboard = document.querySelector(".dashboard");

    dashboard.addEventListener("click", (e) => {
        const row = e.target.closest(".field-row");
        if (!row) return;

        const fieldId = row.dataset.id;

        // BOTÓN CIERRE / APERTURA
        if (e.target.classList.contains("action-btn")) {
            e.stopPropagation();
            toggleRoof(row, e.target, fieldId);
            return;
        }

        // CLICK EN FILA → EDITAR
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


// ============================
// RELOJ Y FECHA
// ============================
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


// ============================
// CLIMA (Open-Meteo)
// ============================
function loadWeather() {
    const weatherEl = document.getElementById("weather-info");
    if (!weatherEl) return;

    if (!navigator.geolocation) {
        weatherEl.textContent = "Geolocalización no soportada.";
        return;
    }

    navigator.geolocation.getCurrentPosition(
        async (pos) => {
            const lat = pos.coords.latitude;
            const lon = pos.coords.longitude;

            try {
                const res = await fetch(`/get-weather?lat=${lat}&lon=${lon}`);
                const data = await res.json();

                if (data.error) {
                    weatherEl.textContent = "Error al obtener datos.";
                    return;
                }

                const sunrise = data.sunrise
                    ? new Date(data.sunrise).toLocaleTimeString("es-ES", {hour: "2-digit", minute: "2-digit"})
                    : "N/A";

                const sunset = data.sunset
                    ? new Date(data.sunset).toLocaleTimeString("es-ES", {hour: "2-digit", minute: "2-digit"})
                    : "N/A";

                weatherEl.innerHTML = `
                    🌡️ <strong>Temp:</strong> ${data.temp_min ?? "N/A"}°C - ${data.temp_max ?? "N/A"}°C 
                    (Sensación: ${data.feels_like ?? "N/A"}°C)<br>

                    💧 <strong>Humedad:</strong> ${data.humidity ?? "N/A"}% 
                    | Punto de rocío: ${data.dew_point ?? "N/A"}°C<br>

                    🌬️ <strong>Viento:</strong> ${data.wind_speed ?? "N/A"} km/h 
                    (${data.wind_deg ?? "N/A"}°)<br>

                    ☀️ <strong>Amanecer:</strong> ${sunrise} 
                    | <strong>Atardecer:</strong> ${sunset}<br>

                    🌧️ <strong>Lluvia:</strong> ${data.rain ?? 0} mm<br>
                    ❄️ <strong>Nieve:</strong> ${data.snow ?? 0} mm<br>
                    🧊 <strong>Granizo:</strong> ${data.hail ?? 0} mm<br>
                `;

            } catch (error) {
                console.error("Error clima:", error);
                weatherEl.textContent = "Error al cargar el clima.";
            }
        },
        () => {
            weatherEl.textContent = "No se pudo obtener la ubicación.";
        }
    );
}


// ============================
// TOGGLE TECHO
// ============================
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
            alert("Error al actualizar estado en servidor.");
            button.disabled = false;
            button.classList.remove("disabled");
        }
    }, 3000);
}
