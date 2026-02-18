document.addEventListener("DOMContentLoaded", () => {
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
    if (addBtn) {
        addBtn.addEventListener("click", () => {
            window.location.href = "/field/new";
        });
    }
});


// ===============================
// RELOJ
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
// WEATHER
// ===============================
async function loadWeather() {

    if (!navigator.geolocation) {
        return;
    }

    navigator.geolocation.getCurrentPosition(
        async (position) => {

            const lat = position.coords.latitude;
            const lon = position.coords.longitude;

            try {

                // Municipio
                const muniRes = await fetch(`/get-municipio?lat=${lat}&lon=${lon}`);
                const muniData = await muniRes.json();
                const municipio = muniData.municipio ?? "Desconocido";

                // Clima
                const weatherRes = await fetch(`/get-weather?lat=${lat}&lon=${lon}`);
                const data = await weatherRes.json();

                if (data.error) return;

                // Datos
                const tempActual = data.temp_actual ?? "--";
                const tempMin = data.temp_min ?? "--";
                const tempMax = data.temp_max ?? "--";
                const lluvia = data.rain ?? 0;
                const nieve = data.snow ?? 0;
                const granizo = data.hail ?? 0;
                const humedad = data.humidity ?? 0;
                const viento = data.wind_speed ?? 0;
                const dirViento = data.wind_deg ?? 0;
                const puntoRocio = data.dew_point ?? 0;

                const sunrise = data.sunrise ? new Date(data.sunrise + "Z") : null;
                const sunset = data.sunset ? new Date(data.sunset + "Z") : null;

                const sunriseDate = sunrise
                    ? sunrise.toLocaleTimeString("es-ES", { hour: "2-digit", minute: "2-digit", hour12: false })
                    : "--:--";

                const sunsetDate = sunset
                    ? sunset.toLocaleTimeString("es-ES", { hour: "2-digit", minute: "2-digit", hour12: false })
                    : "--:--";

                // Progreso solar
                let sunPercent = 0;
                if (sunrise && sunset) {
                    const now = new Date();
                    const total = sunset - sunrise;
                    sunPercent = Math.min(Math.max((now - sunrise) / total * 100, 0), 100);
                }

                // ==========
                // ACTUALIZAR DOM
                // ==========
                document.getElementById("weather-icon").src =
                    `/static/icons/weather/${data.weathercode}.png`;

                document.getElementById("municipio").textContent = municipio;

                document.getElementById("temp-actual").textContent = tempActual;
                document.getElementById("temp-max").textContent = tempMax;
                document.getElementById("temp-min").textContent = tempMin;

                document.getElementById("rain").textContent = lluvia;
                document.getElementById("hail").textContent = granizo;
                document.getElementById("snow").textContent = nieve;

                document.getElementById("humidity").textContent = humedad;
                document.getElementById("wind").textContent = `${viento} (${dirViento}°)`;
                document.getElementById("dew").textContent = puntoRocio;

                document.getElementById("sunrise").textContent = sunriseDate;
                document.getElementById("sunset").textContent = sunsetDate;
                document.getElementById("sun-progress").style.width = `${sunPercent}%`;

            } catch (error) {
                console.error("Error cargando clima:", error);
            }
        },
        () => {},
        { enableHighAccuracy: true, timeout: 15000, maximumAge: 0 }
    );
}


// ===============================
// ESTADO TECHO
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
            alert("Error al actualizar estado.");
            button.disabled = false;
            button.classList.remove("disabled");
        }
    }, 3000);
}
