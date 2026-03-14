"""
LocalAlertService.py
Calcula alertas meteorológicas agrícolas basadas en datos de Open-Meteo.

Alertas:
  - calor          → temperatura máxima 24h
  - helada         → temperatura mínima madrugada (03-07h) + viento
  - lluvia         → precipitación 1h y 24h
  - nieve          → acumulado 24h
  - viento         → rachas máximas 24h
  - tormenta       → weathercode + precipitación + rachas
  - granizo        → via IA (HailPredictor) + CAPE fallback
  - niebla         → visibilidad + humedad relativa

Niveles: verde / amarillo / naranja / rojo
"""

from datetime import datetime


_LEVEL_ORDER = {"verde": 0, "amarillo": 1, "naranja": 2, "rojo": 3}


def _nivel(value: float, thresholds: list) -> str:
    """Devuelve el nivel dado [amarillo, naranja, rojo]."""
    if value >= thresholds[2]:
        return "rojo"
    if value >= thresholds[1]:
        return "naranja"
    if value >= thresholds[0]:
        return "amarillo"
    return "verde"


def _nivel_inv(value: float, thresholds: list) -> str:
    """Igual pero invertido: cuanto más bajo el valor, mayor el nivel (heladas, visibilidad)."""
    if value <= thresholds[2]:
        return "rojo"
    if value <= thresholds[1]:
        return "naranja"
    if value <= thresholds[0]:
        return "amarillo"
    return "verde"


def _default_result() -> dict:
    return {
        "calor":    {"nivel": "verde", "valor": None},
        "helada":   {"nivel": "verde", "valor": None},
        "lluvia":   {"nivel": "verde", "valor": None},
        "nieve":    {"nivel": "verde", "valor": None},
        "viento":   {"nivel": "verde", "valor": None},
        "tormenta": {"nivel": "verde", "valor": None},
        "granizo":  {"nivel": "verde", "valor": None},
        "niebla":   {"nivel": "verde", "valor": None},
        "ticker":   ["No hay alertas activas"],
    }


def calculate_alerts(
    meteo_data: dict,
    lat: float = 40.0,
    lon: float = -3.0,
    hail_prediction: list | None = None,   # lista de {time, hail_probability, cape}
) -> dict:
    """
    Calcula alertas a partir del JSON de Open-Meteo + predicción IA de granizo.

    Args:
        meteo_data:      respuesta de OpenMeteoFacade.get_alerts_data()
        lat, lon:        coordenadas (para futuras regionalizaciones)
        hail_prediction: lista devuelta por HailPredictor.predict_hail()

    Returns:
        dict con calor/helada/lluvia/nieve/viento/tormenta/granizo/niebla/ticker
    """
    result = _default_result()
    hourly = meteo_data.get("hourly", {})
    times  = hourly.get("time", [])

    if not times:
        return result

    # ── Índice de la hora actual ──
    now = datetime.now().replace(minute=0, second=0, microsecond=0)
    idx = 0
    for i, t in enumerate(times):
        try:
            if datetime.fromisoformat(t) >= now:
                idx = i
                break
        except Exception:
            pass

    end_idx     = min(idx + 24, len(times))
    end_idx_12h = min(idx + 12, len(times))

    def safe_list(key):
        return hourly.get(key, [])

    temps      = safe_list("temperature_2m")
    precip     = safe_list("precipitation")
    snowfall   = safe_list("snowfall")
    wind_gusts = safe_list("wind_gusts_10m")
    wind_speed = safe_list("wind_speed_10m")
    humidity   = safe_list("relative_humidity_2m")
    visibility = safe_list("visibility")
    cape_h     = safe_list("cape")
    wcodes     = safe_list("weathercode")

    # ──────────────────────────────────────────────
    # 1. CALOR — temperatura máxima próximas 24h
    # ──────────────────────────────────────────────
    if temps:
        tmax = max((v for v in temps[idx:end_idx] if v is not None), default=None)
        if tmax is not None:
            # Umbrales agrícolas mediterráneos
            nivel = _nivel(tmax, [32, 36, 40])
            if nivel != "verde":
                result["calor"] = {"nivel": nivel, "valor": f"{tmax:.1f} °C"}

    # ──────────────────────────────────────────────
    # 2. HELADA — mínima en madrugada (03–07h) próximas 24h
    #    Penalización si viento < 10 km/h (helada radiativa más probable)
    # ──────────────────────────────────────────────
    frost_temps = []
    for i in range(idx, end_idx):
        if i >= len(times):
            break
        try:
            hour = datetime.fromisoformat(times[i]).hour
        except Exception:
            continue
        if 3 <= hour <= 7:
            v = temps[i] if i < len(temps) else None
            if v is not None:
                frost_temps.append((v, i))

    if frost_temps:
        tmin_dawn, tmin_idx = min(frost_temps, key=lambda x: x[0])

        # Penalización por calma (helada radiativa)
        ws = wind_speed[tmin_idx] if tmin_idx < len(wind_speed) else None
        radiative_bonus = 0.0
        if ws is not None and ws < 10:
            radiative_bonus = 0.5   # baja 0.5 °C efectivos el umbral

        teff = tmin_dawn - radiative_bonus  # temperatura efectiva

        # Umbrales (inversión: cuanto más bajo, peor)
        nivel = _nivel_inv(teff, [3, 1, -1])
        if nivel != "verde":
            radiative_note = " (helada radiativa)" if radiative_bonus > 0 else ""
            result["helada"] = {
                "nivel": nivel,
                "valor": f"{tmin_dawn:.1f} °C madrugada{radiative_note}"
            }

    # ──────────────────────────────────────────────
    # 3. LLUVIA — intensidad 1h y acumulado 24h
    # ──────────────────────────────────────────────
    if precip:
        max_1h   = max((v for v in precip[idx:end_idx] if v is not None), default=0.0)
        sum_24h  = sum(v for v in precip[idx:end_idx] if v is not None)

        nivel_1h  = _nivel(max_1h,  [10, 20, 40])
        nivel_24h = _nivel(sum_24h, [20, 40, 80])

        nivel_lluvia = nivel_1h if _LEVEL_ORDER[nivel_1h] >= _LEVEL_ORDER[nivel_24h] else nivel_24h
        if nivel_lluvia != "verde":
            result["lluvia"] = {
                "nivel": nivel_lluvia,
                "valor": f"{max_1h:.1f} mm/h · {sum_24h:.1f} mm/24h"
            }

    # ──────────────────────────────────────────────
    # 4. NIEVE — acumulado 24h
    # ──────────────────────────────────────────────
    if snowfall:
        snow_24h = sum(v for v in snowfall[idx:end_idx] if v is not None)
        nivel = _nivel(snow_24h, [1, 5, 20])
        if nivel != "verde":
            result["nieve"] = {"nivel": nivel, "valor": f"{snow_24h:.1f} cm/24h"}

    # ──────────────────────────────────────────────
    # 5. VIENTO — rachas máximas 24h
    # ──────────────────────────────────────────────
    if wind_gusts:
        max_gust = max((v for v in wind_gusts[idx:end_idx] if v is not None), default=0.0)
        nivel = _nivel(max_gust, [40, 70, 90])
        if nivel != "verde":
            result["viento"] = {"nivel": nivel, "valor": f"{max_gust:.0f} km/h"}

    # ──────────────────────────────────────────────
    # 6. TORMENTA — weathercode + precipitación + rachas
    # ──────────────────────────────────────────────
    # Weathercodes de tormenta: 95=tormenta, 96=con granizo leve, 99=con granizo fuerte
    STORM_CODES = {95, 96, 99}
    storm_hours = [(wcodes[i], precip[i] if i < len(precip) else 0,
                    wind_gusts[i] if i < len(wind_gusts) else 0)
                   for i in range(idx, end_idx)
                   if i < len(wcodes) and wcodes[i] in STORM_CODES]

    if storm_hours:
        max_precip_storm = max((p for _, p, _ in storm_hours if p is not None), default=0.0)
        max_gust_storm   = max((g for _, _, g in storm_hours if g is not None), default=0.0)

        # Rojo: > 30 mm/h O > 80 km/h rachas
        # Naranja: > 15 mm/h O > 60 km/h
        # Amarillo: tormenta presente
        if max_precip_storm > 30 or max_gust_storm > 80:
            nivel_tormenta = "rojo"
            val = f"{max_precip_storm:.1f} mm/h · {max_gust_storm:.0f} km/h"
        elif max_precip_storm > 15 or max_gust_storm > 60:
            nivel_tormenta = "naranja"
            val = f"{max_precip_storm:.1f} mm/h · {max_gust_storm:.0f} km/h"
        else:
            nivel_tormenta = "amarillo"
            val = "Tormenta ligera"

        result["tormenta"] = {"nivel": nivel_tormenta, "valor": val}

    # ──────────────────────────────────────────────
    # 7. GRANIZO — IA preferente, CAPE como fallback/refuerzo
    # ──────────────────────────────────────────────
    nivel_granizo = "verde"
    valor_granizo = None

    # 7a. Predicción IA (HailPredictor)
    if hail_prediction:
        now_dt = datetime.now()
        relevant = [
            p for p in hail_prediction
            if (datetime.fromisoformat(p["time"]) - now_dt).total_seconds() <= 86400
        ]
        if relevant:
            max_prob = max(p["hail_probability"] for p in relevant)
            if max_prob >= 60:
                nivel_granizo = "rojo"
                valor_granizo = f"IA: {max_prob:.0f}% prob. granizo"
            elif max_prob >= 35:
                nivel_granizo = "naranja"
                valor_granizo = f"IA: {max_prob:.0f}% prob. granizo"
            elif max_prob >= 15:
                nivel_granizo = "amarillo"
                valor_granizo = f"IA: {max_prob:.0f}% prob. granizo"

    # 7b. CAPE fallback / refuerzo si la IA no llega a naranja/rojo
    if cape_h and _LEVEL_ORDER[nivel_granizo] < _LEVEL_ORDER["naranja"]:
        max_cape = max((v for v in cape_h[idx:end_idx] if v is not None), default=0.0)
        # Combinar weathercode de granizo con CAPE
        max_wcode_granizo = max(
            (wcodes[i] for i in range(idx, end_idx)
             if i < len(wcodes) and wcodes[i] in {77, 96, 99}),
            default=0
        )
        if max_cape >= 1500 and max_wcode_granizo in {96, 99}:
            if _LEVEL_ORDER["rojo"] > _LEVEL_ORDER[nivel_granizo]:
                nivel_granizo = "rojo"
                valor_granizo = f"CAPE {max_cape:.0f} J/kg + tormenta severa"
        elif max_cape >= 800 or max_wcode_granizo in {96, 99}:
            if _LEVEL_ORDER["naranja"] > _LEVEL_ORDER[nivel_granizo]:
                nivel_granizo = "naranja"
                valor_granizo = f"CAPE {max_cape:.0f} J/kg" if max_cape >= 800 else "Tormenta convectiva"
        elif max_wcode_granizo == 77:
            if _LEVEL_ORDER["amarillo"] > _LEVEL_ORDER[nivel_granizo]:
                nivel_granizo = "amarillo"
                valor_granizo = "Granizo fino posible"

    if nivel_granizo != "verde":
        result["granizo"] = {"nivel": nivel_granizo, "valor": valor_granizo}

    # ──────────────────────────────────────────────
    # 8. NIEBLA — visibilidad + humedad
    # ──────────────────────────────────────────────
    if visibility:
        # Solo considerar horas con humedad > 90% (condición de niebla real)
        fog_vis = [
            visibility[i]
            for i in range(idx, end_idx)
            if i < len(visibility)
            and visibility[i] is not None
            and (i >= len(humidity) or (humidity[i] is not None and humidity[i] >= 90))
        ]
        if fog_vis:
            min_vis = min(fog_vis)
            # Umbrales inversos (m): [1000, 500, 200]
            nivel = _nivel_inv(min_vis, [1000, 500, 200])
            if nivel != "verde":
                result["niebla"] = {"nivel": nivel, "valor": f"{min_vis:.0f} m visibilidad"}

    # ──────────────────────────────────────────────
    # TICKER
    # ──────────────────────────────────────────────
    LABEL = {
        "calor":    "calor extremo",
        "helada":   "helada",
        "lluvia":   "lluvia intensa",
        "nieve":    "nieve",
        "viento":   "viento fuerte",
        "tormenta": "tormenta",
        "granizo":  "granizo",
        "niebla":   "niebla",
    }
    msgs = []
    for tipo, info in result.items():
        if tipo == "ticker" or info["nivel"] == "verde":
            continue
        nivel_txt = info["nivel"].capitalize()
        valor_txt = f": {info['valor']}" if info.get("valor") else ""
        msgs.append(f"Alerta {nivel_txt} por {LABEL[tipo]}{valor_txt}")

    result["ticker"] = msgs if msgs else ["No hay alertas activas"]
    return result