import requests
from app.config import AEMET_API_KEY, AEMET_BASE_URL


class AemetService:

    @staticmethod
    def _get_headers():
        return {
            "api_key": AEMET_API_KEY
        }

    @staticmethod
    def get_prediccion_diaria(municipio_id: str) -> dict:
        url = f"{AEMET_BASE_URL}/prediccion/especifica/municipio/diaria/{municipio_id}"
        response = requests.get(url, headers=AemetService._get_headers())
        response.raise_for_status()

        datos = response.json()

        # Segunda llamada obligatoria AEMET
        datos_url = datos["datos"]
        resultado = requests.get(datos_url)
        resultado.raise_for_status()

        return resultado.json()

    @staticmethod
    def hay_lluvia(prediccion: dict) -> bool:
        try:
            dias = prediccion[0]["prediccion"]["dia"]
            for dia in dias:
                if dia.get("probPrecipitacion"):
                    for tramo in dia["probPrecipitacion"]:
                        if int(tramo["value"]) > 40:
                            return True
            return False
        except Exception:
            return False
