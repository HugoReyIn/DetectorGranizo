// ---------------- ESTADO ----------------
let points = [];
let markers = [];
let polygon = null;
let municipiosGeoJSON = null;

// ---------------- ICONO PUNTO BLANCO ----------------
const whitePointIcon = L.divIcon({
    className: '',
    html: `<div style="
        width: 10px;
        height: 10px;
        background: white;
        border: 2px solid black;
        border-radius: 50%;
    "></div>`,
    iconSize: [14, 14],
    iconAnchor: [7, 7]
});

// ---------------- CARGAR MUNICIPIOS (TOPOJSON) ----------------
fetch("/static/json/municipalities.json")  // <-- tu nuevo archivo
  .then(res => res.json())
  .then(topoData => {
      municipiosGeoJSON = topojson.feature(topoData, topoData.objects.municipalities);
      console.log("Municipios cargados:", municipiosGeoJSON.features.length);
  })
  .catch(err => console.error("Error cargando municipios:", err));

// ---------------- MAPA ----------------
let map;

if (navigator.geolocation) {
    navigator.geolocation.getCurrentPosition(
        (pos) => initMap(pos.coords.latitude, pos.coords.longitude),
        () => initMap(43.2630, -2.9350) // fallback Bilbao
    );
} else {
    initMap(43.2630, -2.9350);
}

function initMap(lat, lng) {
    map = L.map('map').setView([lat, lng], 16);

    // Satélite + etiquetas
    const esriSat = L.tileLayer(
        "https://services.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
        { maxZoom: 19 }
    );
    const esriLabels = L.tileLayer(
        "https://services.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}",
        { maxZoom: 19, pane: 'overlayPane' }
    );

    esriSat.addTo(map);
    esriLabels.addTo(map);

    map.on('click', function (e) {
        const index = getSegmentIndex(e.latlng);
        if (index !== null) {
            addPointAt(e.latlng, index + 1);
        } else {
            addPoint(e.latlng);
        }
        asignarMunicipio();
    });
}

// ---------------- FUNCIONES DE PUNTOS ----------------
function addPoint(latlng) {
    addPointAt(latlng, points.length);
}

function addPointAt(latlng, index) {
    points.splice(index, 0, [latlng.lat, latlng.lng]);

    const marker = L.marker(latlng, {
        draggable: true,
        icon: whitePointIcon
    }).addTo(map);

    markers.splice(index, 0, marker);
    attachMarkerEvents(marker);
    redrawAll();
    asignarMunicipio();
}

function attachMarkerEvents(marker) {
    marker.on('drag', () => {
        const i = markers.indexOf(marker);
        points[i] = [marker.getLatLng().lat, marker.getLatLng().lng];
        drawPolygon();
        updateInfo();
        asignarMunicipio();
    });

    marker.on('contextmenu', () => {
        const i = markers.indexOf(marker);
        map.removeLayer(marker);
        markers.splice(i, 1);
        points.splice(i, 1);
        redrawAll();
        asignarMunicipio();
    });
}

function redrawAll() {
    drawPolygon();
    updateInfo();
}

// ---------------- POLÍGONO ----------------
function drawPolygon() {
    if (polygon) {
        map.removeLayer(polygon);
        polygon = null;
    }

    if (points.length >= 2) {
        polygon = L.polygon(points, {
            color: 'white',
            fillOpacity: 0.3,
            weight: 2
        }).addTo(map);
    }
}

// ---------------- INFO ----------------
function updateInfo() {
    document.getElementById("points-count").textContent = points.length;

    if (points.length >= 3) {
        const area = calculateArea(points);
        document.getElementById("area").textContent = area.toFixed(2);
    } else {
        document.getElementById("area").textContent = 0;
    }
}

// ---------------- DETECTAR CLICK EN LÍNEA ----------------
function getSegmentIndex(latlng) {
    if (points.length < 2) return null;

    const clickPoint = map.latLngToLayerPoint(latlng);
    const tolerance = 8;

    for (let i = 0; i < points.length; i++) {
        const p1 = map.latLngToLayerPoint(L.latLng(points[i]));
        const p2 = map.latLngToLayerPoint(L.latLng(points[(i + 1) % points.length]));
        if (distanceToSegment(clickPoint, p1, p2) < tolerance) return i;
    }
    return null;
}

function distanceToSegment(p, v, w) {
    const l2 = v.distanceTo(w) ** 2;
    if (l2 === 0) return p.distanceTo(v);

    let t = ((p.x - v.x) * (w.x - v.x) + (p.y - v.y) * (w.y - v.y)) / l2;
    t = Math.max(0, Math.min(1, t));

    return p.distanceTo(L.point(v.x + t * (w.x - v.x), v.y + t * (w.y - v.y)));
}

// ---------------- ÁREA ----------------
function calculateArea(coords) {
    const R = 6378137;
    let area = 0;

    for (let i = 0; i < coords.length; i++) {
        const [lat1, lon1] = coords[i];
        const [lat2, lon2] = coords[(i + 1) % coords.length];
        area += toRad(lon2 - lon1) * (2 + Math.sin(toRad(lat1)) + Math.sin(toRad(lat2)));
    }

    return Math.abs(area * R * R / 2);
}

function toRad(v) { return v * Math.PI / 180; }

// ---------------- ASIGNAR MUNICIPIO ----------------
function asignarMunicipio() {
    if (!municipiosGeoJSON || points.length < 3) {
        document.getElementById("municipio").textContent = "–";
        return null;
    }

    const fieldPolygon = turf.polygon([[...points, points[0]]]);
    let mayorArea = 0;
    let municipioSeleccionado = null;

    municipiosGeoJSON.features.forEach(mun => {
        if (!mun.geometry) return;
        const intersection = turf.intersect(fieldPolygon, mun.geometry);
        if (intersection) {
            const area = turf.area(intersection);
            if (area > mayorArea) {
                mayorArea = area;
                municipioSeleccionado = mun.properties.name;
            }
        }
    });

    if (municipioSeleccionado) {
        document.getElementById("field-location").value = municipioSeleccionado;
        document.getElementById("municipio").textContent = municipioSeleccionado;
    } else {
        document.getElementById("municipio").textContent = "–";
    }

    return municipioSeleccionado;
}

// ---------------- DESHACER CTRL+Z ----------------
document.addEventListener("keydown", function (e) {
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "z") {
        undoLastPoint();
    }
});

function undoLastPoint() {
    if (points.length === 0) return;

    const lastMarker = markers.pop();
    map.removeLayer(lastMarker);
    points.pop();

    redrawAll();
    asignarMunicipio();
}

// ---------------- SUBMIT ----------------
document.getElementById("field-form").addEventListener("submit", (e) => {
    e.preventDefault();

    if (points.length < 3) {
        alert("Debes marcar al menos 3 puntos");
        return;
    }

    console.log("Nombre:", document.getElementById("field-name").value);
    console.log("Municipio:", document.getElementById("field-location").value);
    console.log("Puntos:", points);
});
