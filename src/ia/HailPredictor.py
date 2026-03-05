import requests
import numpy as np
import pandas as pd
from datetime import datetime
from statsmodels.tsa.statespace.sarimax import SARIMAX
import warnings
warnings.filterwarnings("ignore")


# ──────────────────────────────────────────
# WEATHERCODE → HAIL SCORE (variable objetivo)
# 0  = sin granizo
# 0.5 = granizo leve (código 77)
# 0.7 = tormenta con granizo leve (96)
# 1.0 = tormenta con granizo fuerte (99)
# ──────────────────────────────────────────
def weathercode_to_hail_score(code: int) -> float:
    return {77: 0.5, 96: 0.7, 99: 1.0}.get(code, 0.0)


# ──────────────────────────────────────────
# OBTENER DATOS DE OPEN-METEO
# Histórico (30 días) + forecast (2 días)
# ──────────────────────────────────────────
def fetch_meteo_data(lat: float, lon: float) -> dict:
    """
    Devuelve un dict con dos DataFrames:
      - 'history': últimas ~720h con hail_score calculado
      - 'future':  próximas 24h con las mismas variables exógenas
    """
    EXOG_VARS = [
        "cape",
        "lifted_index",
        "freezing_level_height",
        "temperature_2m",
        "precipitation",
        "showers",
        "wind_speed_10m",          # proxy de surface wind
        "cloud_cover",
        "relative_humidity_2m",    # proxy de RH capas medias
        "weathercode",
    ]

    # Open-Meteo soporta algunas presión-level variables solo en modelos específicos.
    # Usamos los equivalentes en superficie disponibles en el modelo icon_eu.
    url = (
        "https://api.open-meteo.com/v1/forecast"
        f"?latitude={lat}&longitude={lon}"
        "&hourly=" + ",".join(EXOG_VARS) +
        "&past_days=30"
        "&forecast_days=2"
        "&timezone=auto"
        "&models=icon_eu"
    )

    r = requests.get(url, timeout=15)
    r.raise_for_status()
    data = r.json()["hourly"]

    df = pd.DataFrame(data)
    df["time"] = pd.to_datetime(df["time"])
    df = df.set_index("time")
    df = df.fillna(method="ffill").fillna(0)

    # Variable objetivo solo en histórico (donde weathercode ya ocurrió)
    df["hail_score"] = df["weathercode"].apply(weathercode_to_hail_score)

    now = pd.Timestamp.now().floor("h")

    history = df[df.index <= now].copy()
    future  = df[df.index >  now].head(24).copy()

    # Las columnas exógenas (sin hail_score ni weathercode)
    exog_cols = [c for c in EXOG_VARS if c != "weathercode"]

    return {
        "history": history,
        "future":  future,
        "exog_cols": exog_cols,
    }


# ──────────────────────────────────────────
# ENTRENAR SARIMAX Y PREDECIR
# ──────────────────────────────────────────
def predict_hail(lat: float, lon: float) -> list[dict]:
    """
    Retorna una lista de dicts:
      [{"time": "2024-06-01T14:00", "hail_probability": 72}, ...]
    para las próximas 24 horas.
    """
    meteo = fetch_meteo_data(lat, lon)
    history  = meteo["history"]
    future   = meteo["future"]
    exog_cols = meteo["exog_cols"]

    # ── Necesitamos al menos 48h de histórico para SARIMAX ──
    if len(history) < 48:
        return _fallback_from_weathercode(future)

    endog = history["hail_score"].values.astype(float)
    exog_train = history[exog_cols].values.astype(float)
    exog_pred  = future[exog_cols].values.astype(float)

    # ── Orden SARIMAX: (1,0,1) sin componente estacional
    #    (datos horarios, estacionalidad diaria sería s=24 y costosa)
    # ──────────────────────────────────────────────────────────────
    try:
        model = SARIMAX(
            endog,
            exog=exog_train,
            order=(1, 0, 1),
            seasonal_order=(0, 0, 0, 0),
            enforce_stationarity=False,
            enforce_invertibility=False,
        )
        fit = model.fit(disp=False, maxiter=100)

        forecast = fit.forecast(steps=len(future), exog=exog_pred)

        # Convertir a probabilidad 0-100 con clip y escala
        probabilities = np.clip(forecast, 0, 1) * 100
        probabilities = probabilities.round(1)

    except Exception as e:
        print(f"[HailPredictor] SARIMAX falló ({e}), usando fallback.")
        return _fallback_from_weathercode(future)

    results = []
    for i, (ts, prob) in enumerate(zip(future.index, probabilities)):
        results.append({
            "time": ts.strftime("%Y-%m-%dT%H:%M"),
            "hail_probability": float(prob),
            # Bonus: incluir datos raw útiles para el frontend
            "cape": float(future["cape"].iloc[i]),
            "lifted_index": float(future["lifted_index"].iloc[i]) if "lifted_index" in future.columns else None,
        })

    return results


# ──────────────────────────────────────────
# FALLBACK: si SARIMAX falla, usar weathercode directamente
# ──────────────────────────────────────────
def _fallback_from_weathercode(future: pd.DataFrame) -> list[dict]:
    results = []
    for ts, row in future.iterrows():
        score = weathercode_to_hail_score(int(row.get("weathercode", 0)))
        results.append({
            "time": ts.strftime("%Y-%m-%dT%H:%M"),
            "hail_probability": round(score * 100, 1),
            "cape": float(row.get("cape", 0)),
            "lifted_index": None,
        })
    return results