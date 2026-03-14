"""
OpenMeteoFacade.py
Remote Facade — encapsula todas las llamadas HTTP a la API Open-Meteo.
Main.py y los servicios nunca llaman a Open-Meteo directamente.
"""

import requests
from datetime import datetime
from config import OPEN_METEO_ARCHIVE_URL, OPEN_METEO_BASE_URL, OPEN_METEO_TIMEOUT


class OpenMeteoFacade:

    BASE_URL    = OPEN_METEO_BASE_URL
    ARCHIVE_URL = OPEN_METEO_ARCHIVE_URL
    TIMEOUT     = OPEN_METEO_TIMEOUT

    # ──────────────────────────────────────────────
    # WEATHER ACTUAL + DAILY (usado en /get-weather)
    # ──────────────────────────────────────────────
    def get_current_weather(self, lat: float, lon: float) -> dict:
        url = (
            f"{self.BASE_URL}"
            f"?latitude={lat}&longitude={lon}"
            "&current=temperature_2m,weathercode,windspeed_10m,winddirection_10m"
            "&hourly=relativehumidity_2m,dewpoint_2m,precipitation,snowfall,"
            "precipitation_probability,soil_moisture_0_1cm"
            "&daily=sunrise,sunset,temperature_2m_max,temperature_2m_min,weathercode"
            "&forecast_days=5&models=icon_eu&timezone=auto"
        )
        response = requests.get(url, timeout=self.TIMEOUT)
        response.raise_for_status()
        return response.json()

    # ──────────────────────────────────────────────
    # HOURLY FORECAST (usado en /get-hourly-weather)
    # ──────────────────────────────────────────────
    def get_hourly_forecast(self, lat: float, lon: float) -> dict:
        url = (
            f"{self.BASE_URL}"
            f"?latitude={lat}&longitude={lon}"
            "&hourly=temperature_2m,precipitation,precipitation_probability,"
            "relativehumidity_2m,windspeed_10m,winddirection_10m,weathercode"
            "&forecast_days=5&timezone=auto"
        )
        response = requests.get(url, timeout=self.TIMEOUT)
        response.raise_for_status()
        return response.json()

    # ──────────────────────────────────────────────
    # AGRONOMIC DATA (usado en /get-agronomic-data)
    # ──────────────────────────────────────────────
    def get_agronomic_data(self, lat: float, lon: float) -> dict:
        url = (
            f"{self.BASE_URL}"
            f"?latitude={lat}&longitude={lon}"
            "&hourly=et0_fao_evapotranspiration,uv_index,surface_pressure,"
            "soil_moisture_0_1cm,soil_moisture_1_3cm,soil_moisture_3_9cm,"
            "soil_temperature_0cm,soil_temperature_6cm,soil_temperature_18cm,"
            "temperature_2m,windspeed_10m,shortwave_radiation,vapour_pressure_deficit"
            "&daily=et0_fao_evapotranspiration,uv_index_max,precipitation_sum,"
            "rain_sum,sunrise,sunset,temperature_2m_max,temperature_2m_min"
            "&forecast_days=5&timezone=auto"
        )
        response = requests.get(url, timeout=self.TIMEOUT)
        response.raise_for_status()
        return response.json()

    # ──────────────────────────────────────────────
    # FIELD SUMMARY (usado en /get-field-summary)
    # ──────────────────────────────────────────────
    def get_field_summary(self, lat: float, lon: float) -> dict:
        url = (
            f"{self.BASE_URL}"
            f"?latitude={lat}&longitude={lon}"
            "&current=temperature_2m,weathercode,windspeed_10m"
            "&hourly=temperature_2m,et0_fao_evapotranspiration,uv_index,"
            "surface_pressure,soil_moisture_0_1cm,precipitation_probability,"
            "weathercode,relativehumidity_2m"
            "&daily=et0_fao_evapotranspiration,temperature_2m_max,temperature_2m_min,sunrise,sunset"
            "&forecast_days=2&timezone=auto"
        )
        response = requests.get(url, timeout=self.TIMEOUT)
        response.raise_for_status()
        return response.json()

    # ──────────────────────────────────────────────
    # ALERTS DATA (usado por LocalAlertService)
    # Variables: temperatura, lluvia, nieve, viento, niebla, helada, tormenta
    # ──────────────────────────────────────────────
    def get_alerts_data(self, lat: float, lon: float) -> dict:
        url = (
            f"{self.BASE_URL}"
            f"?latitude={lat}&longitude={lon}"
            "&hourly=temperature_2m,dew_point_2m,precipitation,snowfall,"
            "wind_speed_10m,wind_gusts_10m,relative_humidity_2m,"
            "visibility,cape,weathercode,precipitation_probability"
            "&forecast_days=2&timezone=auto"
        )
        response = requests.get(url, timeout=self.TIMEOUT)
        response.raise_for_status()
        return response.json()

    # ──────────────────────────────────────────────
    # HAIL PREDICTOR — histórico + forecast (usado por HailPredictor)
    # ──────────────────────────────────────────────
    def get_hail_forecast(self, lat: float, lon: float) -> dict:
        vars_ = [
            "cape", "lifted_index", "freezing_level_height",
            "temperature_2m", "precipitation", "showers",
            "wind_speed_10m", "cloud_cover", "relative_humidity_2m", "weathercode",
        ]
        url = (
            f"{self.BASE_URL}"
            f"?latitude={lat}&longitude={lon}"
            "&hourly=" + ",".join(vars_) +
            "&past_days=7&forecast_days=2&timezone=auto&models=icon_eu"
        )
        response = requests.get(url, timeout=15)
        response.raise_for_status()
        return response.json()

    def get_hail_archive(self, lat: float, lon: float, start_date: str, end_date: str) -> dict:
        vars_ = [
            "cape", "lifted_index", "freezing_level_height",
            "temperature_2m", "precipitation", "showers",
            "wind_speed_10m", "cloud_cover", "relative_humidity_2m", "weather_code",
        ]
        url = (
            f"{self.ARCHIVE_URL}"
            f"?latitude={lat}&longitude={lon}"
            f"&start_date={start_date}&end_date={end_date}"
            "&hourly=" + ",".join(vars_) +
            "&timezone=auto"
        )
        response = requests.get(url, timeout=20)
        response.raise_for_status()
        return response.json()

    # ──────────────────────────────────────────────
    # HELPER — índice de la hora actual en un array hourly
    # ──────────────────────────────────────────────
    @staticmethod
    def current_hour_index(times: list) -> int:
        now = datetime.now().replace(minute=0, second=0, microsecond=0)
        for i, t in enumerate(times):
            if datetime.fromisoformat(t) == now:
                return i
        return 0

    @staticmethod
    def safe(lst: list, idx: int, decimals: int = 2):
        """Extrae un valor de una lista con seguridad."""
        if lst and idx < len(lst) and lst[idx] is not None:
            return round(float(lst[idx]), decimals)
        return None