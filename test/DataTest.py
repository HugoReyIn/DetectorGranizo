"""
DataTest.py
Datos sintéticos de prueba para el predictor de granizo.

Escenarios incluidos:
  - Alto riesgo (AR-*): CAPE alto, LI negativo, weathercodes 96/99 → granizo real
  - Riesgo moderado (RM-*): zona gris — CAPE medio o CIN fuerte
  - Bajo riesgo (BR-*): sin convección → no granizó

Cada escenario tiene la etiqueta ground truth (granizo_real) para
calcular Accuracy, Recall y F1-Score.
"""

from datetime import datetime, timedelta

BASE_TIME = datetime(2024, 6, 15, 14, 0)   # hora pico convectiva (14h)

ESCENARIOS = [

    # ── ALTO RIESGO — debe predecir granizo ──────────────────────────

    {
        "id": "AR-01",
        "descripcion": "Tormenta severa — CAPE extremo, LI muy negativo, wcode 99",
        "hora": BASE_TIME.isoformat(),
        "variables": {
            "cape": 3200.0,
            "lifted_index": -8.0,
            "convective_inhibition": 10.0,       # CIN bajo → disparo fácil
            "freezing_level_height": 3200.0,
            "temperature_2m": 28.0,
            "precipitation": 18.5,
            "showers": 12.0,
            "wind_speed_10m": 45.0,
            "wind_gusts_10m": 75.0,
            "cloud_cover": 95.0,
            "relative_humidity_2m": 88.0,
            "weathercode": 99,
        },
        "granizo_real": True,
    },

    {
        "id": "AR-02",
        "descripcion": "Tormenta con granizo leve — CAPE alto, wcode 96",
        "hora": (BASE_TIME + timedelta(hours=1)).isoformat(),
        "variables": {
            "cape": 1800.0,
            "lifted_index": -5.5,
            "convective_inhibition": 20.0,
            "freezing_level_height": 3500.0,
            "temperature_2m": 26.0,
            "precipitation": 10.2,
            "showers": 8.0,
            "wind_speed_10m": 32.0,
            "wind_gusts_10m": 58.0,
            "cloud_cover": 90.0,
            "relative_humidity_2m": 82.0,
            "weathercode": 96,
        },
        "granizo_real": True,
    },

    {
        "id": "AR-03",
        "descripcion": "Granizo fino — convección moderada, nivel congelación bajo, wcode 77",
        "hora": (BASE_TIME + timedelta(hours=2)).isoformat(),
        "variables": {
            "cape": 950.0,
            "lifted_index": -3.5,
            "convective_inhibition": 35.0,
            "freezing_level_height": 2800.0,     # nivel bajo → granizo más probable
            "temperature_2m": 22.0,
            "precipitation": 4.5,
            "showers": 3.0,
            "wind_speed_10m": 20.0,
            "wind_gusts_10m": 38.0,
            "cloud_cover": 80.0,
            "relative_humidity_2m": 78.0,
            "weathercode": 77,
        },
        "granizo_real": True,
    },

    {
        "id": "AR-04",
        "descripcion": "CAPE muy alto sin wcode de granizo aún — riesgo inminente",
        "hora": (BASE_TIME + timedelta(hours=3)).isoformat(),
        "variables": {
            "cape": 2600.0,
            "lifted_index": -7.0,
            "convective_inhibition": 5.0,        # CIN casi nulo
            "freezing_level_height": 3100.0,
            "temperature_2m": 30.0,
            "precipitation": 2.0,
            "showers": 1.5,
            "wind_speed_10m": 28.0,
            "wind_gusts_10m": 55.0,
            "cloud_cover": 70.0,
            "relative_humidity_2m": 75.0,
            "weathercode": 95,                   # tormenta sin código granizo
        },
        "granizo_real": True,
    },

    # ── RIESGO MODERADO — zona gris ───────────────────────────────────

    {
        "id": "RM-01",
        "descripcion": "CAPE moderado, chubascos — riesgo real pero no granizó",
        "hora": (BASE_TIME + timedelta(hours=4)).isoformat(),
        "variables": {
            "cape": 620.0,
            "lifted_index": -2.0,
            "convective_inhibition": 55.0,
            "freezing_level_height": 3800.0,
            "temperature_2m": 24.0,
            "precipitation": 3.2,
            "showers": 2.0,
            "wind_speed_10m": 18.0,
            "wind_gusts_10m": 30.0,
            "cloud_cover": 65.0,
            "relative_humidity_2m": 70.0,
            "weathercode": 81,
        },
        "granizo_real": False,
    },

    {
        "id": "RM-02",
        "descripcion": "CAPE alto pero CIN fuerte — convección inhibida, no granizó",
        "hora": (BASE_TIME + timedelta(hours=5)).isoformat(),
        "variables": {
            "cape": 1500.0,
            "lifted_index": -4.0,
            "convective_inhibition": 180.0,      # CIN fuerte → inhibe tormenta
            "freezing_level_height": 4000.0,
            "temperature_2m": 27.0,
            "precipitation": 0.5,
            "showers": 0.2,
            "wind_speed_10m": 12.0,
            "wind_gusts_10m": 22.0,
            "cloud_cover": 50.0,
            "relative_humidity_2m": 60.0,
            "weathercode": 3,
        },
        "granizo_real": False,
    },

    # ── BAJO RIESGO — no debe predecir granizo ────────────────────────

    {
        "id": "BR-01",
        "descripcion": "Día soleado de verano — sin convección, LI positivo",
        "hora": (BASE_TIME + timedelta(hours=6)).isoformat(),
        "variables": {
            "cape": 0.0,
            "lifted_index": 2.0,
            "convective_inhibition": 0.0,
            "freezing_level_height": 4500.0,
            "temperature_2m": 32.0,
            "precipitation": 0.0,
            "showers": 0.0,
            "wind_speed_10m": 8.0,
            "wind_gusts_10m": 14.0,
            "cloud_cover": 10.0,
            "relative_humidity_2m": 35.0,
            "weathercode": 0,
        },
        "granizo_real": False,
    },

    {
        "id": "BR-02",
        "descripcion": "Lluvia estratiforme de otoño — sin convección",
        "hora": (BASE_TIME + timedelta(hours=7)).isoformat(),
        "variables": {
            "cape": 50.0,
            "lifted_index": 1.5,
            "convective_inhibition": 0.0,
            "freezing_level_height": 5000.0,
            "temperature_2m": 14.0,
            "precipitation": 2.8,
            "showers": 0.0,
            "wind_speed_10m": 15.0,
            "wind_gusts_10m": 25.0,
            "cloud_cover": 95.0,
            "relative_humidity_2m": 92.0,
            "weathercode": 63,
        },
        "granizo_real": False,
    },

    {
        "id": "BR-03",
        "descripcion": "Noche de invierno despejada — imposible granizo convectivo",
        "hora": (BASE_TIME + timedelta(hours=8)).isoformat(),
        "variables": {
            "cape": 0.0,
            "lifted_index": 5.0,
            "convective_inhibition": 0.0,
            "freezing_level_height": 6000.0,
            "temperature_2m": 4.0,
            "precipitation": 0.0,
            "showers": 0.0,
            "wind_speed_10m": 5.0,
            "wind_gusts_10m": 9.0,
            "cloud_cover": 5.0,
            "relative_humidity_2m": 50.0,
            "weathercode": 0,
        },
        "granizo_real": False,
    },

    {
        "id": "BR-04",
        "descripcion": "Nevada — precipitación sólida pero no granizo convectivo",
        "hora": (BASE_TIME + timedelta(hours=9)).isoformat(),
        "variables": {
            "cape": 10.0,
            "lifted_index": 3.0,
            "convective_inhibition": 0.0,
            "freezing_level_height": 800.0,
            "temperature_2m": -2.0,
            "precipitation": 5.0,
            "showers": 0.0,
            "wind_speed_10m": 20.0,
            "wind_gusts_10m": 35.0,
            "cloud_cover": 100.0,
            "relative_humidity_2m": 95.0,
            "weathercode": 75,
        },
        "granizo_real": False,
    },
]

# Umbral de clasificación — mismo que el sistema real
UMBRAL_GRANIZO = 35.0

# Variables exógenas en el mismo orden que HailPredictor
EXOG_VARS = [
    "cape", "lifted_index", "convective_inhibition", "freezing_level_height",
    "temperature_2m", "precipitation", "showers",
    "wind_speed_10m", "wind_gusts_10m", "cloud_cover", "relative_humidity_2m",
]