document.addEventListener("DOMContentLoaded", () => {
    updateDateTime();
    setInterval(updateDateTime, 1000);

    loadWeather();
    setInterval(loadWeather, 60 * 60 * 1000);

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
// FUNCIONES AUXILIARES FECHAS
// ===============================

// Extrae solo HH:mm del ISO sin convertir zona horaria
function extractHour(isoString) {
    if (!isoString) return "--:--";
    return isoString.split("T")[1].slice(0, 5);
}

// Convierte ISO a Date en hora LOCAL real
function parseLocalDateTime(dateTimeStr) {
    if (!dateTimeStr) return null;

    const [date, time] = dateTimeStr.split("T");
    const [year, month, day] = date.split("-");
    const [hour, minute] = time.split(":");

    return new Date(year, month - 1, day, hour, minute);
}


function getWeatherDescription(code) {
    const weatherMap = {
        0: "Soleado",
        1: "Principalmente despejado",
        2: "Parcialmente nublado",
        3: "Nublado",

        45: "Niebla",
        48: "Niebla con escarcha",

        51: "Llovizna ligera",
        53: "Llovizna moderada",
        55: "Llovizna intensa",
        56: "Llovizna helada ligera",
        57: "Llovizna helada intensa",

        61: "Lluvia ligera",
        63: "Lluvia moderada",
        65: "Lluvia intensa",
        66: "Lluvia helada ligera",
        67: "Lluvia helada intensa",

        71: "Nevada ligera",
        73: "Nevada moderada",
        75: "Nevada intensa",
        77: "Granizo fino",

        80: "Chubascos ligeros",
        81: "Chubascos moderados",
        82: "Chubascos violentos",
        85: "Chubascos de nieve ligeros",
        86: "Chubascos de nieve intensos",

        95: "Tormenta",
        96: "Tormenta con granizo ligero",
        99: "Tormenta con granizo fuerte"
    };

    return weatherMap[code] || "Desconocido";
}

function getHailProbabilityFromCode(code) {
    switch (code) {
        case 77:
            return 50;
        case 96:
            return 70;
        case 99:
            return 100;
        default:
            return 0;
    }
}


// ===============================
// WEATHER
// ===============================
async function loadWeather() {

    if (!navigator.geolocation) return;

    navigator.geolocation.getCurrentPosition(
        async (position) => {

            const lat = position.coords.latitude;
            const lon = position.coords.longitude;

            try {
                // Municipio
                const muniRes = await fetch(`/get-municipio?lat=${lat}&lon=${lon}`);
                const muniData = await muniRes.json();
                const municipio = muniData.municipio ?? "Desconocido";

                // Clima (Open-Meteo)
                const weatherRes = await fetch(`/get-weather?lat=${lat}&lon=${lon}`);
                const data = await weatherRes.json();

                if (data.error) return;

                const tempActual = data.temp_actual ?? "--";
                const tempMin = data.temp_min ?? "--";
                const tempMax = data.temp_max ?? "--";
                const lluvia = data.rain ?? 0;
                const nieve = data.snow ?? 0;
                const humedad = data.humidity ?? 0;
                const viento = data.wind_speed ?? 0;
                const dirViento = data.wind_deg ?? 0;
                const puntoRocio = data.dew_point ?? 0;
                const soilMoisturePercent = (data.soil_moisture ?? 0) * 100;
                const weatherDescription = getWeatherDescription(data.weathercode);

                // ⬇️ CORRECCIÓN DEFINITIVA
                const sunriseDateStr = extractHour(data.sunrise);
                const sunsetDateStr = extractHour(data.sunset);

                const sunrise = parseLocalDateTime(data.sunrise);
                const sunset = parseLocalDateTime(data.sunset);

                // Progreso solar
                let sunPercent = 0;
                if (sunrise && sunset) {
                    const now = new Date();
                    const total = sunset - sunrise;
                    
                    function formatTime(date) {
                        return date.toLocaleTimeString("es-ES", {
                            hour: "2-digit",
                            minute: "2-digit",
                            hour12: false
                        });
                    }

                    const t25 = new Date(sunrise.getTime() + total * 0.25);
                    const t50 = new Date(sunrise.getTime() + total * 0.50);
                    const t75 = new Date(sunrise.getTime() + total * 0.75);

                    document.getElementById("sun-25").textContent = formatTime(t25);
                    document.getElementById("sun-50").textContent = formatTime(t50);
                    document.getElementById("sun-75").textContent = formatTime(t75);

                    sunPercent = Math.min(Math.max(((now - sunrise) / total) * 100, 0), 100);
                }

                // ========== ACTUALIZAR DOM ==========
                document.getElementById("weather-icon").src = `/static/icons/weather/${data.weathercode}.png`;
                document.getElementById("municipio").textContent = municipio;

                document.getElementById("temp-actual").textContent = `${tempActual} ºC`;
                document.getElementById("temp-max").textContent = `${tempMax} ºC`;
                document.getElementById("temp-min").textContent = `${tempMin} ºC`;

                const rainValue = Number(lluvia ?? 0).toFixed(1);
                const snowValue = Number(nieve ?? 0).toFixed(1);
                const hailPercent = getHailProbabilityFromCode(data.weathercode);
                
                document.getElementById("weather-description").textContent = weatherDescription;

                document.getElementById("rain").textContent = `${rainValue} mm`;
                document.getElementById("snow").textContent = `${snowValue} cm`;
                document.getElementById("hail").textContent = `${hailPercent} %`;  

                document.getElementById("humidity").textContent = `Humedad: ${humedad} %`;
                document.getElementById("wind").textContent = `${viento} km/h`;
                document.getElementById("dew").textContent = `Punto de rocio: ${puntoRocio} ºC`;
                document.getElementById("moisture").textContent = `Humedad de la tierra: ${soilMoisturePercent} %`;

                document.getElementById("sunrise").textContent = sunriseDateStr;
                document.getElementById("sunset").textContent = sunsetDateStr;

                const windIcon = document.getElementById("wind-icon");
                if (windIcon) {
                    windIcon.style.transform = `rotate(${dirViento + 180}deg)`;
                    windIcon.style.transition = "transform 0.5s ease";
                }

                const sunProgressEl = document.getElementById("sun-progress");
                const sunIndicatorEl = document.getElementById("sun-indicator");

                sunProgressEl.style.width = `${sunPercent}%`;

                const barWidth = sunProgressEl.parentElement.offsetWidth;
                sunIndicatorEl.style.left = `${(sunPercent / 100) * barWidth}px`;


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
