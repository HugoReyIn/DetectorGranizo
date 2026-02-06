document.addEventListener("DOMContentLoaded", () => {
    let map;
    let points = [];
    let markers = [];
    let polygon = null;
    let geocodeTimeout = null;
    let fieldMunicipio = "–";

    // INICIAR MAPA
    if (navigator.geolocation) {
        navigator.geolocation.getCurrentPosition(
            pos => initMap(pos.coords.latitude, pos.coords.longitude),
            () => initMap(43.2630, -2.9350) 
        );
    } else {
        initMap(43.2630, -2.9350);
    }

    function initMap(lat, lng) {
        map = L.map("map").setView([lat, lng], 16);
        L.tileLayer("https://services.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}", { maxZoom: 19 }).addTo(map);
        L.tileLayer("https://services.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}", { maxZoom: 19 }).addTo(map);

        map.on("click", e => {
            const idx = getSegmentIndex(e.latlng);
            if (idx !== null) addPointAt(e.latlng, idx + 1);
            else addPoint(e.latlng);
        });
    }

    const whiteIcon = L.divIcon({
        className: "",
        html: `<div style="width:10px; height:10px; background:white; border:2px solid black; border-radius:50%;"></div>`,
        iconSize: [14, 14],
        iconAnchor: [7, 7]
    });

    function addPoint(latlng) { addPointAt(latlng, points.length); }

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

    function redraw() {
        if (polygon) map.removeLayer(polygon);
        if (points.length >= 2) {
            polygon = L.polygon(points, { color: "white", fillColor: "white", fillOpacity: 0.3, weight: 2 }).addTo(map);
        }
        updateInfo();
        if (points.length >= 3) debounceMunicipio();
        else {
            fieldMunicipio = "–";
            document.getElementById("field-location").textContent = "–";
        }
    }

    function updateInfo() {
        const areaEl = document.getElementById("area");
        if (points.length >= 3) {
            const area = calculateArea(points);
            areaEl.textContent = area.toLocaleString('es-ES', { minimumFractionDigits: 1, maximumFractionDigits: 1 });
        } else {
            areaEl.textContent = "0,0";
        }
    }

    // CÁLCULO DE ÁREA (Haversine/Spherical)
    function calculateArea(coords) {
        const R = 6378137;
        let area = 0;
        for (let i = 0; i < coords.length; i++) {
            const [lat1, lon1] = coords[i];
            const [lat2, lon2] = coords[(i + 1) % coords.length];
            area += (lon2 - lon1) * Math.PI / 180 * (2 + Math.sin(lat1 * Math.PI / 180) + Math.sin(lat2 * Math.PI / 180));
        }
        return Math.abs(area * R * R / 2);
    }

    function getPolygonCentroid(pts) {
        let lat = 0, lng = 0;
        pts.forEach(p => { lat += p[0]; lng += p[1]; });
        return [lat / pts.length, lng / pts.length];
    }

    function debounceMunicipio() {
        clearTimeout(geocodeTimeout);
        geocodeTimeout = setTimeout(obtenerMunicipio, 800);
    }

    async function obtenerMunicipio() {
        const [lat, lng] = getPolygonCentroid(points);
        try {
            const res = await fetch(`/get-municipio?lat=${lat}&lon=${lng}`);
            const data = await res.json();
            fieldMunicipio = data.municipio || "Desconocido";
            document.getElementById("field-location").textContent = fieldMunicipio;
        } catch (err) {
            document.getElementById("field-location").textContent = "Error";
        }
    }

    // SUBMIT CON ESTADO PREDETERMINADO
    document.getElementById("field-form").addEventListener("submit", e => {
        e.preventDefault();
        if (points.length < 3) return alert("Debes marcar al menos 3 puntos");

        const data = {
            name: document.getElementById("field-name").value,
            municipality: fieldMunicipio,
            area: document.getElementById("area").textContent,
            points: points,
            state: "open" // Todos nacen abiertos
        };
        console.log("Datos a guardar:", data);
        // Aquí harías tu fetch POST
    });

    // Auxiliares para click en línea
    function getSegmentIndex(latlng) {
        if (points.length < 2) return null;
        const p = map.latLngToLayerPoint(latlng);
        for (let i = 0; i < points.length; i++) {
            const a = map.latLngToLayerPoint(points[i]);
            const b = map.latLngToLayerPoint(points[(i + 1) % points.length]);
            if (distanceToSegment(p, a, b) < 8) return i;
        }
        return null;
    }

    function distanceToSegment(p, a, b) {
        const l2 = Math.pow(a.x - b.x, 2) + Math.pow(a.y - b.y, 2);
        if (l2 === 0) return p.distanceTo(a);
        let t = ((p.x - a.x) * (b.x - a.x) + (p.y - a.y) * (b.y - a.y)) / l2;
        t = Math.max(0, Math.min(1, t));
        return p.distanceTo(L.point(a.x + t * (b.x - a.x), a.y + t * (b.y - a.y)));
    }
});