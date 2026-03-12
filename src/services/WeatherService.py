"""
WeatherService.py
Application Service — orquesta toda la lógica meteorológica y agronómica.
Usa los facades como única vía de acceso a APIs externas.
"""

import xml.etree.ElementTree as ET
from datetime import datetime

from facades.OpenMeteoFacade import OpenMeteoFacade
from facades.NominatimFacade import NominatimFacade
from facades.AemetFacade import AemetFacade
from ia.HailPredictor import predict_hail
from ia.AgroAgent import get_card_insights


# ──────────────────────────────────────────────────────────────────────────────
# CONSTANTES AEMET
# ──────────────────────────────────────────────────────────────────────────────
_CAP_EVENT_MAP = {
    "calor": "calor", "heat": "calor",
    "temperatura máxima": "calor", "temperatura minima": "calor",
    "bochorno": "calor",
    "lluvia": "lluvia", "rain": "lluvia",
    "precipitaciones": "lluvia",
    "tormenta": "lluvia", "storm": "lluvia",
    "thunderstorm": "lluvia",
    "nieve": "nieve", "snow": "nieve",
    "nevada": "nieve",
    "granizo": "granizo", "hail": "granizo",
    "piedra": "granizo",
}

_CAP_SEVERITY_MAP = {
    "minor":    "amarillo",
    "moderate": "naranja",
    "severe":   "rojo",
    "extreme":  "rojo",
    "amarillo": "amarillo",
    "naranja":  "naranja",
    "rojo":     "rojo",
}

_LEVEL_ORDER = {"verde": 0, "amarillo": 1, "naranja": 2, "rojo": 3}
_CAP_NS      = {"cap": "urn:oasis:names:tc:emergency:cap:1.2"}

_AEMET_TTL  = 3600   # segundos
_HAIL_TTL   = 3600


def _default_aemet_result() -> dict:
    return {
        "calor":   {"nivel": "verde", "valor": None},
        "lluvia":  {"nivel": "verde", "valor": None},
        "nieve":   {"nivel": "verde", "valor": None},
        "granizo": {"nivel": "verde", "valor": None},
        "ticker":  ["No hay alertas activas"],
    }


# ──────────────────────────────────────────────────────────────────────────────
# SERVICIO
# ──────────────────────────────────────────────────────────────────────────────
class WeatherService:

    def __init__(
        self,
        meteo_facade:     OpenMeteoFacade,
        nominatim_facade: NominatimFacade,
        aemet_facade:     AemetFacade,
    ):
        self._meteo     = meteo_facade
        self._nominatim = nominatim_facade
        self._aemet     = aemet_facade

        self._aemet_cache: dict = {}
        self._hail_cache:  dict = {}

    # ──────────────────────────────────────────────
    # MUNICIPIO
    # ──────────────────────────────────────────────
    def get_municipality(self, lat: float, lon: float) -> str:
        return self._nominatim.get_municipality(lat, lon)

    # ──────────────────────────────────────────────
    # WEATHER ACTUAL
    # ──────────────────────────────────────────────
    def get_current_weather(self, lat: float, lon: float) -> dict:
        data    = self._meteo.get_current_weather(lat, lon)
        current = data.get("current", {})
        hourly  = data.get("hourly",  {})
        daily   = data.get("daily",   {})
        times   = hourly.get("time",  [])

        idx         = OpenMeteoFacade.current_hour_index(times)
        safe        = OpenMeteoFacade.safe
        weathercode = current.get("weathercode", 0)

        precipitation     = hourly.get("precipitation",         [0])[idx] or 0
        snowfall          = hourly.get("snowfall",              [0])[idx] or 0
        precip_prob       = hourly.get("precipitation_probability", [0])[idx] or 0
        soil_moisture_raw = hourly.get("soil_moisture_0_1cm",   [None])[idx]

        hail_probability = precip_prob if weathercode in (96, 99) else 0

        return {
            "temp_actual":  current.get("temperature_2m"),
            "humidity":     hourly.get("relativehumidity_2m",  [None])[idx],
            "dew_point":    hourly.get("dewpoint_2m",          [None])[idx],
            "wind_speed":   current.get("windspeed_10m"),
            "wind_deg":     current.get("winddirection_10m"),
            "rain":         round(float(precipitation), 1),
            "snow":         round(float(snowfall), 1),
            "hail":         int(hail_probability),
            "soil_moisture": round(soil_moisture_raw, 3) if soil_moisture_raw is not None else None,
            "weathercode":  weathercode,
            "temp_max":     daily.get("temperature_2m_max",  [None])[0],
            "temp_min":     daily.get("temperature_2m_min",  [None])[0],
            "sunrise":      daily.get("sunrise",             [None])[0],
            "sunset":       daily.get("sunset",              [None])[0],
            "daily": {
                "time":               daily.get("time"),
                "weathercode":        daily.get("weathercode"),
                "temperature_2m_max": daily.get("temperature_2m_max"),
                "temperature_2m_min": daily.get("temperature_2m_min"),
                "sunrise":            daily.get("sunrise"),
                "sunset":             daily.get("sunset"),
            },
        }

    # ──────────────────────────────────────────────
    # HOURLY WEATHER
    # ──────────────────────────────────────────────
    def get_hourly_weather(self, lat: float, lon: float) -> list[dict]:
        data   = self._meteo.get_hourly_forecast(lat, lon)
        hourly = data.get("hourly", {})
        result = []

        for i in range(len(hourly.get("time", []))):
            code = hourly["weathercode"][i]
            hail = {77: 50, 96: 70, 99: 100}.get(code, 0)
            result.append({
                "time":       hourly["time"][i],
                "temp":       hourly["temperature_2m"][i],
                "rain":       hourly["precipitation"][i],
                "prob_rain":  hourly["precipitation_probability"][i],
                "humidity":   hourly["relativehumidity_2m"][i],
                "wind_speed": hourly["windspeed_10m"][i],
                "wind_dir":   hourly["winddirection_10m"][i],
                "hail":       hail,
            })
        return result

    # ──────────────────────────────────────────────
    # AGRONOMIC DATA
    # ──────────────────────────────────────────────
    def get_agronomic_data(self, lat: float, lon: float) -> dict:
        data   = self._meteo.get_agronomic_data(lat, lon)
        hourly = data.get("hourly", {})
        daily  = data.get("daily",  {})
        times  = hourly.get("time", [])
        idx    = OpenMeteoFacade.current_hour_index(times)
        safe   = OpenMeteoFacade.safe

        temps_24h  = hourly.get("temperature_2m", [])
        start_idx  = max(0, idx - 24)
        cold_hours = sum(
            1 for t in temps_24h[start_idx: idx + 1]
            if t is not None and 0 < t <= 7
        )

        return {
            "et0_current":      safe(hourly.get("et0_fao_evapotranspiration", []), idx, 3),
            "uv_index":         safe(hourly.get("uv_index",                   []), idx, 1),
            "pressure":         safe(hourly.get("surface_pressure",           []), idx, 1),
            "soil_moisture_0":  safe(hourly.get("soil_moisture_0_1cm",        []), idx, 3),
            "soil_moisture_1":  safe(hourly.get("soil_moisture_1_3cm",        []), idx, 3),
            "soil_moisture_3":  safe(hourly.get("soil_moisture_3_9cm",        []), idx, 3),
            "soil_temp_surface":safe(hourly.get("soil_temperature_0cm",       []), idx, 1),
            "soil_temp_6cm":    safe(hourly.get("soil_temperature_6cm",       []), idx, 1),
            "soil_temp_18cm":   safe(hourly.get("soil_temperature_18cm",      []), idx, 1),
            "solar_radiation":  safe(hourly.get("shortwave_radiation",        []), idx, 1),
            "vpd":              safe(hourly.get("vapour_pressure_deficit",    []), idx, 3),
            "cold_hours_24h":   cold_hours,
            "et0_today":        safe(daily.get("et0_fao_evapotranspiration",  []), 0, 2),
            "uv_max_today":     safe(daily.get("uv_index_max",                []), 0, 1),
            "rain_today":       safe(daily.get("rain_sum",                    []), 0, 1),
            "temp_max_today":   safe(daily.get("temperature_2m_max",         []), 0, 1),
            "temp_min_today":   safe(daily.get("temperature_2m_min",         []), 0, 1),
            "et0_forecast": [
                {
                    "date":  daily.get("time", [])[i] if i < len(daily.get("time", [])) else None,
                    "et0":   safe(daily.get("et0_fao_evapotranspiration", []), i, 2),
                    "uv_max":safe(daily.get("uv_index_max",               []), i, 1),
                    "rain":  safe(daily.get("rain_sum",                   []), i, 1),
                    "tmax":  safe(daily.get("temperature_2m_max",        []), i, 1),
                    "tmin":  safe(daily.get("temperature_2m_min",        []), i, 1),
                }
                for i in range(1, min(5, len(daily.get("time", []))))
            ],
            "et0_hourly_today": [
                {
                    "time":      times[i].split("T")[1][:5] if i < len(times) else "",
                    "et0":       safe(hourly.get("et0_fao_evapotranspiration", []), i, 3),
                    "uv":        safe(hourly.get("uv_index",                   []), i, 1),
                    "radiation": safe(hourly.get("shortwave_radiation",        []), i, 1),
                }
                for i in range(idx, min(idx + 24, len(times)))
            ],
        }

    # ──────────────────────────────────────────────
    # FIELD SUMMARY
    # ──────────────────────────────────────────────
    def get_field_summary(self, lat: float, lon: float) -> dict:
        data    = self._meteo.get_field_summary(lat, lon)
        current = data.get("current", {})
        hourly  = data.get("hourly",  {})
        daily   = data.get("daily",   {})
        times   = hourly.get("time",  [])
        idx     = OpenMeteoFacade.current_hour_index(times)
        safe    = OpenMeteoFacade.safe

        codes_6h   = hourly.get("weathercode", [])[idx: idx + 6]
        hail_probs = [{77: 50, 96: 70, 99: 100}.get(c, 0) for c in codes_6h]
        max_hail   = max(hail_probs) if hail_probs else 0

        temps      = hourly.get("temperature_2m", [])
        cold_hours = sum(
            1 for t in temps[max(0, idx - 24): idx + 1]
            if t is not None and 0 < t <= 7
        )

        return {
            "temp":           current.get("temperature_2m"),
            "weathercode":    current.get("weathercode", 0),
            "wind":           current.get("windspeed_10m"),
            "humidity":       safe(hourly.get("relativehumidity_2m", []), idx),
            "pressure":       safe(hourly.get("surface_pressure",    []), idx, 1),
            "soil_moisture":  safe(hourly.get("soil_moisture_0_1cm", []), idx, 3),
            "uv_index":       safe(hourly.get("uv_index",            []), idx, 1),
            "et0_today":      safe(daily.get("et0_fao_evapotranspiration", []), 0, 2),
            "temp_max":       safe(daily.get("temperature_2m_max",  []), 0, 1),
            "temp_min":       safe(daily.get("temperature_2m_min",  []), 0, 1),
            "hail_risk_6h":   max_hail,
            "cold_hours_24h": cold_hours,
        }

    # ──────────────────────────────────────────────
    # AEMET ALERTS (con caché)
    # ──────────────────────────────────────────────
    def get_aemet_alerts(self, lat: float, lon: float) -> dict:
        cache_key = f"aemet_{round(lat, 2)}_{round(lon, 2)}"
        now       = datetime.now()

        cached = self._aemet_cache.get(cache_key)
        if cached and (now - cached["ts"]).total_seconds() < _AEMET_TTL:
            return cached["data"]

        result = _default_aemet_result()

        try:
            province_words = self._get_province_words(lat, lon)
            content_type, body = self._aemet.fetch_alerts_raw()

            if "xml" in content_type or body.strip().startswith("<"):
                self._parse_cap_xml(body, province_words, result)
            elif "json" in content_type:
                self._parse_cap_json(body, province_words, result)

        except Exception as e:
            print(f"[AEMET] Error: {e} — usando valores por defecto")

        result["ticker"] = self._build_ticker(result)
        self._aemet_cache[cache_key] = {"ts": now, "data": result}
        return result

    # ──────────────────────────────────────────────
    # HAIL PREDICTION (con caché)
    # ──────────────────────────────────────────────
    def get_hail_prediction(self, lat: float, lon: float) -> list[dict]:
        cache_key = f"{round(lat, 3)}_{round(lon, 3)}"
        now       = datetime.now()

        cached = self._hail_cache.get(cache_key)
        if cached and (now - cached["timestamp"]).total_seconds() < _HAIL_TTL:
            return cached["data"]

        prediction = predict_hail(lat, lon)
        self._hail_cache[cache_key] = {"timestamp": now, "data": prediction}
        return prediction

    # ──────────────────────────────────────────────
    # AGRO INSIGHTS
    # ──────────────────────────────────────────────
    def get_agro_insights(self, data: dict, crop_type: str) -> dict:
        return get_card_insights(data, crop_type)

    # ──────────────────────────────────────────────
    # HELPERS PRIVADOS — AEMET
    # ──────────────────────────────────────────────
    def _get_province_words(self, lat: float, lon: float) -> set[str]:
        province = self._nominatim.get_province(lat, lon)
        return {w.strip("/()" ) for w in province.split()}

    def _parse_cap_xml(self, xml_text: str, province_words: set, result: dict) -> None:
        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError:
            return

        alerts = root.findall(".//cap:alert", _CAP_NS) or (
            [root] if root.tag.endswith("alert") else []
        )

        for alert in alerts:
            for info in alert.findall("cap:info", _CAP_NS):
                lang = info.findtext("cap:language", default="es", namespaces=_CAP_NS)
                if lang and lang.lower() not in ("es", "es-es", ""):
                    continue

                event        = (info.findtext("cap:event",    default="", namespaces=_CAP_NS) or "").lower()
                severity_raw = (info.findtext("cap:severity", default="", namespaces=_CAP_NS) or "").lower()
                area_desc    = " ".join(
                    (a.findtext("cap:areaDesc", default="", namespaces=_CAP_NS) or "").lower()
                    for a in info.findall("cap:area", _CAP_NS)
                )

                awareness_type  = ""
                awareness_level = ""
                valor           = None
                for param in info.findall("cap:parameter", _CAP_NS):
                    pname = (param.findtext("cap:valueName", default="", namespaces=_CAP_NS) or "").lower()
                    pval  = (param.findtext("cap:value",     default="", namespaces=_CAP_NS) or "").lower()
                    if "awareness_type"  in pname: awareness_type  = pval
                    if "awareness_level" in pname: awareness_level = pval
                    if any(k in pname for k in ("umbral", "threshold", "valor", "value")):
                        valor = pval

                zona_text = area_desc + " " + event
                if province_words and not any(w in zona_text for w in province_words):
                    continue

                tipo = next(
                    (cat for kw, cat in _CAP_EVENT_MAP.items() if kw in event + " " + awareness_type),
                    None,
                )
                if not tipo:
                    continue

                nivel = _CAP_SEVERITY_MAP.get(severity_raw) or _CAP_SEVERITY_MAP.get(awareness_level, "amarillo")
                if _LEVEL_ORDER[nivel] > _LEVEL_ORDER[result[tipo]["nivel"]]:
                    result[tipo]["nivel"] = nivel
                    result[tipo]["valor"] = valor

    def _parse_cap_json(self, body: str, province_words: set, result: dict) -> None:
        import json
        try:
            avisos = json.loads(body)
        except Exception:
            return

        if not isinstance(avisos, list):
            return

        for aviso in avisos:
            event  = (aviso.get("evento") or aviso.get("event") or "").lower()
            severity = (aviso.get("nivel") or aviso.get("severity") or "").lower()
            zona   = (aviso.get("zona")   or aviso.get("area")    or "").lower()
            if province_words and not any(w in zona for w in province_words):
                continue
            tipo = next((cat for kw, cat in _CAP_EVENT_MAP.items() if kw in event), None)
            if not tipo:
                continue
            nivel = _CAP_SEVERITY_MAP.get(severity, "amarillo")
            if _LEVEL_ORDER[nivel] > _LEVEL_ORDER[result[tipo]["nivel"]]:
                result[tipo]["nivel"] = nivel
                result[tipo]["valor"] = aviso.get("umbral")

    @staticmethod
    def _build_ticker(result: dict) -> list[str]:
        LABEL = {"calor": "calor", "lluvia": "lluvia/tormentas", "nieve": "nieve", "granizo": "granizo"}
        UNIT  = {"calor": "ºC",   "lluvia": " mm",              "nieve": " cm",   "granizo": ""}
        msgs  = []
        for tipo, info in result.items():
            if tipo == "ticker" or info["nivel"] == "verde":
                continue
            nivel_txt = info["nivel"].capitalize()
            valor_txt = (
                f": temperatura > {info['valor']}{UNIT[tipo]}" if (tipo == "calor" and info["valor"])
                else (f": {info['valor']}{UNIT[tipo]}" if info["valor"] else "")
            )
            msgs.append(f"Alerta {nivel_txt} por {LABEL[tipo]}{valor_txt}")
        return msgs or ["No hay alertas activas"]