document.addEventListener("DOMContentLoaded", () => {
    const fieldIdInput = document.getElementById("field-id-hidden");
    const isEditing = fieldIdInput && fieldIdInput.value !== "";
    const fieldId = isEditing ? fieldIdInput.value : null;

    const pointsInput = document.getElementById("field-points-hidden");
    let points = JSON.parse(pointsInput.value || "[]");
    let markers = [];
    let polygon = null;
    let map;

    const fieldMunicipioInput = document.getElementById("field-municipality-hidden");
    let fieldMunicipio = fieldMunicipioInput.value || "–";

    let municipioTimeout = null; // Para debounce

    // ========================== MAPA ==========================
    function initMap(lat, lng) {
        map = L.map("map").setView([lat, lng], 16);

        L.tileLayer("https://services.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}", { maxZoom: 19 }).addTo(map);
        L.tileLayer("https://services.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}", { maxZoom: 19 }).addTo(map);

        const whiteIcon = L.divIcon({
            className: "",
            html: `<div style="width:10px;height:10px;background:white;border:2px solid black;border-radius:50%;"></div>`,
            iconSize: [14, 14],
            iconAnchor: [7, 7]
        });

        // Cargar marcadores existentes
        points.forEach(p => {
            const marker = L.marker([p.lat, p.lng], { draggable: true, icon: whiteIcon }).addTo(map);
            markers.push(marker);
            addMarkerEvents(marker);
        });

        redraw();

        // Añadir puntos con click
        map.on("click", e => {
            points.push({ lat: e.latlng.lat, lng: e.latlng.lng });
            const marker = L.marker(e.latlng, { draggable: true, icon: whiteIcon }).addTo(map);
            markers.push(marker);
            addMarkerEvents(marker);
            redraw();
        });
    }

    function addMarkerEvents(marker) {
        marker.on("drag", () => {
            const i = markers.indexOf(marker);
            points[i] = { lat: marker.getLatLng().lat, lng: marker.getLatLng().lng };
            redraw();
        });

        marker.on("contextmenu", () => {
            const i = markers.indexOf(marker);
            map.removeLayer(marker);
            markers.splice(i, 1);
            points.splice(i, 1);
            redraw();
        });
    }

    function redraw() {
        if (polygon) map.removeLayer(polygon);
        if (points.length >= 2) {
            polygon = L.polygon(points.map(p => [p.lat, p.lng]), { color: "white", fillColor: "white", fillOpacity: 0.3, weight: 2 }).addTo(map);
        }

        updateInfo();
        pointsInput.value = JSON.stringify(points);

        updateMunicipioDebounced(); // Actualizar municipio al mover o agregar puntos
    }

    function updateInfo() {
        const areaEl = document.getElementById("area");
        if (points.length >= 3) {
            const area = calculateArea(points.map(p => [p.lat, p.lng]));
            areaEl.textContent = area.toLocaleString('es-ES', { minimumFractionDigits: 1, maximumFractionDigits: 1 });
            document.getElementById("field-area-hidden").value = area;
        } else {
            areaEl.textContent = "0,0";
            document.getElementById("field-area-hidden").value = 0;
        }
        document.getElementById("field-municipality-hidden").value = fieldMunicipio;
    }

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

    function getPolygonCentroid(points) {
        let lat = 0, lng = 0;
        points.forEach(p => { lat += p.lat; lng += p.lng; });
        return { lat: lat / points.length, lng: lng / points.length };
    }

    function updateMunicipioDebounced() {
        clearTimeout(municipioTimeout);
        if (points.length >= 3) {
            municipioTimeout = setTimeout(updateMunicipio, 500);
        } else {
            fieldMunicipio = "–";
            document.getElementById("field-municipality-hidden").value = fieldMunicipio;
            const locEl = document.getElementById("field-location");
            if (locEl) locEl.textContent = fieldMunicipio;
        }
    }

    async function updateMunicipio() {
        const centroid = getPolygonCentroid(points);
        try {
            const res = await fetch(`/get-municipio?lat=${centroid.lat}&lon=${centroid.lng}`);
            const data = await res.json();
            fieldMunicipio = data.municipio || "Desconocido";
            document.getElementById("field-municipality-hidden").value = fieldMunicipio;
            const locEl = document.getElementById("field-location");
            if (locEl) locEl.textContent = fieldMunicipio;
        } catch (err) {
            console.error("Error al obtener municipio:", err);
            fieldMunicipio = "Error";
            document.getElementById("field-municipality-hidden").value = fieldMunicipio;
            const locEl = document.getElementById("field-location");
            if (locEl) locEl.textContent = fieldMunicipio;
        }
    }

    // ========================== INICIALIZAR MAPA ==========================
    if (points.length > 0) initMap(points[0].lat, points[0].lng);
    else if (navigator.geolocation) {
        navigator.geolocation.getCurrentPosition(
            pos => initMap(pos.coords.latitude, pos.coords.longitude),
            () => initMap(43.2630, -2.9350)
        );
    } else {
        initMap(43.2630, -2.9350);
    }

    // ========================== ENVIAR FORMULARIO ==========================
    document.getElementById("field-form").addEventListener("submit", async e => {
        e.preventDefault();
        if (points.length < 3) return alert("Debes marcar al menos 3 puntos");

        await updateMunicipio(); // asegurar que el municipio esté actualizado

        const formData = new FormData(e.target);
        formData.set("municipality", fieldMunicipio);
        formData.set("points", JSON.stringify(points));

        const endpoint = isEditing ? `/field/edit/${fieldId}` : "/field/new";
        fetch(endpoint, { method: "POST", body: formData })
            .then(res => {
                if (res.redirected) window.location.href = res.url;
                else alert("Error al guardar el campo");
            })
            .catch(() => alert("Error de conexión con el servidor."));
    });
});
