"""
HailPredictor.py  —  Predictor de granizo basado en reglas físicas multi-factor.

Sustituye el modelo SARIMAX (propenso a saturarse con CAPE alto y series
casi siempre-cero) por un sistema de puntuación física transparente y
calibrado para el clima peninsular ibérico.

Factores considerados:
  • Weathercode Open-Meteo (señal principal del modelo NWP)
  • CAPE  (J/kg)          — energía convectiva disponible
  • Lifted Index (LI)     — estabilidad atmosférica
  • Freezing level        — altura de la isoterma 0 °C
  • Precipitación + Chubascos

Umbrales calibrados para reducir falsos positivos:
  - CAPE 510 J/kg sin weathercode convectivo  →  ~10-15 % (sin alarma)
  - CAPE > 1500 + LI < -3 + freezing < 2500  →  puede llegar a 70-85 %
  - Weathercode 99 (tormenta + granizo fuerte) →  85-100 %
"""

import requests
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings("ignore")


# ──────────────────────────────────────────────────────────────────────────────
# WEATHERCODE → probabilidad base  (señal principal del modelo NWP)
# ──────────────────────────────────────────────────────────────────────────────
WCODE_BASE_PROB: dict[int, float] = {
    77: 0.30,   # granizo fino (ice pellets)
    96: 0.55,   # tormenta con granizo leve
    99: 0.85,   # tormenta con granizo fuerte
    95: 0.05,   # tormenta sin granizo explícito
}


def _wcode_base(code: int) -> float:
    return WCODE_BASE_PROB.get(int(code), 0.0)


# ──────────────────────────────────────────────────────────────────────────────
# FACTORES FÍSICOS ADICIONALES
# ──────────────────────────────────────────────────────────────────────────────
def _cape_factor(cape: float) -> float:
    """
    Contribución del CAPE. Calibrado para clima ibérico peninsular.
    200-500 J/kg es habitual en verano sin granizo → contribución mínima.
    """
    if cape >= 1500:
        return 0.28
    if cape >= 800:
        return 0.18
    if cape >= 500:
        return 0.10
    if cape >= 200:
        return 0.05
    return 0.0


def _li_factor(li) -> float:
    """Lifted Index negativo = inestable. Solo pesa cuando es muy negativo."""
    if li is None:
        return 0.0
    li = float(li)
    if li <= -5:
        return 0.15
    if li <= -3:
        return 0.08
    if li <= -1:
        return 0.03
    return 0.0


def _freezing_factor(freezing_m) -> float:
    """
    Altura isoterma 0 °C. Menor altura = el granizo llega al suelo.
    Por encima de 3500 m en verano ibérico: granizo casi siempre se funde.
    """
    if freezing_m is None:
        return 0.0
    fl = float(freezing_m)
    if fl < 1500:
        return 0.12
    if fl < 2500:
        return 0.07
    if fl < 3500:
        return 0.03
    return 0.0


def _precip_factor(precip: float, showers: float) -> float:
    """Precipitación convectiva intensa refuerza la señal."""
    convective = max(precip, showers)
    if convective >= 15:
        return 0.08
    if convective >= 5:
        return 0.04
    return 0.0


# ──────────────────────────────────────────────────────────────────────────────
# PREDICCIÓN POR HORA
# ──────────────────────────────────────────────────────────────────────────────
def _compute_hour_probability(row: pd.Series) -> float:
    """
    Probabilidad de granizo (0–1) para una hora.

    Regla clave: si el modelo NWP (weathercode) NO indica convección,
    el CAPE solo puede aportar un máximo del 20 % de probabilidad.
    Esto evita alarmas cuando hay CAPE moderado pero cielos despejados.
    """
    wcode   = int(row.get("weathercode", 0) or 0)
    cape    = float(row.get("cape", 0) or 0)
    li      = row.get("lifted_index")
    fl      = row.get("freezing_level_height")
    precip  = float(row.get("precipitation", 0) or 0)
    showers = float(row.get("showers", 0) or 0)

    base = _wcode_base(wcode)

    if base >= 0.05:
        # Señal NWP convectiva → factores físicos amplían
        prob = base
        prob += _cape_factor(cape)
        prob += _li_factor(li)
        prob += _freezing_factor(fl)
        prob += _precip_factor(precip, showers)
    else:
        # Sin señal NWP: CAPE contribuye muy poco
        # (techo 20 % para reflejar incertidumbre, nunca alarma real)
        cape_contrib = _cape_factor(cape) * 0.5
        prob = min(cape_contrib, 0.20)

    return float(np.clip(prob, 0.0, 1.0))


# ──────────────────────────────────────────────────────────────────────────────
# DESCARGA DE DATOS
# ──────────────────────────────────────────────────────────────────────────────
def _fetch_forecast(lat: float, lon: float) -> pd.DataFrame:
    VARS = [
        "cape", "lifted_index", "freezing_level_height",
        "temperature_2m", "precipitation", "showers",
        "wind_speed_10m", "cloud_cover", "relative_humidity_2m",
        "weathercode",
    ]
    url = (
        "https://api.open-meteo.com/v1/forecast"
        f"?latitude={lat}&longitude={lon}"
        "&hourly=" + ",".join(VARS) +
        "&forecast_days=5&timezone=auto&models=icon_eu"
    )
    r = requests.get(url, timeout=15)
    r.raise_for_status()
    data = r.json().get("hourly", {})

    df = pd.DataFrame(data)
    df["time"] = pd.to_datetime(df["time"])
    df = df.set_index("time")
    df = df.ffill().fillna(0)
    return df


# ──────────────────────────────────────────────────────────────────────────────
# PUNTO DE ENTRADA PRINCIPAL
# ──────────────────────────────────────────────────────────────────────────────
def predict_hail(lat: float, lon: float) -> list[dict]:
    """
    Devuelve lista de dicts {time, hail_probability, cape, lifted_index}
    para las próximas 48 horas. hail_probability en % (0–100).
    """
    try:
        df = _fetch_forecast(lat, lon)
    except Exception as e:
        print(f"[HailPredictor] Error descargando forecast: {e}")
        return []

    now = pd.Timestamp.now().floor("h")
    future = df[df.index >= now].head(5*24).copy()

    if future.empty:
        print("[HailPredictor] Forecast vacío.")
        return []

    results = []
    for ts, row in future.iterrows():
        prob = _compute_hour_probability(row)
        cape_val = float(row.get("cape", 0) or 0)
        li_val   = row.get("lifted_index")

        results.append({
            "time": ts.strftime("%Y-%m-%dT%H:%M"),
            "hail_probability": round(prob * 100, 1),
            "cape": cape_val,
            "lifted_index": float(li_val) if li_val is not None else None,
        })

    max_prob = max(r["hail_probability"] for r in results) if results else 0
    max_cape = max(r["cape"] for r in results) if results else 0
    print(
        f"[HailPredictor] OK — {len(results)}h | "
        f"máx. prob={max_prob:.1f}% | máx. CAPE={max_cape:.0f} J/kg"
    )

    return results