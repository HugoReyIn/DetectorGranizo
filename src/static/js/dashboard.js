document.addEventListener("DOMContentLoaded", () => {
    console.log("[Dashboard] DOM cargado");
    updateDateTime();
    setInterval(updateDateTime, 1000);
    loadWeather();
    setInterval(loadWeather, 5 * 60 * 1000);

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
    if (addBtn) addBtn.addEventListener("click", () => window.location.href = "/field/new");
});

function updateDateTime() {
    const timeEl = document.getElementById("current-time");
    const dateEl = document.getElementById("current-date");
    if (!timeEl || !dateEl) return;

    const now = new Date();
    timeEl.textContent = now.toLocaleTimeString("es-ES", { hour: "2-digit", minute: "2-digit", hour12: false });
    const date = now.toLocaleDateString("es-ES", { weekday: "long", day: "numeric", month: "long", year: "numeric" });
    dateEl.textContent = date.charAt(0).toUpperCase() + date.slice(1);
}

async function loadWeather() {
    const weatherEl = document.getElementById("weather-info");
    if (!weatherEl) {
        console.log("[Weather] Elemento #weather-info no encontrado");
        return;
    }

    weatherEl.textContent = "Obteniendo ubicación...";
    console.log("[Weather] Iniciando geolocalización...");

    if (!navigator.geolocation) {
        console.error("[Weather] Geolocalización no soportada por el navegador");
        weatherEl.textContent = "Geolocalización no soportada por el navegador.";
        return;
    }

    navigator.geolocation.getCurrentPosition(
        async (position) => {
            console.log("[Weather] Ubicación obtenida", position.coords);
            const lat = parseFloat(position.coords.latitude.toFixed(6));
            const lon = parseFloat(position.coords.longitude.toFixed(6));
            console.log(`[Weather] Lat: ${lat}, Lon: ${lon}`);

            try {
                weatherEl.textContent = "Cargando clima...";
                console.log("[Weather] Consultando municipio...");
                const muniRes = await fetch(`/get-municipio?lat=${lat}&lon=${lon}`);
                const muniData = await muniRes.json();
                console.log("[Weather] Municipio recibido:", muniData);
                const municipio = muniData.municipio ?? "Desconocido";

                console.log("[Weather] Consultando clima...");
                const weatherRes = await fetch(`/get-weather?lat=${lat}&lon=${lon}`);
                const data = await weatherRes.json();
                console.log("[Weather] Datos clima recibidos:", data);

                if (data.error) { 
                    console.error("[Weather] Error del servidor:", data.error);
                    weatherEl.textContent = "Error al obtener datos del clima."; 
                    return; 
                }

                const sunrise = data.sunrise ? new Date(data.sunrise + 'Z').toLocaleTimeString("es-ES", { hour: "2-digit", minute: "2-digit" }) : "N/A";
                const sunset = data.sunset ? new Date(data.sunset + 'Z').toLocaleTimeString("es-ES", { hour: "2-digit", minute: "2-digit" }) : "N/A";

                weatherEl.innerHTML = `
                    📍 <strong>${municipio}</strong><br><br>
                    🌡️ <strong>Temp:</strong> ${data.temp_min ?? "N/A"}°C - ${data.temp_max ?? "N/A"}°C
                    (Sensación: ${data.feels_like ?? "N/A"}°C)<br>
                    💧 <strong>Humedad:</strong> ${data.humidity ?? "N/A"}%<br>
                    🌬️ <strong>Viento:</strong> ${data.wind_speed ?? "N/A"} km/h (${data.wind_deg ?? "N/A"}°)<br>
                    🌧️ <strong>Lluvia:</strong> ${data.rain ?? 0} mm<br>
                    ❄️ <strong>Nieve:</strong> ${data.snow ?? 0} mm<br>
                    🧊 <strong>Granizo:</strong> ${data.hail ?? 0} mm<br>
                    ☀️ <strong>Amanecer:</strong> ${sunrise} | 🌙 <strong>Atardecer:</strong> ${sunset}
                `;
                console.log("[Weather] Clima actualizado en DOM");
            } catch (error) {
                console.error("[Weather] Error cargando clima:", error);
                weatherEl.textContent = "Error al cargar el clima.";
            }
        },
        (error) => {
            console.error("[Weather] Error geolocalización:", error);
            switch(error.code) {
                case error.PERMISSION_DENIED:
                    weatherEl.textContent = "Permite la geolocalización para ver el clima.";
                    break;
                case error.POSITION_UNAVAILABLE:
                    weatherEl.textContent = "Ubicación no disponible.";
                    break;
                case error.TIMEOUT:
                    weatherEl.textContent = "Tiempo de espera agotado al obtener ubicación.";
                    break;
                default:
                    weatherEl.textContent = "Error desconocido al obtener ubicación.";
            }
        },
        { enableHighAccuracy: true, timeout: 15000, maximumAge: 0 }
    );
}

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
