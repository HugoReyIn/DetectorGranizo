"""
LocalAlertService.py
Calcula alertas meteorológicas propias basadas en datos de Open-Meteo,
usando umbrales similares a los de AEMET Meteoalerta por región.

Regiones detectadas por coordenadas:
  - Canarias          (lat 27-29.5, lon -18.5 a -13)
  - Baleares          (lat 38.5-40.2, lon 1.1-4.5)
  - Ceuta             (lat 35.8-35.95, lon -5.4 a -5.25)
  - Melilla           (lat 35.25-35.35, lon -2.98 a -2.9)
  - Sur (And/Mur/Val) (lat < 39)
  - Norte peninsular  (lat >= 39)

Fenómenos: calor, lluvia, nieve, granizo
Niveles:   verde / amarillo / naranja / rojo
"""

from datetime import datetime


_LEVEL_ORDER = {"verde": 0, "amarillo": 1, "naranja": 2, "rojo": 3}


# ──────────────────────────────────────────────────────────────────────
# UMBRALES POR REGIÓN
# Fuente: AEMET Plan Meteoalerta — Umbrales y niveles de aviso
# Formato: [amarillo, naranja, rojo]
# ──────────────────────────────────────────────────────────────────────
_THRESHOLDS = {
    # ── Norte peninsular (Galicia, Asturias, Cantabria, PV, Navarra, Aragón norte, Castilla norte)
    "norte": {
        "lluvia_1h":  [15, 30, 60],
        "lluvia_12h": [30, 60, 100],
        "nieve_24h":  [2,  10, 20],
        "temp_max":   [36, 40, 44],
        "temp_min":   [-8, -12, -18],
        "viento":     [70, 90, 120],
    },
    # ── Sur peninsular (Andalucía, Murcia, C. Valenciana, Extremadura, Castilla-La Mancha, Madrid)
    "sur": {
        "lluvia_1h":  [20, 40, 60],
        "lluvia_12h": [40, 70, 120],
        "nieve_24h":  [2,  10, 20],
        "temp_max":   [40, 44, 46],
        "temp_min":   [-4, -8, -12],
        "viento":     [70, 90, 120],
    },
    # ── Canarias
    "canarias": {
        "lluvia_1h":  [15, 30, 50],
        "lluvia_12h": [30, 60, 100],
        "nieve_24h":  [2,  5,  15],
        "temp_max":   [36, 40, 44],
        "temp_min":   [0,  -4, -8],
        "viento":     [70, 90, 120],
    },
    # ── Baleares
    "baleares": {
        "lluvia_1h":  [20, 40, 70],
        "lluvia_12h": [40, 80, 130],
        "nieve_24h":  [2,  5,  15],
        "temp_max":   [38, 42, 44],
        "temp_min":   [-2, -6, -10],
        "viento":     [70, 90, 120],
    },
    # ── Ceuta y Melilla
    "ceuta_melilla": {
        "lluvia_1h":  [20, 40, 60],
        "lluvia_12h": [40, 70, 100],
        "nieve_24h":  [2,  5,  10],
        "temp_max":   [38, 42, 44],
        "temp_min":   [0,  -4, -8],
        "viento":     [70, 90, 120],
    },
}


def _get_region(lat: float, lon: float) -> str:
    """Detecta la región por coordenadas."""
    # Canarias
    if 27.0 <= lat <= 29.5 and -18.5 <= lon <= -13.0:
        return "canarias"
    # Baleares
    if 38.5 <= lat <= 40.2 and 1.1 <= lon <= 4.5:
        return "baleares"
    # Ceuta
    if 35.8 <= lat <= 35.95 and -5.4 <= lon <= -5.25:
        return "ceuta_melilla"
    # Melilla
    if 35.25 <= lat <= 35.40 and -2.98 <= lon <= -2.88:
        return "ceuta_melilla"
    # Norte peninsular (lat >= 39.5 aprox)
    if lat >= 39.5:
        return "norte"
    # Sur peninsular
    return "sur"


def _nivel(value, thresholds: list) -> str:
    """Devuelve el nivel de alerta según los umbrales [amarillo, naranja, rojo]."""
    if value >= thresholds[2]:
        return "rojo"
    if value >= thresholds[1]:
        return "naranja"
    if value >= thresholds[0]:
        return "amarillo"
    return "verde"


def _default_result() -> dict:
    return {
        "calor":   {"nivel": "verde", "valor": None},
        "lluvia":  {"nivel": "verde", "valor": None},
        "nieve":   {"nivel": "verde", "valor": None},
        "granizo": {"nivel": "verde", "valor": None},
        "ticker":  ["No hay alertas activas"],
    }


def calculate_alerts(meteo_data: dict, lat: float = 40.0, lon: float = -3.0) -> dict:
    """
    Calcula alertas a partir del JSON de Open-Meteo.
    Analiza las próximas 24h de datos horarios.

    Args:
        meteo_data: respuesta de OpenMeteoFacade.get_alerts_data()
        lat, lon:   coordenadas para detectar la región

    Returns:
        dict con estructura compatible con el frontend (calor/lluvia/nieve/granizo/ticker)
    """
    result = _default_result()
    thr    = _THRESHOLDS[_get_region(lat, lon)]
    hourly = meteo_data.get("hourly", {})
    times  = hourly.get("time", [])

    if not times:
        return result

    # Índice de la hora actual
    now = datetime.now().replace(minute=0, second=0, microsecond=0)
    idx = 0
    for i, t in enumerate(times):
        try:
            if datetime.fromisoformat(t) >= now:
                idx = i
                break
        except Exception:
            pass

    end_idx = min(idx + 24, len(times))

    # ── TEMPERATURA MÁXIMA (calor) ──
    temps = hourly.get("temperature_2m", [])
    if temps:
        temp_max_24h = max((t for t in temps[idx:end_idx] if t is not None), default=None)
        if temp_max_24h is not None:
            nivel = _nivel(temp_max_24h, thr["temp_max"])
            if nivel != "verde":
                result["calor"] = {"nivel": nivel, "valor": f"{temp_max_24h:.1f}ºC"}

    # ── LLUVIA ──
    precip_h = hourly.get("precipitation", [])
    if precip_h:
        max_1h  = max((p for p in precip_h[idx:end_idx] if p is not None), default=0.0)
        sum_12h = sum(p for p in precip_h[idx:min(idx+12, end_idx)] if p is not None)

        nivel_1h  = _nivel(max_1h,  thr["lluvia_1h"])
        nivel_12h = _nivel(sum_12h, thr["lluvia_12h"])

        # Tomar el peor nivel entre 1h y 12h
        nivel_lluvia = nivel_1h if _LEVEL_ORDER[nivel_1h] >= _LEVEL_ORDER[nivel_12h] else nivel_12h
        if nivel_lluvia != "verde":
            result["lluvia"] = {
                "nivel": nivel_lluvia,
                "valor": f"{max_1h:.1f}mm/1h · {sum_12h:.1f}mm/12h"
            }

    # ── NIEVE ──
    snowfall_h = hourly.get("snowfall", [])
    if snowfall_h:
        snow_24h = sum(s for s in snowfall_h[idx:end_idx] if s is not None)
        nivel = _nivel(snow_24h, thr["nieve_24h"])
        if nivel != "verde":
            result["nieve"] = {"nivel": nivel, "valor": f"{snow_24h:.1f}cm/24h"}

    # ── GRANIZO (weathercode Open-Meteo) ──
    # 77=granizo fino, 96=tormenta con granizo leve, 99=tormenta con granizo fuerte
    wcodes = hourly.get("weathercode", [])
    if wcodes:
        max_wcode = max((w for w in wcodes[idx:end_idx] if w is not None), default=0)
        if max_wcode == 99:
            result["granizo"] = {"nivel": "rojo",     "valor": "Tormenta con granizo fuerte"}
        elif max_wcode == 96:
            result["granizo"] = {"nivel": "naranja",  "valor": "Tormenta con granizo"}
        elif max_wcode == 77:
            result["granizo"] = {"nivel": "amarillo", "valor": "Granizo fino"}

    # ── TICKER ──
    LABEL = {"calor": "calor", "lluvia": "lluvia", "nieve": "nieve", "granizo": "granizo"}
    msgs  = []
    for tipo, info in result.items():
        if tipo == "ticker" or info["nivel"] == "verde":
            continue
        nivel_txt = info["nivel"].capitalize()
        valor_txt = f": {info['valor']}" if info.get("valor") else ""
        msgs.append(f"Alerta {nivel_txt} por {LABEL[tipo]}{valor_txt}")

    result["ticker"] = msgs if msgs else ["No hay alertas activas"]
    return result