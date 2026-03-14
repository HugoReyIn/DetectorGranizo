"""
NominatimFacade.py
Remote Facade — encapsula las llamadas HTTP a Nominatim (OpenStreetMap).
Incluye caché de 24h y rate-limit de 1 req/s para respetar el ToS.
"""

import time
import threading
from datetime import datetime
import requests
from config import NOMINATIM_BASE_URL, NOMINATIM_TIMEOUT, NOMINATIM_USER_AGENT


class NominatimFacade:

    BASE_URL = NOMINATIM_BASE_URL
    HEADERS  = {"User-Agent": NOMINATIM_USER_AGENT}
    TIMEOUT  = NOMINATIM_TIMEOUT

    _TTL     = 86400   # 24 h — la provincia no cambia
    _MIN_GAP = 1.1     # segundos mínimos entre peticiones reales

    def __init__(self):
        self._cache: dict         = {}   # key → {ts, data}
        self._lock:  threading.Lock = threading.Lock()
        self._last_request: float = 0.0

    # ──────────────────────────────────────────────
    # PÚBLICA PRINCIPAL
    # ──────────────────────────────────────────────
    def reverse_geocode(self, lat: float, lon: float) -> dict:
        """Devuelve el JSON completo de Nominatim para unas coordenadas."""
        key = f"{round(lat, 3)}_{round(lon, 3)}"

        with self._lock:
            cached = self._cache.get(key)
            if cached and (datetime.now() - cached["ts"]).total_seconds() < self._TTL:
                return cached["data"]

            # Rate-limit: esperar si la última petición fue hace menos de 1.1 s
            elapsed = time.monotonic() - self._last_request
            if elapsed < self._MIN_GAP:
                time.sleep(self._MIN_GAP - elapsed)

            params   = {"lat": lat, "lon": lon, "format": "json", "accept-language": "es"}
            response = requests.get(
                self.BASE_URL, headers=self.HEADERS, params=params, timeout=self.TIMEOUT
            )
            response.raise_for_status()
            data = response.json()

            self._last_request = time.monotonic()
            self._cache[key]   = {"ts": datetime.now(), "data": data}
            return data

    # ──────────────────────────────────────────────
    # HELPERS
    # ──────────────────────────────────────────────
    def get_municipality(self, lat: float, lon: float) -> str:
        address = self.reverse_geocode(lat, lon).get("address", {})
        return (
            address.get("municipality")
            or address.get("city")
            or address.get("town")
            or address.get("village")
            or address.get("hamlet")
            or address.get("suburb")
            or address.get("county")
            or address.get("state_district")
            or "Desconocido"
        )

    def get_province(self, lat: float, lon: float) -> str:
        """Devuelve todos los campos geográficos útiles normalizados."""
        address = self.reverse_geocode(lat, lon).get("address", {})
        fields  = [
            address.get("province",     ""),
            address.get("state",        ""),
            address.get("county",       ""),
            address.get("city",         ""),
            address.get("town",         ""),
            address.get("municipality", ""),
        ]
        def _norm(s: str) -> str:
            return (s.lower()
                    .replace("á","a").replace("é","e").replace("í","i")
                    .replace("ó","o").replace("ú","u").replace("ñ","n"))
        return " ".join(_norm(f) for f in fields if f)