"""
test_data.py
Datos sintéticos de prueba para el predictor de granizo.

Cada escenario representa una hora meteorológica con sus variables
y la etiqueta real (granizo_real=True/False) para calcular las métricas.

Escenarios incluidos:
  - Condiciones de alto riesgo (CAPE alto, LI negativo, codes 96/99)
  - Condiciones de riesgo moderado (CAPE medio, chubascos)
  - Condiciones de bajo riesgo (cielo despejado, sin convección)
  - Casos límite (CAPE alto pero CIN fuerte → convección inhibida)
"""

from datetime import datetime, timedelta

# ──────────────────────────────────────────────────────────────────────
# ESTRUCTURA DE CADA CASO:
# {
#   "id":            identificador del escenario
#   "descripcion":   descripción legible
#   "hora":          timestamp ISO
#   "variables":     dict con las variables meteorológicas de entrada
#   "granizo_real":  True si granizó realmente (etiqueta ground truth)
# }
# ──────────────────────────────────────────────────────────────────────

BASE_TIME = datetime(2024, 6, 15, 12, 0)   # tarde de verano (pico convectivo)

ESCENARIOS = [

    # ── ALTO RIESGO — debe predecir granizo ──────────────────────────

    {
        "id": "AR-01",
        "descripcion": "Tormenta severa con granizo grande — CAPE extremo, LI muy negativo",
        "hora": BASE_TIME.isoformat(),
        "variables": {
            "cape": 3200.0,
            "lifted_index": -8.0,
            "convective_inhibition": -10.0,      # CIN bajo: fácil disparo
            "freezing_level_height": 3200.0,
            "temperature_2m": 28.0,
            "precipitation": 18.5,
            "showers": 12.0,
            "wind_speed_10m": 45.0,
            "wind_gusts_10m": 75.0,
            "cloud_cover": 95.0,
            "relative_humidity_2m": 88.0,
            "total_column_integrated_water_vapour": 42.0,
            "weathercode": 99,                   # tormenta con granizo fuerte
        },
        "granizo_real": True,
    },

    {
        "id": "AR-02",
        "descripcion": "Tormenta con granizo leve — CAPE alto, chubascos intensos",
        "hora": (BASE_TIME + timedelta(hours=1)).isoformat(),
        "variables": {
            "cape": 1800.0,
            "lifted_index": -5.5,
            "convective_inhibition": -20.0,
            "freezing_level_height": 3500.0,
            "temperature_2m": 26.0,
            "precipitation": 10.2,
            "showers": 8.0,
            "wind_speed_10m": 32.0,
            "wind_gusts_10m": 58.0,
            "cloud_cover": 90.0,
            "relative_humidity_2m": 82.0,
            "total_column_integrated_water_vapour": 38.0,
            "weathercode": 96,                   # tormenta con granizo ligero
        },
        "granizo_real": True,
    },

    {
        "id": "AR-03",
        "descripcion": "Granizo fino — convección moderada, nivel de congelación bajo",
        "hora": (BASE_TIME + timedelta(hours=2)).isoformat(),
        "variables": {
            "cape": 950.0,
            "lifted_index": -3.5,
            "convective_inhibition": -35.0,
            "freezing_level_height": 2800.0,     # nivel bajo → granizo más probable
            "temperature_2m": 22.0,
            "precipitation": 4.5,
            "showers": 3.0,
            "wind_speed_10m": 20.0,
            "wind_gusts_10m": 38.0,
            "cloud_cover": 80.0,
            "relative_humidity_2m": 78.0,
            "total_column_integrated_water_vapour": 32.0,
            "weathercode": 77,                   # granizo fino
        },
        "granizo_real": True,
    },

    {
        "id": "AR-04",
        "descripcion": "CAPE muy alto, ambiente húmedo — alto riesgo aunque sin code de granizo aún",
        "hora": (BASE_TIME + timedelta(hours=3)).isoformat(),
        "variables": {
            "cape": 2600.0,
            "lifted_index": -7.0,
            "convective_inhibition": -5.0,
            "freezing_level_height": 3100.0,
            "temperature_2m": 30.0,
            "precipitation": 2.0,
            "showers": 1.5,
            "wind_speed_10m": 28.0,
            "wind_gusts_10m": 55.0,
            "cloud_cover": 70.0,
            "relative_humidity_2m": 75.0,
            "total_column_integrated_water_vapour": 45.0,
            "weathercode": 95,                   # tormenta (sin granizo aún en código)
        },
        "granizo_real": True,
    },

    # ── RIESGO MODERADO — puede predecir granizo (zona gris) ─────────

    {
        "id": "RM-01",
        "descripcion": "CAPE moderado, chubascos — riesgo real pero bajo",
        "hora": (BASE_TIME + timedelta(hours=4)).isoformat(),
        "variables": {
            "cape": 620.0,
            "lifted_index": -2.0,
            "convective_inhibition": -55.0,
            "freezing_level_height": 3800.0,
            "temperature_2m": 24.0,
            "precipitation": 3.2,
            "showers": 2.0,
            "wind_speed_10m": 18.0,
            "wind_gusts_10m": 30.0,
            "cloud_cover": 65.0,
            "relative_humidity_2m": 70.0,
            "total_column_integrated_water_vapour": 28.0,
            "weathercode": 81,                   # chubascos moderados
        },
        "granizo_real": False,                   # no granizó finalmente
    },

    {
        "id": "RM-02",
        "descripcion": "CAPE alto pero CIN fuerte — convección inhibida",
        "hora": (BASE_TIME + timedelta(hours=5)).isoformat(),
        "variables": {
            "cape": 1500.0,
            "lifted_index": -4.0,
            "convective_inhibition": -180.0,     # CIN muy fuerte → inhibe tormenta
            "freezing_level_height": 4000.0,
            "temperature_2m": 27.0,
            "precipitation": 0.5,
            "showers": 0.2,
            "wind_speed_10m": 12.0,
            "wind_gusts_10m": 22.0,
            "cloud_cover": 50.0,
            "relative_humidity_2m": 60.0,
            "total_column_integrated_water_vapour": 25.0,
            "weathercode": 3,                    # nublado — sin tormenta
        },
        "granizo_real": False,                   # CIN impidió el granizo
    },

    # ── BAJO RIESGO — no debe predecir granizo ────────────────────────

    {
        "id": "BR-01",
        "descripcion": "Día soleado de verano — sin convección",
        "hora": (BASE_TIME + timedelta(hours=6)).isoformat(),
        "variables": {
            "cape": 0.0,
            "lifted_index": 2.0,                 # LI positivo = atmósfera estable
            "convective_inhibition": 0.0,
            "freezing_level_height": 4500.0,
            "temperature_2m": 32.0,
            "precipitation": 0.0,
            "showers": 0.0,
            "wind_speed_10m": 8.0,
            "wind_gusts_10m": 14.0,
            "cloud_cover": 10.0,
            "relative_humidity_2m": 35.0,
            "total_column_integrated_water_vapour": 18.0,
            "weathercode": 0,                    # soleado
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
            "total_column_integrated_water_vapour": 20.0,
            "weathercode": 63,                   # lluvia moderada
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
            "total_column_integrated_water_vapour": 8.0,
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
            "total_column_integrated_water_vapour": 10.0,
            "weathercode": 75,                   # nevada intensa
        },
        "granizo_real": False,
    },
]

# Umbral de clasificación (igual que en el sistema real)
UMBRAL_GRANIZO = 35.0

# Campos que el modelo necesita como exógenos (mismo orden que HailPredictor)
EXOG_VARS = [
    "cape", "lifted_index", "freezing_level_height",
    "temperature_2m", "precipitation", "showers",
    "wind_speed_10m", "cloud_cover", "relative_humidity_2m",
    "convective_inhibition", "total_column_integrated_water_vapour",
    "wind_gusts_10m",
]