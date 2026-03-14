import requests
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from statsmodels.tsa.statespace.sarimax import SARIMAX
import warnings
warnings.filterwarnings("ignore")


# ──────────────────────────────────────────
# WEATHERCODE → HAIL SCORE (variable objetivo)
# 0   = sin granizo
# 0.5 = granizo fino (código 77)
# 0.7 = tormenta con granizo leve (96)
# 1.0 = tormenta con granizo fuerte (99)
# ──────────────────────────────────────────
def weathercode_to_hail_score(code: int) -> float:
    return {77: 0.5, 96: 0.7, 99: 1.0}.get(int(code), 0.0)


def cape_bonus(cape: float) -> float:
    """
    Bonus al hail_score basado en CAPE (J/kg).
    CAPE > 1500 → +0.3 (condición severa)
    CAPE > 800  → +0.15 (condición moderada)
    CAPE > 400  → +0.05 (condición leve)
    Se aplica solo si ya hay alguna señal convectiva (score > 0).
    """
    if cape >= 1500:
        return 0.30
    if cape >= 800:
        return 0.15
    if cape >= 400:
        return 0.05
    return 0.0


# ──────────────────────────────────────────
# HISTÓRICO VERIFICADO (Open-Meteo Archive API)
# Descarga hasta 60 días de datos reales
# ──────────────────────────────────────────
def fetch_historical_data(lat: float, lon: float) -> pd.DataFrame:
    end_date = datetime.now().date() - timedelta(days=1)
    start_date = end_date - timedelta(days=59)

    VARS = [
        "cape", "lifted_index", "freezing_level_height",
        "temperature_2m", "precipitation", "showers",
        "wind_speed_10m", "cloud_cover", "relative_humidity_2m",
        "weather_code",
    ]

    url = (
        "https://archive-api.open-meteo.com/v1/archive"
        f"?latitude={lat}&longitude={lon}"
        f"&start_date={start_date}&end_date={end_date}"
        "&hourly=" + ",".join(VARS) +
        "&timezone=auto"
    )

    try:
        r = requests.get(url, timeout=20)
        r.raise_for_status()
        data = r.json().get("hourly", {})
        if not data or "time" not in data:
            return pd.DataFrame()

        df = pd.DataFrame(data)
        df["time"] = pd.to_datetime(df["time"])
        df = df.set_index("time")
        if "weather_code" in df.columns:
            df.rename(columns={"weather_code": "weathercode"}, inplace=True)
        df = df.ffill().fillna(0)
        df["hail_score"] = df["weathercode"].apply(weathercode_to_hail_score)
        # Refuerzo con CAPE: solo aumenta score si ya hay señal convectiva
        if "cape" in df.columns:
            df["hail_score"] = df.apply(
                lambda row: min(1.0, row["hail_score"] + cape_bonus(row["cape"]))
                if row["hail_score"] > 0 else row["hail_score"],
                axis=1
            )
        return df

    except Exception as e:
        print(f"[HailPredictor] Error histórico archivo: {e}")
        return pd.DataFrame()


# ──────────────────────────────────────────
# FORECAST + ÚLTIMOS 7 DÍAS (Open-Meteo)
# ──────────────────────────────────────────
def fetch_recent_and_forecast(lat: float, lon: float) -> tuple[pd.DataFrame, pd.DataFrame]:
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
        "&past_days=7&forecast_days=2"
        "&timezone=auto&models=icon_eu"
    )

    r = requests.get(url, timeout=15)
    r.raise_for_status()
    data = r.json().get("hourly", {})

    df = pd.DataFrame(data)
    df["time"] = pd.to_datetime(df["time"])
    df = df.set_index("time")
    df = df.ffill().fillna(0)
    df["hail_score"] = df["weathercode"].apply(weathercode_to_hail_score)
    if "cape" in df.columns:
        df["hail_score"] = df.apply(
            lambda row: min(1.0, row["hail_score"] + cape_bonus(row["cape"]))
            if row["hail_score"] > 0 else row["hail_score"],
            axis=1
        )

    now = pd.Timestamp.now().floor("h")
    history_recent = df[df.index <= now].copy()
    future = df[df.index > now].head(24).copy()

    return history_recent, future


# ──────────────────────────────────────────
# COMBINAR DATOS Y PREDECIR
# ──────────────────────────────────────────
def fetch_meteo_data(lat: float, lon: float) -> dict:
    exog_cols = [
        "cape", "lifted_index", "freezing_level_height",
        "temperature_2m", "precipitation", "showers",
        "wind_speed_10m", "cloud_cover", "relative_humidity_2m",
    ]

    # Datos históricos verificados (60 días)
    history_archive = fetch_historical_data(lat, lon)

    # Datos recientes + forecast
    history_recent, future = fetch_recent_and_forecast(lat, lon)

    # Combinar: archivo (60d) + últimos 7 días, sin duplicados
    if not history_archive.empty:
        common_cols = [c for c in history_archive.columns if c in history_recent.columns]
        combined = pd.concat([
            history_archive[common_cols],
            history_recent[[c for c in common_cols if c in history_recent.columns]]
        ])
        combined = combined[~combined.index.duplicated(keep="last")]
        history = combined.sort_index()
    else:
        history = history_recent

    print(f"[HailPredictor] Histórico total: {len(history)}h ({len(history)//24}d) | Forecast: {len(future)}h")

    # Filtrar exog_cols disponibles
    exog_cols = [c for c in exog_cols if c in history.columns and c in future.columns]

    return {"history": history, "future": future, "exog_cols": exog_cols}


# ──────────────────────────────────────────
# PREDICT (SARIMAX)
# ──────────────────────────────────────────
def predict_hail(lat: float, lon: float) -> list[dict]:
    meteo = fetch_meteo_data(lat, lon)
    history  = meteo["history"]
    future   = meteo["future"]
    exog_cols = meteo["exog_cols"]

    if len(history) < 48 or len(future) == 0:
        print("[HailPredictor] Datos insuficientes, usando fallback.")
        return _fallback_from_weathercode(future)

    endog      = history["hail_score"].values.astype(float)
    exog_train = history[exog_cols].values.astype(float)
    exog_pred  = future[exog_cols].values.astype(float)

    try:
        model = SARIMAX(
            endog,
            exog=exog_train,
            order=(1, 0, 1),
            seasonal_order=(0, 0, 0, 0),
            enforce_stationarity=False,
            enforce_invertibility=False,
        )
        fit = model.fit(disp=False, maxiter=200)
        forecast = fit.forecast(steps=len(future), exog=exog_pred)

        probabilities = np.clip(forecast, 0, 1) * 100
        probabilities = probabilities.round(1)

        print(f"[HailPredictor] OK — AIC={fit.aic:.1f}")

    except Exception as e:
        print(f"[HailPredictor] SARIMAX falló ({e}), fallback.")
        return _fallback_from_weathercode(future)

    results = []
    for i, (ts, prob) in enumerate(zip(future.index, probabilities)):
        results.append({
            "time": ts.strftime("%Y-%m-%dT%H:%M"),
            "hail_probability": float(prob),
            "cape": float(future["cape"].iloc[i]) if "cape" in future.columns else 0,
            "lifted_index": float(future["lifted_index"].iloc[i]) if "lifted_index" in future.columns else None,
        })

    return results


# ──────────────────────────────────────────
# FALLBACK
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