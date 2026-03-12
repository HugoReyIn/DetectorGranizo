"""
AemetFacade.py
Remote Facade — encapsula las llamadas HTTP a la API de AEMET OpenData.
Separa la obtención de datos de su interpretación (que vive en WeatherService).
"""

import requests
from config import AEMET_API_URL, AEMET_TIMEOUT


class AemetFacade:

    API_URL = AEMET_API_URL
    TIMEOUT = AEMET_TIMEOUT

    def __init__(self, api_key: str):
        self._headers = {"api_key": api_key, "Accept": "application/json"}

    def fetch_alerts_raw(self) -> tuple[str, str]:
        """
        Obtiene el contenido bruto de alertas CAP de AEMET.

        Returns:
            (content_type, body_text) — el content-type y el cuerpo de la respuesta
            de datos, para que el servicio decida cómo parsearlo.

        Raises:
            requests.HTTPError si cualquiera de las dos peticiones falla.
        """
        # Paso 1: metadata → URL de datos real
        r1 = requests.get(self.API_URL, headers=self._headers, timeout=10)
        r1.raise_for_status()
        meta     = r1.json()
        data_url = meta.get("datos")
        if not data_url:
            raise ValueError("AEMET no devolvió URL de datos")

        # Paso 2: datos reales (XML o JSON según AEMET)
        r2 = requests.get(data_url, headers=self._headers, timeout=self.TIMEOUT)
        r2.raise_for_status()

        content_type = r2.headers.get("Content-Type", "")
        return content_type, r2.text