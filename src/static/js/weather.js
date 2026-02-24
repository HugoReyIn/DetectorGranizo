// =====================================================
// weather.js
// Sistema único de clima (Open-Meteo)
// Usado por dashboard.js y field.js
// =====================================================

let sunriseTime = null;
let sunsetTime = null;

// ===============================
// DESCRIPCIÓN CLIMA
// ===============================
function getWeatherDescription(code) {
    const weatherMap = {
        0: "Soleado", 1: "Principalmente despejado", 2: "Parcialmente nublado", 3: "Nublado",
        45: "Niebla", 48: "Niebla con escarcha",
        51: "Llovizna ligera", 53: "Llovizna moderada", 55: "Llovizna intensa",
        56: "Llovizna helada ligera", 57: "Llovizna helada intensa",
        61: "Lluvia ligera", 63: "Lluvia moderada", 65: "Lluvia intensa",
        66: "Lluvia helada ligera", 67: "Lluvia helada intensa",
        71: "Nevada ligera", 73: "Nevada moderada", 75: "Nevada intensa",
        77: "Granizo fino",
        80: "Chubascos ligeros", 81: "Chubascos moderados", 82: "Chubascos violentos",
        85: "Chubascos de nieve ligeros", 86: "Chubascos de nieve intensos",
        95: "Tormenta", 96: "Tormenta con granizo ligero", 99: "Tormenta con granizo fuerte"
    };
    return weatherMap[code] || "Desconocido";
}

function getHailProbabilityFromCode(code) {
    switch(code) {
        case 77: return 50;
        case 96: return 70;
        case 99: return 100;
        default: return 0;
    }
}

function extractHour(dateTimeStr) {
    return new Date(dateTimeStr).toLocaleTimeString("es-ES", {
        hour: "2-digit",
        minute: "2-digit",
        hour12: false
    });
}

function parseLocalDateTime(dateTimeStr) {
    return new Date(dateTimeStr);
}

// ===============================
// FORECAST
// ===============================
function renderForecast(daily) {
    for (let i = 1; i <= 4; i++) {
        const date = new Date(daily.time[i]);
        const dayName = date.toLocaleDateString("es-ES", { weekday: "long" });
        const formattedDay = dayName.charAt(0).toUpperCase() + dayName.slice(1);

        const weatherCode = daily.weathercode[i];
        const max = daily.temperature_2m_max[i];
        const min = daily.temperature_2m_min[i];

        document.getElementById(`day-${i}-name`).textContent = formattedDay;
        document.getElementById(`day-${i}-icon`).src = `/static/img/${weatherCode}.png`;
        document.getElementById(`day-${i}-max`).textContent = `${Math.round(max)} ºC`;
        document.getElementById(`day-${i}-min`).textContent = `${Math.round(min)} ºC`;
        document.getElementById(`day-${i}-sunrise`).textContent = extractHour(daily.sunrise[i]);
        document.getElementById(`day-${i}-sunset`).textContent = extractHour(daily.sunset[i]);
    }
}

// ===============================
// FUNCIÓN PRINCIPAL
// ===============================
export async function loadWeatherByCoords(lat, lon) {

    try {
        // Municipio
        const muniRes = await fetch(`/get-municipio?lat=${lat}&lon=${lon}`);
        const muniData = await muniRes.json();
        const municipio = muniData.municipio ?? "Desconocido";

        // Clima
        const weatherRes = await fetch(`/get-weather?lat=${lat}&lon=${lon}`);
        const data = await weatherRes.json();
        if (data.error) return;

        const hailPercent = getHailProbabilityFromCode(data.weathercode);
        const weatherDescription = getWeatherDescription(data.weathercode);
        const soilMoisturePercent = (data.soil_moisture ?? 0) * 100;

        // DOM
        document.getElementById("municipio").textContent = municipio;
        document.getElementById("weather-icon").src = `/static/img/${data.weathercode}.png`;
        document.getElementById("temp-actual").textContent = `${data.temp_actual} ºC`;
        document.getElementById("temp-max").textContent = `${data.temp_max} ºC`;
        document.getElementById("temp-min").textContent = `${data.temp_min} ºC`;
        document.getElementById("rain").textContent = `${data.rain} mm`;
        document.getElementById("snow").textContent = `${data.snow} cm`;
        document.getElementById("hail").textContent = `${hailPercent} %`;
        document.getElementById("humidity").textContent = `Humedad: ${data.humidity}%`;
        document.getElementById("wind").textContent = `${data.wind_speed} km/h`;
        document.getElementById("dew").textContent = `Punto de rocio: ${data.dew_point} ºC`;
        document.getElementById("moisture").textContent =`Humedad de la tierra: ${soilMoisturePercent.toFixed(1)}%`;
        document.getElementById("weather-description").textContent = weatherDescription;

        sunriseTime = parseLocalDateTime(data.sunrise);
        sunsetTime = parseLocalDateTime(data.sunset);

        document.getElementById("sunrise").textContent = extractHour(data.sunrise);
        document.getElementById("sunset").textContent = extractHour(data.sunset);

        updateSunProgress();
        if (data.daily) renderForecast(data.daily);

        const windIcon = document.getElementById("wind-icon");
        if (windIcon) {
            windIcon.style.transform = `rotate(${data.wind_deg + 180}deg)`;
            windIcon.style.transition = "transform 0.5s ease";
        }

    } catch (error) {
        console.error("Error cargando clima:", error);
    }
}

// ===============================
// BARRA SOLAR
// ===============================
function updateSunProgress() {
    if (!sunriseTime || !sunsetTime) return;

    const now = new Date();
    const total = sunsetTime - sunriseTime;
    const elapsed = now - sunriseTime;
    const percent = Math.min(Math.max((elapsed / total) * 100, 0), 100);

    const sunProgressEl = document.getElementById("sun-progress");
    const sunIndicatorEl = document.getElementById("sun-indicator");

    if (!sunProgressEl || !sunIndicatorEl) return;

    sunProgressEl.style.width = `${percent}%`;
    const barWidth = sunProgressEl.parentElement.offsetWidth;
    sunIndicatorEl.style.left = `${(percent / 100) * barWidth}px`;
}

setInterval(updateSunProgress, 1000);