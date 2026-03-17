import { loadWeatherByCoords, getHailPrediction, getMaxHailNext6h } from "./weather.js";

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

    let municipioTimeout = null;
    let weatherTimeout = null;

    // ===============================
    // MAPA
    // ===============================

    // Umbral en píxeles para detectar click sobre una línea
    const LINE_HIT_PX = 12;

    const whiteIcon = L.divIcon({
        className: "",
        html: `<div style="width:10px;height:10px;background:white;border:2px solid black;border-radius:50%;cursor:grab;"></div>`,
        iconSize: [14, 14],
        iconAnchor: [7, 7]
    });

    function initMap(lat, lng) {
        map = L.map("map").setView([lat, lng], 16);

        L.tileLayer("https://services.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}", { maxZoom: 19 }).addTo(map);
        L.tileLayer("https://services.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}", { maxZoom: 19 }).addTo(map);

        points.forEach(p => {
            const marker = L.marker([p.lat, p.lng], { draggable: true, icon: whiteIcon }).addTo(map);
            markers.push(marker);
            addMarkerEvents(marker);
        });

        redraw();

        map.on("click", e => {
            // Comprobar si el click está cerca de algún segmento (en píxeles de pantalla)
            const nearSegIdx = getNearestSegmentIndex(e);

            if (nearSegIdx !== -1) {
                // Insertar nuevo punto en ese segmento
                insertPointOnSegment(e.latlng, nearSegIdx);
            } else {
                // Añadir punto nuevo al final
                const marker = L.marker(e.latlng, { draggable: true, icon: whiteIcon }).addTo(map);
                markers.push(marker);
                points.push({ lat: e.latlng.lat, lng: e.latlng.lng });
                addMarkerEvents(marker);
                redraw();
            }
        });
    }

    /**
     * Devuelve el índice del segmento más cercano al click si está dentro
     * del umbral LINE_HIT_PX en coordenadas de pantalla, o -1 si no hay ninguno.
     * Solo activo cuando hay al menos 2 puntos.
     */
    function getNearestSegmentIndex(e) {
        if (points.length < 2) return -1;

        const clickPx = map.latLngToContainerPoint(e.latlng);
        let bestIdx  = -1;
        let bestDist = LINE_HIT_PX;

        const n = points.length;
        for (let i = 0; i < n; i++) {
            // Solo iterar segmentos cerrados si hay al menos 3 puntos
            if (i === n - 1 && n < 3) continue;

            const aPx = map.latLngToContainerPoint(L.latLng(points[i].lat, points[i].lng));
            const bPx = map.latLngToContainerPoint(L.latLng(points[(i + 1) % n].lat, points[(i + 1) % n].lng));

            const dist = distToSegmentPx(clickPx, aPx, bPx);
            if (dist < bestDist) {
                bestDist = dist;
                bestIdx  = i;
            }
        }

        return bestIdx;
    }

    /** Distancia en píxeles de un punto p al segmento a-b */
    function distToSegmentPx(p, a, b) {
        const dx = b.x - a.x;
        const dy = b.y - a.y;
        const lenSq = dx * dx + dy * dy;
        if (lenSq === 0) return Math.hypot(p.x - a.x, p.y - a.y);
        let t = ((p.x - a.x) * dx + (p.y - a.y) * dy) / lenSq;
        t = Math.max(0, Math.min(1, t));
        return Math.hypot(p.x - (a.x + t * dx), p.y - (a.y + t * dy));
    }

    /** Inserta un punto nuevo después del segmento segIdx */
    function insertPointOnSegment(latlng, segIdx) {
        const newPoint = { lat: latlng.lat, lng: latlng.lng };
        const marker   = L.marker(latlng, { draggable: true, icon: whiteIcon }).addTo(map);

        points.splice(segIdx + 1, 0, newPoint);
        markers.splice(segIdx + 1, 0, marker);
        addMarkerEvents(marker);
        redraw();
    }

    function addMarkerEvents(marker) {
        marker.on("drag", () => {
            const i = markers.indexOf(marker);
            if (i === -1) return;
            points[i] = { lat: marker.getLatLng().lat, lng: marker.getLatLng().lng };
            redraw();
        });

        marker.on("contextmenu", (e) => {
            L.DomEvent.stopPropagation(e); // evitar que suba al mapa
            const i = markers.indexOf(marker);
            if (i === -1) return;
            map.removeLayer(marker);
            markers.splice(i, 1);
            points.splice(i, 1);
            redraw();
        });
    }

    function redraw() {

        if (polygon) map.removeLayer(polygon);

        if (points.length >= 2) {
            polygon = L.polygon(points.map(p => [p.lat, p.lng]), {
                color: "white",
                fillColor: "white",
                fillOpacity: 0.3,
                weight: 2
            }).addTo(map);
        }

        updateInfo();
        pointsInput.value = JSON.stringify(points);
        updateMunicipioDebounced();
        updateWeatherDebounced();
    }

    // ===============================
    // ÁREA
    // ===============================

    function calculateArea(coords) {
        const R = 6378137;
        let area = 0;
        for (let i = 0; i < coords.length; i++) {
            const [lat1, lon1] = coords[i];
            const [lat2, lon2] = coords[(i + 1) % coords.length];
            area += (lon2 - lon1) * Math.PI / 180 *
                (2 + Math.sin(lat1 * Math.PI / 180) + Math.sin(lat2 * Math.PI / 180));
        }
        return Math.abs(area * R * R / 2);
    }

    function updateInfo() {
        const areaEl = document.getElementById("area");

        if (points.length >= 3) {
            const area = calculateArea(points.map(p => [p.lat, p.lng]));
            areaEl.textContent = area.toLocaleString('es-ES', {
                minimumFractionDigits: 1,
                maximumFractionDigits: 1
            });
            document.getElementById("field-area-hidden").value = area;
        } else {
            areaEl.textContent = "0,0";
            document.getElementById("field-area-hidden").value = 0;
        }

        document.getElementById("field-municipality-hidden").value = fieldMunicipio;

        const locEl = document.getElementById("field-location");
        if (locEl) locEl.textContent = fieldMunicipio;
    }

    // ===============================
    // CENTROIDE
    // ===============================

    function getPolygonCentroid(points) {
        let lat = 0, lng = 0;
        points.forEach(p => { lat += p.lat; lng += p.lng; });
        return { lat: lat / points.length, lng: lng / points.length };
    }

    // ===============================
    // MUNICIPIO
    // ===============================

    function updateMunicipioDebounced() {
        clearTimeout(municipioTimeout);

        if (points.length >= 3) {
            municipioTimeout = setTimeout(updateMunicipio, 500);
        } else {
            fieldMunicipio = "–";
        }
    }

    async function updateMunicipio() {
        if (points.length < 3) return;

        const centroid = getPolygonCentroid(points);

        try {
            const res = await fetch(`/get-municipio?lat=${centroid.lat}&lon=${centroid.lng}`);
            const data = await res.json();
            fieldMunicipio = data.municipio || "Desconocido";
        } catch {
            fieldMunicipio = "Error";
        }

        document.getElementById("field-municipality-hidden").value = fieldMunicipio;
        const locEl = document.getElementById("field-location");
        if (locEl) locEl.textContent = fieldMunicipio;
    }

    // ===============================
    // WEATHER (NUEVO SISTEMA)
    // ===============================

    function updateWeatherDebounced() {
        clearTimeout(weatherTimeout);

        if (points.length >= 3) {
            weatherTimeout = setTimeout(loadWeatherFromField, 600);
        }
    }

    async function loadWeatherFromField() {
    if (points.length < 3) return;

    const centroid = getPolygonCentroid(points);

    // Clima actual (ya existente)
    loadWeatherByCoords(centroid.lat, centroid.lng);

    // Predicción de granizo por IA
    try {
        const prediction = await getHailPrediction(centroid.lat, centroid.lng);

        // Probabilidad máxima próximas 6h (de la IA)
        const maxHail6h = getMaxHailNext6h(prediction);
        const hailEl = document.getElementById("hail");
        if (hailEl) hailEl.textContent = `${maxHail6h.toFixed(0)} %`;

        // Guardar en window para uso externo
        window.hailPrediction = prediction;

        // ── CIERRE AUTOMÁTICO si riesgo >= 35% ──
        if (maxHail6h >= 35) {
            const fieldId = fieldIdInput?.value;
            if (fieldId) {
                console.warn(`[Granizo] Riesgo ${maxHail6h.toFixed(0)}% — cerrando techo automáticamente`);

                // Notificación visual
                const banner = document.createElement("div");
                banner.id = "hail-auto-close-banner";
                banner.innerHTML = `🧊 <strong>Riesgo de granizo ${maxHail6h.toFixed(0)}%</strong> — Techo cerrado automáticamente por la IA`;
                banner.style.cssText = "position:fixed;top:0;left:0;right:0;z-index:9999;background:#e53935;color:#fff;text-align:center;padding:12px 20px;font-size:14px;font-weight:600;box-shadow:0 2px 8px rgba(0,0,0,0.3);";
                if (!document.getElementById("hail-auto-close-banner")) {
                    document.body.prepend(banner);
                    setTimeout(() => banner.remove(), 10000);
                }

                // Llamar al endpoint de cierre
                const currentState = document.querySelector(".field-status")?.dataset?.state
                    || document.querySelector("[data-state]")?.dataset?.state;

                if (currentState !== "closed" && currentState !== "closing") {
                    await fetch(`/field/update-status/${fieldId}`, {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({ state: "closed" })
                    });

                    // Actualizar UI
                    const statusEl = document.querySelector(".field-status");
                    if (statusEl) {
                        statusEl.className = "field-status status-closed";
                        statusEl.textContent = "Cerrado";
                    }
                }
            }
        }

    } catch (e) {
        console.warn("Predicción granizo no disponible:", e);
    }
}

    // ===============================
    // CTRL + Z
    // ===============================

    document.addEventListener("keydown", (e) => {
        if ((e.ctrlKey || e.metaKey) && e.key === "z") {
            if (points.length === 0) return;
            const lastMarker = markers.pop();
            map.removeLayer(lastMarker);
            points.pop();
            redraw();
        }
    });

    // ===============================
    // INIT MAPA
    // ===============================

    if (points.length > 0) {
        initMap(points[0].lat, points[0].lng);
        if (points.length >= 3) loadWeatherFromField();
    } else if (navigator.geolocation) {
        navigator.geolocation.getCurrentPosition(
            pos => initMap(pos.coords.latitude, pos.coords.longitude),
            () => initMap(43.2630, -2.9350)
        );
    } else {
        initMap(43.2630, -2.9350);
    }

    // ===============================
    // GUARDAR
    // ===============================

    document.getElementById("field-form").addEventListener("submit", async e => {
        e.preventDefault();

        if (points.length < 3) return alert("Debes marcar al menos 3 puntos");

        await updateMunicipio();

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

    // ===============================
    // ELIMINAR
    // ===============================

    const deleteBtn = document.getElementById("delete-field-btn");

    if (deleteBtn && isEditing) {
        deleteBtn.addEventListener("click", () => {
            const fieldName = document.getElementById("field-name")?.value || "este campo";
            const overlay   = document.getElementById("delete-modal-overlay");
            const nameEl    = document.getElementById("delete-modal-fieldname");
            const cancelBtn = document.getElementById("delete-modal-cancel");
            const confirmBtn= document.getElementById("delete-modal-confirm");

            if (!overlay) {
                // Fallback por si el modal no está en el DOM
                if (!confirm("¿Seguro que quieres eliminar este campo?")) return;
                fetch(`/field/delete/${fieldId}`, { method: "POST" })
                    .then(res => { if (res.redirected) window.location.href = res.url; });
                return;
            }

            if (nameEl) nameEl.textContent = `"${fieldName}"`;
            overlay.style.display = "flex";

            const close = () => {
                overlay.style.display = "none";
                cancelBtn.removeEventListener("click", close);
                confirmBtn.removeEventListener("click", doDelete);
                overlay.removeEventListener("click", onOverlayClick);
            };

            const doDelete = () => {
                close();
                fetch(`/field/delete/${fieldId}`, { method: "POST" })
                    .then(res => {
                        if (res.redirected) window.location.href = res.url;
                        else alert("Error al eliminar el campo");
                    })
                    .catch(() => alert("Error de conexión con el servidor"));
            };

            const onOverlayClick = (e) => {
                if (e.target === overlay) close();
            };

            cancelBtn.addEventListener("click", close);
            confirmBtn.addEventListener("click", doDelete);
            overlay.addEventListener("click", onOverlayClick);
        });
    }


    function renderHailForecastChart(prediction) {
    const canvas = document.getElementById("hail-forecast-canvas");
    if (!canvas) return;

    const labels = prediction.map(p => p.time.split("T")[1].slice(0, 5));
    const values = prediction.map(p => p.hail_probability);

    if (window._hailChart) window._hailChart.destroy();

    window._hailChart = new Chart(canvas, {
        type: "bar",
        data: {
            labels,
            datasets: [{
                data: values,
                backgroundColor: values.map(v =>
                    v >= 70 ? "rgba(220,30,30,0.7)" :
                    v >= 40 ? "rgba(255,140,0,0.7)" :
                              "rgba(33,150,243,0.5)"
                ),
                borderRadius: 4,
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { display: false } },
            scales: {
                y: { min: 0, max: 100, ticks: { callback: v => v + "%" } },
                x: { ticks: { maxRotation: 45 } }
            }
        }
    });
}

});