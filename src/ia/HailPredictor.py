import os
import requests
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from statsmodels.tsa.statespace.sarimax import SARIMAX
import warnings
warnings.filterwarnings("ignore")

# ──────────────────────────────────────────
# CONFIGURACIÓN
# ──────────────────────────────────────────
HISTORICAL_YEARS = 2          # años hacia atrás que se descargan
CHUNK_MONTHS     = 6          # tamaño de cada petición al archivo
CACHE_DIR        = ".hail_cache"   # carpeta local para caché en disco
CACHE_TTL_HOURS  = 24         # horas antes de refrescar el archivo histórico


# ──────────────────────────────────────────
# WEATHERCODE → HAIL SCORE (variable objetivo)
# 0   = sin granizo
# 0.5 = granizo fino (código 77)
# 0.7 = tormenta con granizo leve (96)
# 1.0 = tormenta con granizo fuerte (99)
# ──────────────────────────────────────────
def weathercode_to_hail_score(code: int) -> float:
    return {77: 0.5, 96: 0.7, 99: 1.0}.get(int(code), 0.0)


def compute_hail_score(weathercode: int, cape: float, lifted_index: float,
                       cin: float = 0.0) -> float:
    """
    Construye el hail_score combinando tres fuentes independientes:

    1. Weathercode verificado (fuente más fiable, pero incompleta)
    2. CAPE independiente — permite detectar eventos que Open-Meteo
       no codifica como granizo pero tienen condiciones severas reales
    3. Lifted Index negativo — refuerza la señal convectiva

    La CIN actúa como moderador: si hay mucha inhibición, reduce el score
    aunque el CAPE sea alto (la energía está "tapada").

    El resultado se recorta a [0, 1].
    """
    score = weathercode_to_hail_score(weathercode)

    # ── Contribución CAPE — independiente del weathercode ──
    # A diferencia del cape_bonus anterior, aquí el CAPE puede subir el score
    # incluso cuando weathercode = 0 (Open-Meteo no detectó granizo pero
    # las condiciones físicas lo indican).
    if cape >= 2000:
        cape_contrib = 0.50
    elif cape >= 1500:
        cape_contrib = 0.35
    elif cape >= 1000:
        cape_contrib = 0.20
    elif cape >= 600:
        cape_contrib = 0.10
    elif cape >= 300:
        cape_contrib = 0.04
    else:
        cape_contrib = 0.0

    # ── Contribución Lifted Index ──
    # LI < 0 = atmósfera inestable. Cuanto más negativo, más inestable.
    if lifted_index <= -6:
        li_contrib = 0.20
    elif lifted_index <= -4:
        li_contrib = 0.12
    elif lifted_index <= -2:
        li_contrib = 0.06
    elif lifted_index <= 0:
        li_contrib = 0.02
    else:
        li_contrib = 0.0

    # ── Moderador CIN ──
    # CIN > 100 J/kg: la "tapa" es fuerte, reduce contribuciones físicas
    # CIN > 200 J/kg: la "tapa" es muy fuerte, casi anula la señal convectiva
    if cin >= 200:
        cin_factor = 0.10
    elif cin >= 100:
        cin_factor = 0.40
    elif cin >= 50:
        cin_factor = 0.75
    else:
        cin_factor = 1.0

    # El weathercode ya verificado no se modera por CIN (es observación real)
    score += (cape_contrib + li_contrib) * cin_factor

    return min(1.0, score)


# ──────────────────────────────────────────
# CACHÉ EN DISCO
# Guarda cada chunk como Parquet para evitar
# repetir descargas en cada llamada al predictor.
# ──────────────────────────────────────────
def _cache_path(lat: float, lon: float) -> str:
    os.makedirs(CACHE_DIR, exist_ok=True)
    key = f"{round(lat, 2)}_{round(lon, 2)}".replace("-", "n")
    return os.path.join(CACHE_DIR, f"hail_{key}.parquet")


def _cache_is_fresh(path: str) -> bool:
    """Devuelve True si el archivo existe y fue escrito hace menos de CACHE_TTL_HOURS."""
    if not os.path.exists(path):
        return False
    age = datetime.now() - datetime.fromtimestamp(os.path.getmtime(path))
    return age.total_seconds() < CACHE_TTL_HOURS * 3600


def _load_cache(path: str) -> pd.DataFrame:
    try:
        return pd.read_parquet(path)
    except Exception as e:
        print(f"[HailPredictor] Caché corrupta, regenerando: {e}")
        return pd.DataFrame()


def _save_cache(path: str, df: pd.DataFrame) -> None:
    try:
        df.to_parquet(path)
    except Exception as e:
        print(f"[HailPredictor] No se pudo guardar caché: {e}")


# ──────────────────────────────────────────
# DESCARGA DE UN CHUNK DEL ARCHIVO
# ──────────────────────────────────────────
ARCHIVE_VARS = [
    # Inestabilidad convectiva — los más importantes para granizo
    "cape", "lifted_index", "convective_inhibition", "freezing_level_height",
    # Termodinámica
    "temperature_2m", "dew_point_2m", "relative_humidity_2m",
    # Presión y viento
    "surface_pressure", "wind_speed_10m", "wind_gusts_10m",
    # Precipitación
    "precipitation", "showers", "cloud_cover",
    # Código de tiempo verificado
    "weather_code",
]

def _fetch_archive_chunk(lat: float, lon: float,
                          start: str, end: str) -> pd.DataFrame:
    """Descarga un tramo del archivo Open-Meteo y devuelve un DataFrame procesado."""
    url = (
        "https://archive-api.open-meteo.com/v1/archive"
        f"?latitude={lat}&longitude={lon}"
        f"&start_date={start}&end_date={end}"
        "&hourly=" + ",".join(ARCHIVE_VARS) +
        "&timezone=auto"
    )
    try:
        r = requests.get(url, timeout=30)
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

        # hail_score con la nueva función que combina weathercode + CAPE + LI + CIN
        df["hail_score"] = df.apply(
            lambda row: compute_hail_score(
                weathercode  = int(row.get("weathercode", 0)),
                cape         = float(row.get("cape", 0)),
                lifted_index = float(row.get("lifted_index", 0)),
                cin          = float(row.get("convective_inhibition", 0)),
            ),
            axis=1,
        )

        # Feature de hora del día: el granizo es más probable entre las 14-19h.
        # Se codifica como seno/coseno para que el SARIMAX capture la periodicidad.
        hour = df.index.hour
        df["hour_sin"] = np.sin(2 * np.pi * hour / 24)
        df["hour_cos"] = np.cos(2 * np.pi * hour / 24)

        return df

    except Exception as e:
        print(f"[HailPredictor] Error chunk {start}→{end}: {e}")
        return pd.DataFrame()


# ──────────────────────────────────────────
# HISTÓRICO VERIFICADO — 2 AÑOS EN CHUNKS
# ──────────────────────────────────────────
def fetch_historical_data(lat: float, lon: float) -> pd.DataFrame:
    """
    Descarga hasta HISTORICAL_YEARS años de datos del archivo Open-Meteo.
    Las descargas se dividen en tramos de CHUNK_MONTHS meses para evitar
    timeouts. El resultado se guarda en disco (Parquet) y se reutiliza
    durante CACHE_TTL_HOURS horas.
    """
    cache_file = _cache_path(lat, lon)

    if _cache_is_fresh(cache_file):
        df = _load_cache(cache_file)
        if not df.empty:
            print(f"[HailPredictor] Caché OK — {len(df)}h ({len(df)//24}d) desde disco")
            return df

    end_date   = datetime.now().date() - timedelta(days=1)
    start_date = end_date - relativedelta(years=HISTORICAL_YEARS)

    # Generar lista de tramos
    chunks = []
    cursor = start_date
    while cursor < end_date:
        chunk_end = min(cursor + relativedelta(months=CHUNK_MONTHS) - timedelta(days=1),
                        end_date)
        chunks.append((str(cursor), str(chunk_end)))
        cursor += relativedelta(months=CHUNK_MONTHS)

    print(f"[HailPredictor] Descargando {len(chunks)} chunks "
          f"({start_date} → {end_date})…")

    frames = []
    for i, (s, e) in enumerate(chunks, 1):
        print(f"[HailPredictor]   chunk {i}/{len(chunks)}: {s} → {e}")
        chunk_df = _fetch_archive_chunk(lat, lon, s, e)
        if not chunk_df.empty:
            frames.append(chunk_df)

    if not frames:
        print("[HailPredictor] Sin datos históricos.")
        return pd.DataFrame()

    df = pd.concat(frames)
    df = df[~df.index.duplicated(keep="last")].sort_index()
    _save_cache(cache_file, df)
    print(f"[HailPredictor] Histórico total: {len(df)}h ({len(df)//24}d) — guardado en caché")
    return df


# ──────────────────────────────────────────
# FORECAST + ÚLTIMOS 7 DÍAS (Open-Meteo)
# ──────────────────────────────────────────
def fetch_recent_and_forecast(lat: float, lon: float) -> tuple[pd.DataFrame, pd.DataFrame]:
    VARS = [
        # Inestabilidad convectiva
        "cape", "lifted_index", "convective_inhibition", "freezing_level_height",
        # Termodinámica
        "temperature_2m", "dew_point_2m", "relative_humidity_2m",
        # Presión y viento
        "surface_pressure", "wind_speed_10m", "wind_gusts_10m",
        # Precipitación
        "precipitation", "showers", "precipitation_probability", "cloud_cover",
        # Código de tiempo
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

    df["hail_score"] = df.apply(
        lambda row: compute_hail_score(
            weathercode  = int(row.get("weathercode", 0)),
            cape         = float(row.get("cape", 0)),
            lifted_index = float(row.get("lifted_index", 0)),
            cin          = float(row.get("convective_inhibition", 0)),
        ),
        axis=1,
    )

    hour = df.index.hour
    df["hour_sin"] = np.sin(2 * np.pi * hour / 24)
    df["hour_cos"] = np.cos(2 * np.pi * hour / 24)

    now = pd.Timestamp.now().floor("h")
    history_recent = df[df.index <= now].copy()
    future = df[df.index > now].head(24).copy()

    return history_recent, future


# ──────────────────────────────────────────
# COMBINAR DATOS Y PREDECIR
# ──────────────────────────────────────────
def fetch_meteo_data(lat: float, lon: float) -> dict:
    exog_cols = [
        # Inestabilidad — máximo peso predictivo
        "cape", "lifted_index", "convective_inhibition", "freezing_level_height",
        # Termodinámica
        "temperature_2m", "dew_point_2m", "relative_humidity_2m",
        # Presión y viento
        "surface_pressure", "wind_speed_10m", "wind_gusts_10m",
        # Precipitación
        "precipitation", "showers", "precipitation_probability", "cloud_cover",
        # Ciclo diario — el granizo ocurre principalmente entre las 14-19h
        "hour_sin", "hour_cos",
    ]

    # Datos históricos verificados (2 años, con caché en disco)
    history_archive = fetch_historical_data(lat, lon)

    # Datos recientes + forecast
    history_recent, future = fetch_recent_and_forecast(lat, lon)

    # Combinar: archivo (2 años) + últimos 7 días, sin duplicados
    if not history_archive.empty:
        common_cols = [c for c in history_archive.columns if c in history_recent.columns]
        combined = pd.concat([
            history_archive[common_cols],
            history_recent[[c for c in common_cols if c in history_recent.columns]],
        ])
        combined = combined[~combined.index.duplicated(keep="last")]
        history = combined.sort_index()
    else:
        history = history_recent

    print(f"[HailPredictor] Series para SARIMAX: {len(history)}h ({len(history)//24}d) | "
          f"Forecast: {len(future)}h")

    # Filtrar exog_cols disponibles en ambos dataframes
    exog_cols = [c for c in exog_cols if c in history.columns and c in future.columns]

    return {"history": history, "future": future, "exog_cols": exog_cols}


# ──────────────────────────────────────────
# PREDICT (SARIMAX)
# Con 2 años de datos se añade componente estacional anual (s=8760h).
# Para series largas se usa un subconjunto de los últimos 6 meses
# para el ajuste del modelo, preservando el contexto estacional.
# ──────────────────────────────────────────
def predict_hail(lat: float, lon: float) -> list[dict]:
    meteo    = fetch_meteo_data(lat, lon)
    history  = meteo["history"]
    future   = meteo["future"]
    exog_cols = meteo["exog_cols"]

    if len(history) < 48 or len(future) == 0:
        print("[HailPredictor] Datos insuficientes, usando fallback.")
        return _fallback_from_weathercode(future)

    # Añadir ciclo diario al future si no viene ya calculado
    if "hour_sin" not in future.columns:
        future = future.copy()
        future["hour_sin"] = np.sin(2 * np.pi * future.index.hour / 24)
        future["hour_cos"] = np.cos(2 * np.pi * future.index.hour / 24)

    # Para el ajuste SARIMAX usamos los últimos 6 meses (4380h) como máximo.
    MAX_FIT_HOURS = 24 * 180
    fit_history = history.iloc[-MAX_FIT_HOURS:] if len(history) > MAX_FIT_HOURS else history

    n_eventos = int((fit_history["hail_score"] > 0).sum())
    score_medio = float(fit_history["hail_score"].mean())

    endog      = fit_history["hail_score"].values.astype(float)
    exog_train = fit_history[exog_cols].values.astype(float)
    exog_pred  = future[exog_cols].values.astype(float)

    # Componente estacional diaria (s=24) si hay eventos de granizo detectados.
    # Con señal enriquecida por CAPE+LI ahora hay muchos más puntos > 0.
    has_hail_signal = n_eventos >= 5

    try:
        model = SARIMAX(
            endog,
            exog=exog_train,
            order=(2, 0, 1),
            seasonal_order=(1, 0, 1, 24) if has_hail_signal else (0, 0, 0, 0),
            enforce_stationarity=False,
            enforce_invertibility=False,
        )
        fit = model.fit(disp=False, maxiter=300)
        forecast = fit.forecast(steps=len(future), exog=exog_pred)

        probabilities = np.clip(forecast, 0, 1) * 100
        probabilities = probabilities.round(1)

        print(
            f"[HailPredictor] OK — AIC={fit.aic:.1f} | "
            f"Horas con señal: {n_eventos} | "
            f"Score medio: {score_medio:.4f} | "
            f"Estacional: {'sí (s=24)' if has_hail_signal else 'no'}"
        )

    except Exception as e:
        print(f"[HailPredictor] SARIMAX falló ({e}), fallback.")
        return _fallback_from_weathercode(future)

    results = []
    for i, (ts, prob) in enumerate(zip(future.index, probabilities)):
        results.append({
            "time":               ts.strftime("%Y-%m-%dT%H:%M"),
            "hail_probability":   float(prob),
            "cape":               float(future["cape"].iloc[i])               if "cape"               in future.columns else 0,
            "lifted_index":       float(future["lifted_index"].iloc[i])       if "lifted_index"       in future.columns else None,
            "cin":                float(future["convective_inhibition"].iloc[i]) if "convective_inhibition" in future.columns else None,
            "surface_pressure":   float(future["surface_pressure"].iloc[i])   if "surface_pressure"   in future.columns else None,
            "dew_point":          float(future["dew_point_2m"].iloc[i])       if "dew_point_2m"       in future.columns else None,
            "wind_gusts":         float(future["wind_gusts_10m"].iloc[i])     if "wind_gusts_10m"     in future.columns else None,
            "precip_probability": float(future["precipitation_probability"].iloc[i]) if "precipitation_probability" in future.columns else None,
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
            "time":             ts.strftime("%Y-%m-%dT%H:%M"),
            "hail_probability": round(score * 100, 1),
            "cape":             float(row.get("cape", 0)),
            "lifted_index":     None,
        })
    return results