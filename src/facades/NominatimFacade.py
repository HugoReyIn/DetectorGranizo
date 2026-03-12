"""
NominatimFacade.py
Remote Facade — encapsula las llamadas HTTP a la API de Nominatim (OpenStreetMap).
"""

import requests
from config import NOMINATIM_BASE_URL, NOMINATIM_TIMEOUT, NOMINATIM_USER_AGENT


class NominatimFacade:

    BASE_URL = NOMINATIM_BASE_URL
    HEADERS  = {"User-Agent": NOMINATIM_USER_AGENT}
    TIMEOUT  = NOMINATIM_TIMEOUT

    def reverse_geocode(self, lat: float, lon: float) -> dict:
        """Devuelve el JSON completo de Nominatim para unas coordenadas."""
        params = {"lat": lat, "lon": lon, "format": "json"}
        response = requests.get(self.BASE_URL, headers=self.HEADERS, params=params, timeout=self.TIMEOUT)
        response.raise_for_status()
        return response.json()

    def get_municipality(self, lat: float, lon: float) -> str:
        """Devuelve el nombre del municipio más cercano a las coordenadas."""
        data    = self.reverse_geocode(lat, lon)
        address = data.get("address", {})
        return (
            address.get("municipality")
            or address.get("city")
            or address.get("town")
            or address.get("village")
            or "Desconocido"
        )

    def get_province(self, lat: float, lon: float) -> str:
        """Devuelve el nombre de la provincia normalizado (sin tildes, en minúsculas)."""
        data     = self.reverse_geocode(lat, lon)
        address  = data.get("address", {})
        province = (address.get("province") or address.get("state") or "").lower()
        return (
            province
            .replace("á", "a").replace("é", "e")
            .replace("í", "i").replace("ó", "o").replace("ú", "u")
        )