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
    const weatherDefault = document.getElementById("weather-actual-info");
    if (!weatherDefault) return;

    weatherDefault.textContent = "Obteniendo ubicación...";

    if (!navigator.geolocation) {
        weatherDefault.textContent = "Geolocalización no soportada.";
        return;
    }

    navigator.geolocation.getCurrentPosition(
        async (position) => {
            const lat = position.coords.latitude;
            const lon = position.coords.longitude;

            try {
                weatherDefault.textContent = "Cargando clima...";

                // Municipio
                const muniRes = await fetch(`/get-municipio?lat=${lat}&lon=${lon}`);
                const muniData = await muniRes.json();
                const municipio = muniData.municipio ?? "Desconocido";

                // Clima
                const weatherRes = await fetch(`/get-weather?lat=${lat}&lon=${lon}`);
                const data = await weatherRes.json();

                if (data.error) {
                    weatherDefault.textContent = "Error al obtener datos del clima.";
                    return;
                }

                // Datos esenciales
                const tempActual = data.temp_actual ?? "N/A";
                const tempMin = data.temp_min ?? "N/A";
                const tempMax = data.temp_max ?? "N/A";
                const lluvia = data.rain ?? 0;
                const nieve = data.snow ?? 0;
                const granizo = data.hail ?? 0;
                const humedad = data.humidity ?? 0;
                const viento = data.wind_speed ?? 0;
                const dirViento = data.wind_deg ?? 0;
                const puntoRocio = data.dew_point ?? 0;
                const sunrise = data.sunrise ? new Date(data.sunrise + 'Z') : null;
                const sunset = data.sunset ? new Date(data.sunset + 'Z') : null;

                // Barra amanecer/atardecer
                const now = new Date();
                let sunPercent = 0;
                if (sunrise && sunset) {
                    const total = sunset - sunrise;
                    sunPercent = Math.min(Math.max((now - sunrise) / total * 100, 0), 100);
                }

                const weatherHTML = `
                    <div class="weather-mockup">
                        <div class="weather-left">
                            <div class="weather-code">
                                <img src="/static/icons/weather/${data.weathercode}.png" alt="Estado">
                            </div>
                            <div class="weather-municipio">${municipio}</div>
                        </div>

                        <div class="weather-center">
                            <div class="temp-actual">${tempActual}°C</div>
                            <div class="temp-minmax">
                                <span class="temp-max">${tempMax}°C</span>
                                <span class="temp-min">${tempMin}°C</span>
                            </div>
                        </div>

                        <div class="weather-right">
                            <div>Lluvia: ${lluvia}mm</div>
                            <div>Granizo: ${granizo}%</div>
                            <div>Nieve: ${nieve}mm</div>
                            <div>Humedad: ${humedad}%</div>
                            <div>Viento: ${viento} km/h (${dirViento}°)</div>
                            <div>Punto Rocío: ${puntoRocio}°C</div>
                        </div>

                        <div class="weather-sun">
                            <span>Amanecer</span>
                            <div class="sun-bar">
                                <div class="sun-progress" style="width:${sunPercent}%"></div>
                            </div>
                            <span>Atardecer</span>
                        </div>
                    </div>
                `;

                weatherDefault.innerHTML = weatherHTML;

            } catch (error) {
                console.error("Error cargando clima:", error);
                weatherDefault.textContent = "Error al cargar el clima.";
            }

        },
        (error) => {
            weatherDefault.textContent = "Error obteniendo ubicación";
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
