import { getHourlyWeather } from '/static/js/weather.js';

const container = document.getElementById("weather-container");

function windDirection(deg) {
    const directions = ["N", "NE", "E", "SE", "S", "SO", "O", "NO"];
    return directions[Math.round(deg / 45) % 8];
}

function formatDateTitle(dateString, index) {
    const date = new Date(dateString);

    if (index === 0) return "Hoy - " + date.toLocaleDateString("es-ES");
    if (index === 1) return "Mañana - " + date.toLocaleDateString("es-ES");

    return date.toLocaleDateString("es-ES", {
        weekday: "long",
        day: "numeric",
        month: "long"
    });
}

async function loadWeather() {

    if (!navigator.geolocation) {
        container.innerHTML = "<div class='error'>La geolocalización no está soportada.</div>";
        return;
    }

    navigator.geolocation.getCurrentPosition(async (position) => {

        const lat = position.coords.latitude;
        const lon = position.coords.longitude;

        container.innerHTML = "Cargando datos meteorológicos...";

        try {

            const grouped = await getHourlyWeather(lat, lon);
            container.innerHTML = "";

            const dates = Object.keys(grouped).slice(0, 5);

            dates.forEach((date, index) => {

                const dayBlock = document.createElement("div");
                dayBlock.className = "day-block";

                const title = document.createElement("h2");
                title.textContent = formatDateTitle(date, index);
                dayBlock.appendChild(title);

                const hourGrid = document.createElement("div");
                hourGrid.className = "hour-grid";

                grouped[date].forEach(hour => {

                    const hourCard = document.createElement("div");
                    hourCard.className = "hour-card";

                    hourCard.innerHTML = `
                        <strong>${hour.time}</strong>
                        🌡️ ${hour.temp} ºC<br>
                        🌧️ ${hour.rain} mm<br>
                        ☔ ${hour.prob_rain}% lluvia<br>
                        🧊 ${hour.hail}% granizo<br>
                        💨 ${hour.wind_speed} km/h (${windDirection(hour.wind_dir)})
                    `;

                    hourGrid.appendChild(hourCard);
                });

                dayBlock.appendChild(hourGrid);
                container.appendChild(dayBlock);
            });

        } catch (error) {
            container.innerHTML = "<div class='error'>Error cargando datos meteorológicos</div>";
        }

    }, () => {
        container.innerHTML = "<div class='error'>No se pudo obtener la ubicación.</div>";
    });
}

loadWeather();