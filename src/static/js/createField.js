const map = L.map('map').setView([42.465, -2.445], 16);

// Satélite (ESRI)
L.tileLayer(
  'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
  { maxZoom: 19 }
).addTo(map);

let points = [];
let markers = [];
let polygon = null;

map.on('click', function (e) {
    addPoint(e.latlng);
});

function addPoint(latlng) {
    points.push([latlng.lat, latlng.lng]);

    const marker = L.circleMarker(latlng, {
        radius: 6,
        color: '#000',
        fillColor: '#fff',
        fillOpacity: 1
    }).addTo(map);

    markers.push(marker);
    drawPolygon();
    updateInfo();
}

function drawPolygon() {
    if (polygon) {
        map.removeLayer(polygon);
    }

    if (points.length >= 2) {
        polygon = L.polygon(points, {
            color: 'green',
            fillOpacity: 0.3
        }).addTo(map);
    }
}

function updateInfo() {
    document.getElementById("points-count").textContent = points.length;

    if (points.length >= 3) {
        const area = calculateArea(points);
        document.getElementById("area").textContent = area.toFixed(2);
    } else {
        document.getElementById("area").textContent = 0;
    }
}

/**
 * Calcula el área en m² usando fórmula geodésica
 */
function calculateArea(coords) {
    const earthRadius = 6378137;
    let area = 0;

    for (let i = 0; i < coords.length; i++) {
        const [lat1, lon1] = coords[i];
        const [lat2, lon2] = coords[(i + 1) % coords.length];

        area += toRad(lon2 - lon1) *
            (2 + Math.sin(toRad(lat1)) + Math.sin(toRad(lat2)));
    }

    area = area * earthRadius * earthRadius / 2;
    return Math.abs(area);
}

function toRad(value) {
    return value * Math.PI / 180;
}

document.getElementById("field-form").addEventListener("submit", function (e) {
    e.preventDefault();

    if (points.length < 3) {
        alert("Debes marcar al menos 3 puntos");
        return;
    }

    // Aquí luego enviaremos los datos al backend
    console.log("Nombre:", fieldName.value);
    console.log("Dirección:", fieldLocation.value);
    console.log("Puntos:", points);
});
