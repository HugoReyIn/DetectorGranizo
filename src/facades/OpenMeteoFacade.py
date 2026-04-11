"""
OpenMeteoFacade.py
Remote Facade — encapsula todas las llamadas HTTP a la API Open-Meteo.
Main.py y los servicios nunca llaman a Open-Meteo directamente.

Mejoras de rendimiento:
  - Caché TTL por endpoint: evita llamadas repetidas a la API dentro de la
    misma hora. Usa cachetools.TTLCache con límite de entradas para no crecer
    indefinidamente. Instalar: pip install cachetools
  - current_hour_index en O(1): calcula el índice directamente desde el primer
    timestamp del array, sin iterar toda la lista.
"""

import requests
from datetime import datetime

from cachetools import TTLCache
from cachetools.keys import hashkey

from config import OPEN_METEO_ARCHIVE_URL, OPEN_METEO_BASE_URL, OPEN_METEO_TIMEOUT


# TTL en segundos para cada tipo de dato (los datos horarios cambian cada hora)
_TTL_CURRENT  = 1800   # 30 min — datos actuales
_TTL_HOURLY   = 3600   # 1 h   — forecast horario
_TTL_AGRONOMIC = 3600  # 1 h   — datos agronómicos (incluye 30 días históricos)
_TTL_SUMMARY  = 1800   # 30 min — resumen de campo
_TTL_ALERTS   = 3600   # 1 h   — datos para alertas
_TTL_HAIL     = 3600   # 1 h   — predicción de granizo

_MAX_ENTRIES  = 200    # máximo de coordenadas distintas en caché


class OpenMeteoFacade:

    BASE_URL    = OPEN_METEO_BASE_URL
    ARCHIVE_URL = OPEN_METEO_ARCHIVE_URL
    TIMEOUT     = OPEN_METEO_TIMEOUT

    def __init__(self):
        # Una caché por tipo de endpoint — cada una con su propio TTL
        self._cache_current   = TTLCache(maxsize=_MAX_ENTRIES, ttl=_TTL_CURRENT)
        self._cache_hourly    = TTLCache(maxsize=_MAX_ENTRIES, ttl=_TTL_HOURLY)
        self._cache_agronomic = TTLCache(maxsize=_MAX_ENTRIES, ttl=_TTL_AGRONOMIC)
        self._cache_summary   = TTLCache(maxsize=_MAX_ENTRIES, ttl=_TTL_SUMMARY)
        self._cache_alerts    = TTLCache(maxsize=_MAX_ENTRIES, ttl=_TTL_ALERTS)
        self._cache_hail      = TTLCache(maxsize=_MAX_ENTRIES, ttl=_TTL_HAIL)

    # ──────────────────────────────────────────────
    # HELPER INTERNO — clave de caché redondeada a 2 decimales (~1 km)
    # ──────────────────────────────────────────────
    @staticmethod
    def _key(lat: float, lon: float):
        return hashkey(round(lat, 2), round(lon, 2))

    # ──────────────────────────────────────────────
    # WEATHER ACTUAL + DAILY (usado en /get-weather)
    # ──────────────────────────────────────────────
    def get_current_weather(self, lat: float, lon: float) -> dict:
        key = self._key(lat, lon)
        if key in self._cache_current:
            return self._cache_current[key]

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
        data = response.json()
        self._cache_current[key] = data
        return data

    # ──────────────────────────────────────────────
    # HOURLY FORECAST (usado en /get-hourly-weather)
    # ──────────────────────────────────────────────
    def get_hourly_forecast(self, lat: float, lon: float) -> dict:
        key = self._key(lat, lon)
        if key in self._cache_hourly:
            return self._cache_hourly[key]

        url = (
            f"{self.BASE_URL}"
            f"?latitude={lat}&longitude={lon}"
            "&hourly=temperature_2m,precipitation,precipitation_probability,"
            "relativehumidity_2m,windspeed_10m,winddirection_10m,weathercode"
            "&forecast_days=5&timezone=auto"
        )
        response = requests.get(url, timeout=self.TIMEOUT)
        response.raise_for_status()
        data = response.json()
        self._cache_hourly[key] = data
        return data

    # ──────────────────────────────────────────────
    # AGRONOMIC DATA (usado en /get-agronomic-data)
    # ──────────────────────────────────────────────
    def get_agronomic_data(self, lat: float, lon: float) -> dict:
        key = self._key(lat, lon)
        if key in self._cache_agronomic:
            return self._cache_agronomic[key]

        url = (
            f"{self.BASE_URL}"
            f"?latitude={lat}&longitude={lon}"
            "&hourly=et0_fao_evapotranspiration,uv_index,surface_pressure,"
            "soil_moisture_0_1cm,soil_moisture_1_3cm,soil_moisture_3_9cm,"
            "soil_temperature_0cm,soil_temperature_6cm,soil_temperature_18cm,"
            "temperature_2m,windspeed_10m,shortwave_radiation,vapour_pressure_deficit,"
            "relative_humidity_2m,precipitation"
            "&daily=et0_fao_evapotranspiration,uv_index_max,precipitation_sum,"
            "rain_sum,sunrise,sunset,temperature_2m_max,temperature_2m_min"
            "&forecast_days=5&past_days=30&timezone=auto"
        )
        response = requests.get(url, timeout=self.TIMEOUT)
        response.raise_for_status()
        data = response.json()
        self._cache_agronomic[key] = data
        return data

    # ──────────────────────────────────────────────
    # FIELD SUMMARY (usado en /get-field-summary)
    # ──────────────────────────────────────────────
    def get_field_summary(self, lat: float, lon: float) -> dict:
        key = self._key(lat, lon)
        if key in self._cache_summary:
            return self._cache_summary[key]

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
        data = response.json()
        self._cache_summary[key] = data
        return data

    # ──────────────────────────────────────────────
    # ALERTS DATA (usado por LocalAlertService)
    # ──────────────────────────────────────────────
    def get_alerts_data(self, lat: float, lon: float) -> dict:
        key = self._key(lat, lon)
        if key in self._cache_alerts:
            return self._cache_alerts[key]

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
        data = response.json()
        self._cache_alerts[key] = data
        return data

    # ──────────────────────────────────────────────
    # HAIL PREDICTOR — histórico + forecast
    # ──────────────────────────────────────────────
    def get_hail_forecast(self, lat: float, lon: float) -> dict:
        key = self._key(lat, lon)
        if key in self._cache_hail:
            return self._cache_hail[key]

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
        data = response.json()
        self._cache_hail[key] = data
        return data

    def get_hail_archive(self, lat: float, lon: float, start_date: str, end_date: str) -> dict:
        # El archivo histórico no se cachea: las fechas varían en cada llamada
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
    # HELPER — índice de la hora actual en O(1)
    # ──────────────────────────────────────────────
    @staticmethod
    def current_hour_index(times: list) -> int:
        """
        Calcula el índice de la hora actual en el array hourly sin iterar.

        Open-Meteo devuelve timestamps en formato ISO con intervalos exactos
        de 1 hora. Dado el primer timestamp, el índice es simplemente la
        diferencia en horas entre ahora y ese primer timestamp.
        """
        if not times:
            return 0
        try:
            first = datetime.fromisoformat(times[0])
            now   = datetime.now().replace(minute=0, second=0, microsecond=0)
            # Normalizar timezone: si first tiene tzinfo, añadirla a now
            if first.tzinfo is not None:
                now = now.replace(tzinfo=first.tzinfo)
            idx = int((now - first).total_seconds() // 3600)
            return max(0, min(idx, len(times) - 1))
        except Exception:
            return 0

    @staticmethod
    def safe(lst: list, idx: int, decimals: int = 2):
        """Extrae un valor de una lista con seguridad."""
        if lst and idx < len(lst) and lst[idx] is not None:
            return round(float(lst[idx]), decimals)
        return None