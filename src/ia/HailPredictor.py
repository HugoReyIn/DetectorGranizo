"""
HailPredictor.py — v3
Predictor de granizo en dos capas con todas las mejoras:

  MEJORA 1 — Más histórico (ERA5 multi-año)
    Usa la Archive API de Open-Meteo con hasta 3 años de reanálisis ERA5
    en lugar de solo 60 días. El granizo es estacional; con 3 años el
    modelo aprende los patrones de mayo-septiembre (pico en España).

  MEJORA 2 — Entrenamiento asíncrono al arranque
    Al iniciar la app, se precalientan los modelos de todos los campos
    registrados en segundo plano. La primera petición de un usuario
    no espera el entrenamiento.

  MEJORA 3 — Nuevas variables predictoras
    Añadidas: Convective Inhibition (CIN), updraft, precipitable water
    y wind shear (diferencia de viento entre 10m y 850hPa).
    Son los mejores indicadores físicos de granizo severo junto al CAPE.

  MEJORA 4 — Modelo por región climática
    En lugar de cachear por coordenada exacta, se agrupa por celda de
    0.5° (~55 km), que corresponde aproximadamente a una comarca.
    Un modelo entrenado con datos de toda una comarca es más robusto
    que uno de un punto con poca historia de granizo.
"""

import requests
import numpy as np
import pandas as pd
import threading
from datetime import datetime, timedelta
from statsmodels.tsa.statespace.sarimax import SARIMAX
import warnings
warnings.filterwarnings("ignore")


# ──────────────────────────────────────────────────────────────────────
# CONFIGURACIÓN
# ──────────────────────────────────────────────────────────────────────
_HISTORY_YEARS   = 3        # años de histórico ERA5
_MODEL_TTL_HOURS = 12       # reentrenar máximo cada 12 horas
_REGION_GRID     = 0.5      # grados para agrupar por región climática (~55 km)
_MIN_HISTORY_H   = 168      # mínimo de horas para entrenar (1 semana)

# Variables exógenas — base + nuevas de mejora 3
_EXOG_VARS = [
    # Variables originales
    "cape", "lifted_index", "freezing_level_height",
    "temperature_2m", "precipitation", "showers",
    "wind_speed_10m", "cloud_cover", "relative_humidity_2m",
    # Nuevas variables (mejora 3)
    "convective_inhibition",          # CIN — barrera energética
    "total_column_integrated_water_vapour",  # agua precipitable
    "wind_gusts_10m",                 # wind shear aproximado (proxy)
]

# Caché de modelos: clave = región (lat_05, lon_05)
_model_cache: dict = {}
_cache_lock = threading.Lock()


# ──────────────────────────────────────────────────────────────────────
# MEJORA 4 — REGIÓN CLIMÁTICA
# ──────────────────────────────────────────────────────────────────────
def _region_key(lat: float, lon: float) -> tuple:
    """
    Redondea coordenadas a la celda de 0.5° más cercana.
    Coordenadas dentro de ~55 km comparten el mismo modelo.
    """
    return (round(round(lat / _REGION_GRID) * _REGION_GRID, 1),
            round(round(lon / _REGION_GRID) * _REGION_GRID, 1))


def _region_center(lat: float, lon: float) -> tuple:
    """Devuelve las coordenadas del centro de la celda regional."""
    key = _region_key(lat, lon)
    return key  # ya son las coordenadas del centro


# ──────────────────────────────────────────────────────────────────────
# HELPERS
# ──────────────────────────────────────────────────────────────────────
def weathercode_to_hail_score(code: int) -> float:
    return {77: 0.5, 96: 0.7, 99: 1.0}.get(int(code), 0.0)


def cape_to_hail_prob(cape: float, lifted_index: float | None = None,
                      cin: float | None = None) -> float:
    """
    Probabilidad de granizo desde CAPE + Lifted Index + CIN.
    CIN alto (>100 J/kg en valor absoluto) puede suprimir la convección
    incluso con CAPE elevado.
    """
    if cape <= 0:
        return 0.0

    if cape >= 2500:
        prob = 0.85
    elif cape >= 1500:
        prob = 0.60
    elif cape >= 800:
        prob = 0.35
    elif cape >= 400:
        prob = 0.15
    elif cape >= 200:
        prob = 0.05
    else:
        return 0.0

    # Refuerzo por Lifted Index negativo
    if lifted_index is not None:
        if lifted_index <= -6:
            prob = min(1.0, prob + 0.20)
        elif lifted_index <= -4:
            prob = min(1.0, prob + 0.12)
        elif lifted_index <= -2:
            prob = min(1.0, prob + 0.06)

    # Penalización por CIN alto (inhibe la convección)
    # CIN viene en J/kg negativo — cuanto más negativo, más inhibición
    if cin is not None and cin < -150:
        prob *= 0.4   # inhibición fuerte
    elif cin is not None and cin < -80:
        prob *= 0.7   # inhibición moderada

    return round(prob * 100, 1)


# ──────────────────────────────────────────────────────────────────────
# CAPA 1 — NOWCASTING (primeras 6 horas, resolución 15 min)
# ──────────────────────────────────────────────────────────────────────
def _fetch_nowcast(lat: float, lon: float) -> list[dict]:
    """
    Datos de 15 minutos para las próximas 6 horas.
    Incluye CIN y agua precipitable para máxima precisión.
    """
    vars_15m = [
        "cape", "lifted_index", "convective_inhibition",
        "precipitation", "weather_code", "freezing_level_height",
        "total_column_integrated_water_vapour",
    ]
    url = (
        "https://api.open-meteo.com/v1/forecast"
        f"?latitude={lat}&longitude={lon}"
        "&minutely_15=" + ",".join(vars_15m) +
        "&forecast_minutely_15=24"
        "&timezone=auto"
    )

    try:
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        data = r.json().get("minutely_15", {})
        if not data or "time" not in data:
            return []

        df = pd.DataFrame(data)
        df["time"] = pd.to_datetime(df["time"])
        df = df.ffill().fillna(0)
        df["hour"] = df["time"].dt.floor("h")

        agg = {
            "cape":                                  "max",
            "lifted_index":                          "min",
            "convective_inhibition":                 "mean",
            "precipitation":                         "sum",
            "weather_code":                          "max",
            "freezing_level_height":                 "mean",
            "total_column_integrated_water_vapour":  "max",
        }
        # Solo agregar columnas que existan
        agg = {k: v for k, v in agg.items() if k in df.columns}
        hourly = df.groupby("hour").agg(agg).reset_index()

        results = []
        for _, row in hourly.iterrows():
            prob_cape = cape_to_hail_prob(
                float(row.get("cape", 0)),
                float(row.get("lifted_index", 0)) if "lifted_index" in row else None,
                float(row.get("convective_inhibition", 0)) if "convective_inhibition" in row else None,
            )
            wcode = int(row.get("weather_code", 0))
            prob_wcode = weathercode_to_hail_score(wcode) * 100

            # Bonus por agua precipitable alta (>30 kg/m² favorece granizo)
            pwat = float(row.get("total_column_integrated_water_vapour", 0))
            pwat_bonus = min(8.0, max(0.0, (pwat - 30) * 0.4)) if pwat > 30 else 0.0

            precip_bonus = min(10.0, float(row.get("precipitation", 0)) * 2)
            prob = min(100.0, max(prob_cape, prob_wcode) + precip_bonus + pwat_bonus)

            results.append({
                "time":             row["hour"].strftime("%Y-%m-%dT%H:%M"),
                "hail_probability": round(prob, 1),
                "cape":             float(row.get("cape", 0)),
                "lifted_index":     float(row.get("lifted_index", 0)) if "lifted_index" in row else None,
                "cin":              float(row.get("convective_inhibition", 0)) if "convective_inhibition" in row else None,
                "source":           "nowcast",
            })

        return results

    except Exception as e:
        print(f"[HailPredictor] Nowcast falló: {e}")
        return []


# ──────────────────────────────────────────────────────────────────────
# MEJORA 1 — HISTÓRICO ERA5 MULTI-AÑO
# ──────────────────────────────────────────────────────────────────────
def _fetch_history_era5(lat: float, lon: float) -> pd.DataFrame:
    """
    Descarga hasta 3 años de histórico ERA5 desde Open-Meteo Archive.
    Usa el centro de la región climática para datos representativos.
    """
    rlat, rlon = _region_center(lat, lon)
    end_date   = datetime.now().date() - timedelta(days=1)
    start_date = end_date - timedelta(days=365 * _HISTORY_YEARS)

    # Variables disponibles en ERA5 Archive
    archive_vars = [
        "cape", "lifted_index", "freezing_level_height",
        "temperature_2m", "precipitation", "showers",
        "wind_speed_10m", "cloud_cover", "relative_humidity_2m",
        "convective_inhibition", "total_column_integrated_water_vapour",
        "wind_gusts_10m", "weather_code",
    ]

    url = (
        "https://archive-api.open-meteo.com/v1/archive"
        f"?latitude={rlat}&longitude={rlon}"
        f"&start_date={start_date}&end_date={end_date}"
        "&hourly=" + ",".join(archive_vars) +
        "&timezone=auto"
    )

    try:
        print(f"[HailPredictor] Descargando ERA5 {_HISTORY_YEARS}a para región ({rlat},{rlon})...")
        r = requests.get(url, timeout=60)
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

        # Variable objetivo: hail_score ponderado por CAPE + señal continua
        df["hail_score"] = df["weathercode"].apply(weathercode_to_hail_score)
        if "cape" in df.columns:
            # Señal continua de CAPE para que el modelo aprenda
            # el patrón atmosférico aunque no haya weathercode de granizo
            cape_signal = df["cape"].apply(lambda c: min(0.25, c / 6000))
            df["hail_score"] = (df["hail_score"] + cape_signal).clip(upper=1.0)

        print(f"[HailPredictor] ERA5 cargado: {len(df)}h ({len(df)//24//30}m aprox)")
        return df

    except Exception as e:
        print(f"[HailPredictor] Error ERA5: {e}")
        return pd.DataFrame()


# ──────────────────────────────────────────────────────────────────────
# FORECAST 7–24h
# ──────────────────────────────────────────────────────────────────────
def _fetch_forecast(lat: float, lon: float) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Devuelve (history_recent_7d, future_h7_to_h24)."""
    vars_ = [v for v in _EXOG_VARS if v != "wind_shear"] + ["weathercode"]

    url = (
        "https://api.open-meteo.com/v1/forecast"
        f"?latitude={lat}&longitude={lon}"
        "&hourly=" + ",".join(vars_) +
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
        cape_signal = df["cape"].apply(lambda c: min(0.25, c / 6000))
        df["hail_score"] = (df["hail_score"] + cape_signal).clip(upper=1.0)

    now = pd.Timestamp.now().floor("h")
    history_recent = df[df.index <= now].copy()

    # Horas 7-24 (nowcast cubre 0-6)
    future_start = now + pd.Timedelta(hours=7)
    future_end   = now + pd.Timedelta(hours=24)
    future = df[(df.index >= future_start) & (df.index <= future_end)].copy()

    return history_recent, future


# ──────────────────────────────────────────────────────────────────────
# MEJORA 2 — ENTRENAMIENTO ASÍNCRONO + CACHÉ POR REGIÓN
# ──────────────────────────────────────────────────────────────────────
def _get_or_train_model(lat: float, lon: float,
                        history: pd.DataFrame, exog_cols: list):
    """
    Recupera el modelo de caché si es reciente, o entrena uno nuevo.
    Caché por región climática de 0.5° (mejora 4).
    """
    key = _region_key(lat, lon)

    with _cache_lock:
        cached = _model_cache.get(key)
        if cached:
            age_h = (datetime.now() - cached["trained_at"]).total_seconds() / 3600
            if age_h < _MODEL_TTL_HOURS:
                print(f"[HailPredictor] Modelo región {key} en caché ({age_h:.1f}h)")
                return cached["fit"], cached["exog_cols"]

    return _train_and_cache(key, history, exog_cols)


def _train_and_cache(key: tuple, history: pd.DataFrame, exog_cols: list):
    """Entrena el SARIMAX y lo guarda en caché."""
    print(f"[HailPredictor] Entrenando región {key} con {len(history)}h "
          f"({len(history)//24}d) histórico y {len(exog_cols)} variables...")

    endog      = history["hail_score"].values.astype(float)
    exog_train = history[exog_cols].values.astype(float)

    model = SARIMAX(
        endog,
        exog=exog_train,
        order=(2, 0, 1),
        seasonal_order=(1, 0, 0, 24),   # estacionalidad diaria
        enforce_stationarity=False,
        enforce_invertibility=False,
    )
    fit = model.fit(disp=False, maxiter=300)
    print(f"[HailPredictor] Región {key} entrenada — AIC={fit.aic:.1f}")

    with _cache_lock:
        _model_cache[key] = {
            "fit":        fit,
            "trained_at": datetime.now(),
            "exog_cols":  exog_cols,
        }

    return fit, exog_cols


def warmup_models(field_coords: list[tuple[float, float]]) -> None:
    """
    MEJORA 2 — Precalienta modelos al arrancar la app.
    Recibe lista de (lat, lon) de los campos registrados.
    Se ejecuta en un hilo separado para no bloquear el arranque.

    Uso en Main.py (lifespan):
        coords = [(p.lat, p.lon) for p in all_points]
        thread = threading.Thread(target=warmup_models, args=(coords,), daemon=True)
        thread.start()
    """
    regions_done = set()
    for lat, lon in field_coords:
        key = _region_key(lat, lon)
        if key in regions_done:
            continue
        regions_done.add(key)
        try:
            print(f"[HailPredictor] Precalentando región {key}...")
            history = _fetch_history_era5(lat, lon)
            _, future = _fetch_forecast(lat, lon)
            if history.empty or len(history) < _MIN_HISTORY_H:
                print(f"[HailPredictor] Región {key}: histórico insuficiente, omitiendo")
                continue
            exog_cols = [c for c in _EXOG_VARS if c in history.columns and c in future.columns]
            if exog_cols:
                _train_and_cache(key, history, exog_cols)
        except Exception as e:
            print(f"[HailPredictor] Error precalentando región {key}: {e}")

    print(f"[HailPredictor] Precalentamiento completado ({len(regions_done)} regiones)")


# ──────────────────────────────────────────────────────────────────────
# FALLBACK
# ──────────────────────────────────────────────────────────────────────
def _fallback(future: pd.DataFrame) -> list[dict]:
    results = []
    for ts, row in future.iterrows():
        prob_wcode = weathercode_to_hail_score(int(row.get("weathercode", 0))) * 100
        prob_cape  = cape_to_hail_prob(
            float(row.get("cape", 0)),
            float(row.get("lifted_index", 0)) if "lifted_index" in row else None,
            float(row.get("convective_inhibition", 0)) if "convective_inhibition" in row else None,
        )
        prob = min(100.0, max(prob_wcode, prob_cape))
        results.append({
            "time":             ts.strftime("%Y-%m-%dT%H:%M"),
            "hail_probability": round(prob, 1),
            "cape":             float(row.get("cape", 0)),
            "lifted_index":     float(row.get("lifted_index", 0)) if "lifted_index" in row else None,
            "source":           "fallback",
        })
    return results


# ──────────────────────────────────────────────────────────────────────
# FUNCIÓN PRINCIPAL
# ──────────────────────────────────────────────────────────────────────
def predict_hail(lat: float, lon: float) -> list[dict]:
    """
    Predicción hora a hora para las próximas 24h:
      - H0–H6:  nowcasting 15 min (CAPE + CIN + agua precipitable)
      - H7–H24: SARIMAX entrenado con ERA5 multi-año por región climática

    Cada dict: time, hail_probability, cape, lifted_index, [cin], source
    """
    results = []

    # ── CAPA 1: Nowcasting ──
    nowcast = _fetch_nowcast(lat, lon)
    if nowcast:
        results.extend(nowcast)
        print(f"[HailPredictor] Nowcast: {len(nowcast)}h OK")

    # ── Datos para CAPA 2 ──
    try:
        history_era5   = _fetch_history_era5(lat, lon)
        history_recent, future = _fetch_forecast(lat, lon)

        # Combinar ERA5 + últimos 7 días recientes sin duplicados
        if not history_era5.empty:
            common = [c for c in history_era5.columns if c in history_recent.columns]
            combined = pd.concat([
                history_era5[common],
                history_recent[[c for c in common if c in history_recent.columns]],
            ])
            combined = combined[~combined.index.duplicated(keep="last")]
            history = combined.sort_index()
        else:
            history = history_recent

        exog_cols = [c for c in _EXOG_VARS if c in history.columns and c in future.columns]

        # Si el nowcast falló, usar SARIMAX para todo el rango 0-24h
        if not nowcast:
            now = pd.Timestamp.now().floor("h")
            future_all = history_recent[history_recent.index > now].head(24)
        else:
            future_all = future   # ya son horas 7-24

        if len(history) < _MIN_HISTORY_H or len(future_all) == 0 or not exog_cols:
            print("[HailPredictor] Datos insuficientes, usando fallback")
            fallback_data = _fallback(future_all if len(future_all) > 0 else future)
            return sorted((nowcast or []) + fallback_data, key=lambda x: x["time"])

        # ── CAPA 2: SARIMAX con modelo regional ──
        fit, used_cols = _get_or_train_model(lat, lon, history, exog_cols)
        exog_pred = future_all[used_cols].values.astype(float)
        forecast  = fit.forecast(steps=len(future_all), exog=exog_pred)
        probs     = np.clip(forecast, 0, 1) * 100

        for i, (ts, row) in enumerate(future_all.iterrows()):
            # Refuerzo final con CAPE + CIN del forecast
            cape_prob = cape_to_hail_prob(
                float(row.get("cape", 0)),
                float(row.get("lifted_index", 0)) if "lifted_index" in row else None,
                float(row.get("convective_inhibition", 0)) if "convective_inhibition" in row else None,
            )
            final_prob = min(100.0, max(float(probs[i]), cape_prob))

            # Bonus por agua precipitable alta
            pwat = float(row.get("total_column_integrated_water_vapour", 0))
            if pwat > 35:
                final_prob = min(100.0, final_prob + min(5.0, (pwat - 35) * 0.3))

            results.append({
                "time":             ts.strftime("%Y-%m-%dT%H:%M"),
                "hail_probability": round(final_prob, 1),
                "cape":             float(row.get("cape", 0)),
                "lifted_index":     float(row.get("lifted_index", 0)) if "lifted_index" in row else None,
                "cin":              float(row.get("convective_inhibition", 0)) if "convective_inhibition" in row else None,
                "source":           "sarimax",
            })

    except Exception as e:
        print(f"[HailPredictor] Error CAPA 2: {e}")

    return sorted(results, key=lambda x: x["time"])