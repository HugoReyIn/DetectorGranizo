// weatherChart.js
import { loadWeatherByCoords, getHourlyWeather, updateGeneralWeatherDOM } from "./weather.js";


function getWindDirectionLabel(degrees) {
    if (degrees === undefined || degrees === null) return "";
    const adjusted = (degrees + 180) % 360;
    const directions = ["N", "NE", "E", "SE", "S", "SO", "O", "NO"];
    return directions[Math.round(adjusted / 45) % 8];
}

document.addEventListener("DOMContentLoaded", async () => {
    let lat, lon;

    if (window.fieldCoords) {
        lat = window.fieldCoords.lat;
        lon = window.fieldCoords.lon;
    } else if (navigator.geolocation) {
        await new Promise(resolve => {
            navigator.geolocation.getCurrentPosition(pos => {
                lat = pos.coords.latitude;
                lon = pos.coords.longitude;
                resolve();
            });
        });
    }

    // Obtener datos
    const data = await loadWeatherByCoords(lat, lon);

    // Actualizar campos generales en el DOM
    updateGeneralWeatherDOM(data);

    // Obtener datos horarios y dibujar gráficas
    const hourlyData = await getHourlyWeather(lat, lon);
    renderAllCharts(hourlyData);
});

function renderAllCharts(grouped) {
    const days = Object.keys(grouped);
    days.forEach((day, index) => {
        const dayIndex = index + 1;
        const canvas = document.getElementById(`chart-${dayIndex}`);
        if (canvas) drawChart(canvas, grouped[day]);
    });
}

function drawChart(canvas, hourlyData) {
    const ctx = canvas.getContext("2d");
    ctx.clearRect(0,0,canvas.width,canvas.height);
    const padding = 75;
    const width = canvas.width - padding*2;
    const height = canvas.height - padding*2;

    // Temperatura
    const temps = hourlyData.map(h => h.temp);
    const maxTemp = Math.max(...temps);
    const minTemp = 0;
    const tempRange = maxTemp - minTemp || 1;
    const tempPoints = hourlyData.map((h,i) => {
        const x = padding + (i/(hourlyData.length-1))*width;
        const y = padding + height - ((h.temp - minTemp)/tempRange)*height;
        return {x,y,value:h.temp,time:h.time};
    });

    // Área temperatura
    ctx.beginPath();
    ctx.moveTo(tempPoints[0].x, canvas.height-padding);
    tempPoints.forEach(p=>ctx.lineTo(p.x,p.y));
    ctx.lineTo(tempPoints[tempPoints.length-1].x, canvas.height-padding);
    ctx.closePath();
    ctx.fillStyle="rgba(240,200,100,0.35)";
    ctx.fill();

    // Línea temperatura
    ctx.beginPath();
    ctx.moveTo(tempPoints[0].x,tempPoints[0].y);
    for(let i=1;i<tempPoints.length;i++) ctx.lineTo(tempPoints[i].x,tempPoints[i].y);
    ctx.strokeStyle="#e0a800";
    ctx.lineWidth=3;
    ctx.stroke();

    // Puntos temperatura
    tempPoints.forEach(p=>{
        ctx.beginPath();
        ctx.arc(p.x,p.y,5,0,2*Math.PI);
        ctx.fillStyle="#e0a800";
        ctx.fill();
    });

    // Texto temperatura
    ctx.fillStyle="#333";
    ctx.font="bold 14px Arial";
    ctx.textAlign="center";
    tempPoints.forEach(p=>ctx.fillText(p.value+"°",p.x,p.y-15));

    // Probabilidad de lluvia
    const rainPoints = hourlyData.map((h,i)=>{
        const x = padding + (i/(hourlyData.length-1))*width;
        const y = padding + height - (h.prob_rain/100)*height;
        return {x,y,value:h.prob_rain};
    });

    ctx.beginPath();
    ctx.moveTo(rainPoints[0].x,rainPoints[0].y);
    for(let i=1;i<rainPoints.length;i++) ctx.lineTo(rainPoints[i].x,rainPoints[i].y);
    ctx.strokeStyle="#2196f3";
    ctx.lineWidth=2;
    ctx.stroke();

    rainPoints.forEach(p=>{
        ctx.beginPath();
        ctx.arc(p.x,p.y,4,0,2*Math.PI);
        ctx.fillStyle="#2196f3";
        ctx.fill();
    });

    // Eje X
    ctx.beginPath();
    ctx.moveTo(padding,canvas.height-padding);
    ctx.lineTo(canvas.width-padding,canvas.height-padding);
    ctx.strokeStyle="#aaa";
    ctx.lineWidth=1;
    ctx.stroke();

    // Datos debajo
    const baseY = canvas.height - padding + 25;
    const leftColumnX = padding - 45;

    // Horas
    ctx.fillStyle="#666";
    ctx.font="12px Arial";
    ctx.textAlign="center";
    tempPoints.forEach(p=>ctx.fillText(p.time,p.x,baseY));

    // Unidades izquierda
    ctx.textAlign="right";
    ctx.font="bold 12px Arial";
    ctx.fillStyle="#2196f3";
    ctx.fillText("mm", leftColumnX-5, baseY+22);
    ctx.fillStyle="#444";
    ctx.fillText("km/h", leftColumnX-5, baseY+40);

    // Lluvia
    ctx.fillStyle="#2196f3";
    hourlyData.forEach((h,i)=>ctx.fillText(h.rain,tempPoints[i].x,baseY+22));

    // Viento
    ctx.fillStyle="#444";
    hourlyData.forEach((h,i)=>{
        const windLabel = getWindDirectionLabel(h.wind_dir);
        ctx.fillText(h.wind_speed + " (" + windLabel + ")", tempPoints[i].x, baseY+40);
    });
}