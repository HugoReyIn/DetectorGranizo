// ================= ESTADO =================
let map;
let points = [];
let markers = [];
let polygon = null;
let geocodeTimeout = null;

// ================= INICIAR MAPA =================
if (navigator.geolocation) {
    navigator.geolocation.getCurrentPosition(
        pos => initMap(pos.coords.latitude, pos.coords.longitude),
        () => initMap(43.2630, -2.9350) // fallback Bilbao
    );
} else {
    initMap(43.2630, -2.9350);
}

function initMap(lat, lng) {
    map = L.map("map").setView([lat, lng], 16);

    // Satélite
    L.tileLayer(
        "https://services.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
        { maxZoom: 19 }
    ).addTo(map);

    // Etiquetas (municipios)
    L.tileLayer(
        "https://services.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}",
        { maxZoom: 19 }
    ).addTo(map);

    // Añadir puntos al hacer click
    map.on("click", e => {
        const idx = getSegmentIndex(e.latlng);
        if (idx !== null) addPointAt(e.latlng, idx + 1);
        else addPoint(e.latlng);
    });
}

// ================= ICONO DE PUNTO =================
const whiteIcon = L.divIcon({
    className: "",
    html: `<div style="
        width:10px;
        height:10px;
        background:white;
        border:2px solid black;
        border-radius:50%;
    "></div>`,
    iconSize: [14, 14],
    iconAnchor: [7, 7]
});

// ================= PUNTOS =================
function addPoint(latlng) {
    addPointAt(latlng, points.length);
}

function addPointAt(latlng, index) {
    points.splice(index, 0, [latlng.lat, latlng.lng]);

    const marker = L.marker(latlng, { draggable: true, icon: whiteIcon }).addTo(map);
    markers.splice(index, 0, marker);

    marker.on("drag", () => {
        const i = markers.indexOf(marker);
        points[i] = [marker.getLatLng().lat, marker.getLatLng().lng];
        redraw();
    });

    marker.on("contextmenu", () => {
        const i = markers.indexOf(marker);
        map.removeLayer(marker);
        markers.splice(i, 1);
        points.splice(i, 1);
        redraw();
    });

    redraw();
}

// ================= REDIBUJAR =================
function redraw() {
    if (polygon) map.removeLayer(polygon);

    if (points.length >= 2) {
        polygon = L.polygon(points, {
            color: "white",
            fillColor: "white",
            fillOpacity: 0.3,
            weight: 2
        }).addTo(map);
    }

    updateInfo();

    if (points.length >= 3) {
        debounceMunicipio();
    } else {
        // Si hay menos de 3 puntos, resetear municipio a "–"
        document.getElementById("field-location").value = "";
        document.getElementById("municipio").textContent = "–";
    }
}

// ================= INFO =================
function updateInfo() {
    document.getElementById("points-count").textContent = points.length;

    if (points.length >= 3) {
        document.getElementById("area").textContent = calculateArea(points).toFixed(2);
    } else {
        document.getElementById("area").textContent = 0;
    }
}

// ================= CLICK EN LINEA =================
function getSegmentIndex(latlng) {
    if (points.length < 2) return null;
    const p = map.latLngToLayerPoint(latlng);
    const tol = 8;

    for (let i = 0; i < points.length; i++) {
        const a = map.latLngToLayerPoint(points[i]);
        const b = map.latLngToLayerPoint(points[(i + 1) % points.length]);
        if (distanceToSegment(p, a, b) < tol) return i;
    }
    return null;
}

function distanceToSegment(p, a, b) {
    const l2 = a.distanceTo(b) ** 2;
    if (l2 === 0) return p.distanceTo(a);
    let t = ((p.x - a.x) * (b.x - a.x) + (p.y - a.y) * (b.y - a.y)) / l2;
    t = Math.max(0, Math.min(1, t));
    return p.distanceTo(L.point(a.x + t * (b.x - a.x), a.y + t * (b.y - a.y)));
}

// ================= AREA =================
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
const toRad = v => v * Math.PI / 180;

// ================= CENTROIDE =================
function getPolygonCentroid(pts) {
    let x = 0, y = 0, z = 0;
    pts.forEach(p => {
        const lat = p[0] * Math.PI / 180;
        const lon = p[1] * Math.PI / 180;
        x += Math.cos(lat) * Math.cos(lon);
        y += Math.cos(lat) * Math.sin(lon);
        z += Math.sin(lat);
    });
    const total = pts.length;
    x /= total; y /= total; z /= total;
    const lon = Math.atan2(y, x);
    const hyp = Math.sqrt(x * x + y * y);
    const lat = Math.atan2(z, hyp);
    return [lat * 180 / Math.PI, lon * 180 / Math.PI];
}

// ================= MUNICIPIO (BACKEND) =================
function debounceMunicipio() {
    clearTimeout(geocodeTimeout);
    if (points.length >= 3) {
        geocodeTimeout = setTimeout(obtenerMunicipio, 800);
    }
}

async function obtenerMunicipio() {
    if (points.length < 3) return;

    const [lat, lng] = getPolygonCentroid(points);
    if (isNaN(lat) || isNaN(lng)) return;

    try {
        const res = await fetch(`/get-municipio?lat=${lat}&lon=${lng}`);
        const data = await res.json();
        const municipio = data.municipio || "Desconocido";

        document.getElementById("field-location").value = municipio;
        document.getElementById("municipio").textContent = municipio;
    } catch (err) {
        console.error("Error cargando municipios:", err);
        document.getElementById("municipio").textContent = "Error";
    }
}

// ================= SUBMIT =================
document.getElementById("field-form").addEventListener("submit", e => {
    e.preventDefault();

    if (points.length < 3) {
        alert("Debes marcar al menos 3 puntos");
        return;
    }

    const fieldName = document.getElementById("field-name").value;
    const fieldLocation = document.getElementById("field-location").value;

    console.log("Nombre:", fieldName);
    console.log("Municipio:", fieldLocation);
    console.log("Puntos:", points);

    // Aquí enviarías los datos al backend con fetch POST
});

// ================= UNDO (Ctrl+Z) =================
document.addEventListener("keydown", (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key === "z") {
        e.preventDefault();
        removeLastPoint();
    }
});

function removeLastPoint() {
    if (points.length === 0) return;

    const lastMarker = markers.pop();
    map.removeLayer(lastMarker);

    points.pop();

    redraw();
}
