import requests
from config import AEMET_BASE_URL, AEMET_TIMEOUT


class AemetFacade:

    BASE_URL = AEMET_BASE_URL
    TIMEOUT  = AEMET_TIMEOUT

    def __init__(self, api_key: str):
        self._headers = {"api_key": api_key, "Accept": "application/json"}

    @staticmethod
    def _get_area(lat: float, lon: float) -> str:
        """Devuelve el código de área AEMET según coordenadas."""
        if 27.0 <= lat <= 29.5 and -18.5 <= lon <= -13.0:
            return "62"  # Canarias
        return "61"      # Península + Baleares

    def fetch_alerts_raw(self, lat: float, lon: float) -> tuple[str, str]:
        area    = self._get_area(lat, lon)
        api_url = self.BASE_URL.format(area=area)

        r1 = requests.get(api_url, headers=self._headers, timeout=self.TIMEOUT)
        r1.raise_for_status()
        meta     = r1.json()
        data_url = meta.get("datos")
        if not data_url:
            raise ValueError("AEMET no devolvió URL de datos")

        r2 = requests.get(data_url, headers=self._headers, timeout=self.TIMEOUT)
        r2.raise_for_status()

        content_type = r2.headers.get("Content-Type", "")
        return content_type, r2.text