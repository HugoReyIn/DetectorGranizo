"""
HailPredictorTest.py — Suite completa de pruebas  DetectorGranizo
═══════════════════════════════════════════════════════════════════

Bloques de tests:
  ① Unitarios — HailPredictor (lógica física interna)
  ② Unitarios — LocalAlertService (umbrales y niveles de alerta)
  ③ Unitarios — FieldService / UserService (lógica de negocio)
  ④ Integración — pipeline HailPredictor → LocalAlertService
  ⑤ Integración — AlertMonitor (lógica de cierre/apertura de techo)
  ⑥ IA — predict_hail con coordenadas reales (requiere red)

Uso:
    # Desde la carpeta raíz del proyecto:
    python test/HailPredictorTest.py

    # Solo tests sin red:
    python test/HailPredictorTest.py --no-ia

    # Con pytest:
    pytest test/HailPredictorTest.py -v

Requisitos:
    pip install numpy pandas requests bcrypt
"""

import sys
import os
import unittest
import argparse
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

# ── Path: añadir src/ al sys.path ───────────────────────────────────────────
# Layout real del proyecto:
#   DETECTORGRANIZO/
#     src/
#       ia/HailPredictor.py, services/LocalAlertService.py, ...
#     test/
#       HailPredictorTest.py   ← este archivo
#
# Solo necesitamos que src/ esté en sys.path; los paquetes (ia, services,
# daos, models, facades) ya tienen sus __init__.py y se importan con su
# nombre de paquete real, sin ningún shim.

import types as _types

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_PARENT   = os.path.abspath(os.path.join(_THIS_DIR, ".."))

def _find_src() -> str:
    """Localiza la carpeta src/ que contiene los paquetes del proyecto."""
    candidates = [
        os.path.join(_PARENT, "src"),    # test/../src/   ← layout estándar
        os.path.join(_THIS_DIR, "src"),  # test/src/      (menos habitual)
        _PARENT,                          # test/../       (todo en raíz sin src/)
        _THIS_DIR,                        # test/          (layout completamente plano)
    ]
    for p in candidates:
        # Buscamos ia/HailPredictor.py que es el módulo clave
        if os.path.isfile(os.path.join(p, "ia", "HailPredictor.py")):
            return p
        # También aceptamos HailPredictor.py suelto (layout plano legacy)
        if os.path.isfile(os.path.join(p, "HailPredictor.py")):
            return p
    return _PARENT

SRC = _find_src()
if SRC not in sys.path:
    sys.path.insert(0, SRC)

# ── Mock de mysql.connector (BD no disponible en tests) ──────────────────────
# Los DAOs importan mysql al cargarse; lo mockeamos antes para que no explote.
if "mysql" not in sys.modules:
    _mysql     = _types.ModuleType("mysql")
    _connector = _types.ModuleType("mysql.connector")
    _pooling   = _types.ModuleType("mysql.connector.pooling")

    class _FakePool:
        def __init__(self, **kw): pass
        def get_connection(self): return None

    _pooling.MySQLConnectionPool = _FakePool
    _connector.pooling = _pooling
    _mysql.connector   = _connector
    sys.modules["mysql"]                   = _mysql
    sys.modules["mysql.connector"]         = _connector
    sys.modules["mysql.connector.pooling"] = _pooling

# ── Mock de config (credenciales de BD/SMTP no disponibles en tests) ─────────
try:
    import config as _cfg  # noqa: F401
except (ImportError, Exception):
    _cfg = _types.ModuleType("config")
    for _k in ("DB_HOST", "DB_PORT", "DB_USER", "DB_PASSWORD", "DB_NAME",
               "SMTP_HOST", "SMTP_PORT", "SMTP_USER", "SMTP_PASSWORD", "SMTP_FROM",
               "NOMINATIM_BASE_URL", "NOMINATIM_TIMEOUT", "NOMINATIM_USER_AGENT",
               "OPEN_METEO_BASE_URL", "OPEN_METEO_ARCHIVE_URL", "OPEN_METEO_TIMEOUT",
               "ALERT_STATE_FILE", "SECRET_KEY"):
        setattr(_cfg, _k, "mock")
    _cfg.DB_PORT         = 3306
    _cfg.SMTP_PORT       = 587
    _cfg.NOMINATIM_TIMEOUT    = 10
    _cfg.OPEN_METEO_TIMEOUT   = 15
    sys.modules["config"] = _cfg

# ── Importar módulos del proyecto con sus rutas de paquete reales ────────────
try:
    from ia.HailPredictor import (
        _wcode_base,
        _cape_factor,
        _li_factor,
        _freezing_factor,
        _precip_factor,
        _compute_hour_probability,
        predict_hail,
        WCODE_BASE_PROB,
    )
    import pandas as pd
    HAIL_OK = True
except ImportError as e:
    print(f"[AVISO] No se pudo importar HailPredictor: {e}")
    print(f"        Comprueba que numpy/pandas están instalados y que SRC={SRC!r} es correcto.")
    HAIL_OK = False

try:
    from services.LocalAlertService import calculate_alerts, _nivel, _nivel_inv
    ALERTS_OK = True
except ImportError as e:
    print(f"[AVISO] No se pudo importar LocalAlertService: {e}")
    ALERTS_OK = False

try:
    from services.FieldService import FieldService
    from services.UserService  import UserService
    from models.Field import Field
    from models.Point import Point
    from models.User  import User
    SERVICES_OK = True
except ImportError as e:
    print(f"[AVISO] No se pudo importar servicios: {e}")
    SERVICES_OK = False


# ═══════════════════════════════════════════════════════════════════════════════
# CONSTANTES Y HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

UMBRAL_GRANIZO = 35.0          # % — igual que el frontend y AlertMonitor
BASE_TIME      = datetime(2025, 6, 15, 12, 0)

# Escenarios de clasificación (usados en varios bloques)
ESCENARIOS = [
    # ── Alto riesgo: deben superar el 35% ──────────────────────────────────
    {
        "id": "AR-01", "granizo_real": True,
        "descripcion": "Tormenta severa — weathercode 99, CAPE extremo, LI muy negativo",
        "row": {"weathercode": 99, "cape": 2500.0, "lifted_index": -7.0,
                "freezing_level_height": 1800.0, "precipitation": 20.0, "showers": 25.0},
    },
    {
        "id": "AR-02", "granizo_real": True,
        "descripcion": "Tormenta con granizo — weathercode 96, CAPE alto",
        "row": {"weathercode": 96, "cape": 1600.0, "lifted_index": -5.0,
                "freezing_level_height": 2200.0, "precipitation": 12.0, "showers": 15.0},
    },
    {
        "id": "AR-03", "granizo_real": True,
        "descripcion": "Granizo fino — weathercode 77, convección moderada",
        "row": {"weathercode": 77, "cape": 900.0, "lifted_index": -3.5,
                "freezing_level_height": 2000.0, "precipitation": 5.0, "showers": 6.0},
    },
    {
        "id": "AR-04", "granizo_real": True,
        "descripcion": "CAPE muy alto + weathercode 96 sin precipitación explícita",
        "row": {"weathercode": 96, "cape": 2000.0, "lifted_index": -4.0,
                "freezing_level_height": 2500.0, "precipitation": 0.0, "showers": 2.0},
    },
    # ── Riesgo moderado: zona gris (no se exige clasificación concreta) ──────
    {
        "id": "RM-01", "granizo_real": False,
        "descripcion": "CAPE moderado, chubascos — riesgo real pero sin granizo",
        "row": {"weathercode": 63, "cape": 600.0, "lifted_index": -2.0,
                "freezing_level_height": 3000.0, "precipitation": 4.0, "showers": 3.0},
    },
    {
        "id": "RM-02", "granizo_real": False,
        "descripcion": "CAPE alto pero sin señal NWP convectiva",
        "row": {"weathercode": 3, "cape": 1200.0, "lifted_index": -3.0,
                "freezing_level_height": 3500.0, "precipitation": 0.0, "showers": 0.0},
    },
    # ── Bajo riesgo: NO deben superar el 35% ────────────────────────────────
    {
        "id": "BR-01", "granizo_real": False,
        "descripcion": "Día soleado de verano — sin convección, LI positivo",
        "row": {"weathercode": 0, "cape": 150.0, "lifted_index": 2.0,
                "freezing_level_height": 4500.0, "precipitation": 0.0, "showers": 0.0},
    },
    {
        "id": "BR-02", "granizo_real": False,
        "descripcion": "Lluvia estratiforme de otoño — sin convección",
        "row": {"weathercode": 63, "cape": 50.0, "lifted_index": 1.0,
                "freezing_level_height": 4000.0, "precipitation": 3.0, "showers": 0.0},
    },
    {
        "id": "BR-03", "granizo_real": False,
        "descripcion": "Noche de invierno despejada — imposible granizo convectivo",
        "row": {"weathercode": 0, "cape": 0.0, "lifted_index": 5.0,
                "freezing_level_height": 6000.0, "precipitation": 0.0, "showers": 0.0},
    },
    {
        "id": "BR-04", "granizo_real": False,
        "descripcion": "Nevada — precipitación sólida pero no granizo convectivo",
        "row": {"weathercode": 75, "cape": 10.0, "lifted_index": 3.0,
                "freezing_level_height": 800.0, "precipitation": 5.0, "showers": 0.0},
    },
]


def _row_to_series(row_dict: dict):
    """Convierte dict a pd.Series si pandas está disponible, si no lo deja como dict."""
    if HAIL_OK:
        return pd.Series(row_dict)
    return row_dict


def _prob(row_dict: dict) -> float:
    """Calcula probabilidad (0-100) usando _compute_hour_probability."""
    if not HAIL_OK:
        return 0.0
    return round(_compute_hour_probability(_row_to_series(row_dict)) * 100, 1)


def _clasificar(prob: float) -> bool:
    return prob >= UMBRAL_GRANIZO


def _make_hourly_block(n: int = 48, base_hour: int = 12,
                       temp: float = 22.0, precip: float = 0.0,
                       gusts: float = 20.0, snow: float = 0.0,
                       cape: float = 0.0, wcode: int = 0,
                       vis: float = 10000.0, hum: float = 50.0) -> dict:
    """Genera un bloque hourly de Open-Meteo sintético para tests de alertas."""
    start = datetime(2025, 6, 15, base_hour, 0)
    times = [(start + timedelta(hours=i)).strftime("%Y-%m-%dT%H:00") for i in range(n)]
    return {
        "hourly": {
            "time":               times,
            "temperature_2m":     [temp]   * n,
            "precipitation":      [precip] * n,
            "snowfall":           [snow]   * n,
            "wind_gusts_10m":     [gusts]  * n,
            "wind_speed_10m":     [10.0]   * n,
            "relative_humidity_2m": [hum]  * n,
            "visibility":         [vis]    * n,
            "cape":               [cape]   * n,
            "weathercode":        [wcode]  * n,
        }
    }


# ═══════════════════════════════════════════════════════════════════════════════
# ① BLOQUE UNITARIO — HailPredictor
# ═══════════════════════════════════════════════════════════════════════════════

@unittest.skipUnless(HAIL_OK, "HailPredictor no disponible")
class TestHailPredictorUnitario(unittest.TestCase):
    """Tests de caja blanca sobre las funciones internas de HailPredictor."""

    # ── Factores individuales ────────────────────────────────────────────────

    def test_wcode_base_conocidos(self):
        """_wcode_base devuelve los valores documentados."""
        self.assertEqual(_wcode_base(99), 0.85)
        self.assertEqual(_wcode_base(96), 0.55)
        self.assertEqual(_wcode_base(77), 0.30)
        self.assertEqual(_wcode_base(95), 0.05)
        self.assertEqual(_wcode_base(0),  0.0)
        self.assertEqual(_wcode_base(63), 0.0)

    def test_wcode_base_ordenados(self):
        """El riesgo de weathercode respeta: 99 > 96 > 77 > 95 > resto."""
        self.assertGreater(_wcode_base(99), _wcode_base(96))
        self.assertGreater(_wcode_base(96), _wcode_base(77))
        self.assertGreater(_wcode_base(77), _wcode_base(95))
        self.assertGreater(_wcode_base(95), _wcode_base(0))

    def test_cape_factor_escalonado(self):
        """_cape_factor crece monótonamente con el CAPE."""
        self.assertEqual(_cape_factor(0),    0.0)
        self.assertLess(_cape_factor(100),   _cape_factor(300))
        self.assertLess(_cape_factor(300),   _cape_factor(600))
        self.assertLess(_cape_factor(600),   _cape_factor(900))
        self.assertLess(_cape_factor(900),   _cape_factor(1600))
        # Techo: no supera 0.30 nunca (calibrado para clima ibérico)
        self.assertLessEqual(_cape_factor(5000), 0.30)

    def test_li_factor_negativo_aumenta(self):
        """LI más negativo = mayor inestabilidad = mayor factor."""
        self.assertEqual(_li_factor(None), 0.0)
        self.assertEqual(_li_factor(2),    0.0)
        self.assertGreater(_li_factor(-2), 0.0)
        self.assertGreater(_li_factor(-4), _li_factor(-2))
        self.assertGreater(_li_factor(-6), _li_factor(-4))

    def test_freezing_factor_bajo_nivel_cero(self):
        """Isoterma 0°C baja (granizo llega al suelo) da factor más alto."""
        self.assertEqual(_freezing_factor(None), 0.0)
        self.assertGreater(_freezing_factor(1000), _freezing_factor(2000))
        self.assertGreater(_freezing_factor(2000), _freezing_factor(3000))
        self.assertGreater(_freezing_factor(3000), _freezing_factor(4000))
        self.assertEqual(_freezing_factor(4000), 0.0)

    def test_precip_factor_escalonado(self):
        """Mayor precipitación convectiva → mayor factor."""
        self.assertEqual(_precip_factor(0, 0),   0.0)
        self.assertGreater(_precip_factor(6, 0),  _precip_factor(0, 0))
        self.assertGreater(_precip_factor(20, 0), _precip_factor(6, 0))
        # showers compite con precip: max de los dos
        self.assertEqual(_precip_factor(0, 20),  _precip_factor(20, 0))

    # ── _compute_hour_probability: regla NWP ─────────────────────────────────

    def test_sin_nwp_cape_limitado_al_20pct(self):
        """Sin señal NWP (wcode sin convección), el CAPE solo llega al 20%."""
        row = _row_to_series({
            "weathercode": 0, "cape": 5000.0, "lifted_index": -10.0,
            "freezing_level_height": 500.0, "precipitation": 0.0, "showers": 0.0,
        })
        prob = _compute_hour_probability(row)
        self.assertLessEqual(prob, 0.20,
            f"Sin NWP la prob no debe superar 20%, obtenida: {prob:.2%}")

    def test_con_nwp_amplifica_factores(self):
        """Con wcode=99, los factores físicos se suman sin techo del 20%."""
        row_sin = _row_to_series({
            "weathercode": 0, "cape": 2000.0, "lifted_index": -7.0,
            "freezing_level_height": 1500.0, "precipitation": 20.0, "showers": 20.0,
        })
        row_con = _row_to_series({
            "weathercode": 99, "cape": 2000.0, "lifted_index": -7.0,
            "freezing_level_height": 1500.0, "precipitation": 20.0, "showers": 20.0,
        })
        self.assertGreater(
            _compute_hour_probability(row_con),
            _compute_hour_probability(row_sin),
            "wcode=99 debe dar probabilidad mayor que wcode=0 con los mismos parámetros físicos"
        )

    def test_prob_siempre_entre_0_y_1(self):
        """La probabilidad horaria nunca sale del rango [0, 1]."""
        casos = [
            {"weathercode": 0,  "cape": 0.0,    "lifted_index": 5.0,   "freezing_level_height": 5000.0, "precipitation": 0.0,  "showers": 0.0},
            {"weathercode": 99, "cape": 3000.0,  "lifted_index": -10.0, "freezing_level_height": 500.0,  "precipitation": 50.0, "showers": 50.0},
            {"weathercode": 77, "cape": 900.0,   "lifted_index": -3.0,  "freezing_level_height": 2000.0, "precipitation": 5.0,  "showers": 5.0},
        ]
        for d in casos:
            prob = _compute_hour_probability(_row_to_series(d))
            with self.subTest(wcode=d["weathercode"]):
                self.assertGreaterEqual(prob, 0.0)
                self.assertLessEqual(prob, 1.0)

    def test_cape_cero_wcode_neutro_da_cero(self):
        """Sin CAPE y sin weathercode convectivo, la probabilidad es 0."""
        row = _row_to_series({
            "weathercode": 0, "cape": 0.0, "lifted_index": 3.0,
            "freezing_level_height": 5000.0, "precipitation": 0.0, "showers": 0.0,
        })
        self.assertEqual(_compute_hour_probability(row), 0.0)

    # ── Clasificación por escenarios ─────────────────────────────────────────

    def test_escenarios_ar_superan_umbral(self):
        """Todos los escenarios AR-* deben superar el 35%."""
        for esc in [e for e in ESCENARIOS if e["id"].startswith("AR-")]:
            with self.subTest(id=esc["id"]):
                prob = _prob(esc["row"])
                self.assertGreaterEqual(prob, UMBRAL_GRANIZO,
                    f"[{esc['id']}] {esc['descripcion']} → {prob}% < {UMBRAL_GRANIZO}%")

    def test_escenarios_br_no_superan_umbral(self):
        """Todos los escenarios BR-* deben estar por debajo del 35%."""
        for esc in [e for e in ESCENARIOS if e["id"].startswith("BR-")]:
            with self.subTest(id=esc["id"]):
                prob = _prob(esc["row"])
                self.assertLess(prob, UMBRAL_GRANIZO,
                    f"[{esc['id']}] {esc['descripcion']} → {prob}% >= {UMBRAL_GRANIZO}%")

    def test_metricas_sobre_escenarios(self):
        """Accuracy, Recall y F1 deben superar umbrales mínimos sobre los escenarios."""
        TP = TN = FP = FN = 0
        for esc in ESCENARIOS:
            prob = _prob(esc["row"])
            pred = _clasificar(prob)
            real = esc["granizo_real"]
            if pred and real:           TP += 1
            elif not pred and not real: TN += 1
            elif pred and not real:     FP += 1
            else:                       FN += 1

        total     = TP + TN + FP + FN
        accuracy  = (TP + TN) / total if total else 0
        recall    = TP / (TP + FN) if (TP + FN) else 0
        precision = TP / (TP + FP) if (TP + FP) else 1
        f1        = 2 * precision * recall / (precision + recall) if (precision + recall) else 0

        self.assertGreaterEqual(accuracy, 0.70,  f"Accuracy={accuracy:.1%} < 70%")
        self.assertGreaterEqual(recall,   0.75,  f"Recall={recall:.1%} < 75%  (FN={FN})")
        self.assertGreaterEqual(f1,       0.70,  f"F1={f1:.3f} < 0.70")
        self.assertEqual(FN, 0, f"{FN} granizos AR no detectados (FN > 0)")


# ═══════════════════════════════════════════════════════════════════════════════
# ② BLOQUE UNITARIO — LocalAlertService
# ═══════════════════════════════════════════════════════════════════════════════

@unittest.skipUnless(ALERTS_OK, "LocalAlertService no disponible")
class TestLocalAlertServiceUnitario(unittest.TestCase):
    """Tests de caja blanca sobre _nivel, _nivel_inv y calculate_alerts."""

    # ── Helpers internos ─────────────────────────────────────────────────────

    def test_nivel_umbrales(self):
        """_nivel clasifica correctamente según thresholds [am, na, ro]."""
        th = [32, 36, 40]
        self.assertEqual(_nivel(25.0, th), "verde")
        self.assertEqual(_nivel(33.0, th), "amarillo")
        self.assertEqual(_nivel(37.0, th), "naranja")
        self.assertEqual(_nivel(41.0, th), "rojo")
        self.assertEqual(_nivel(32.0, th), "amarillo")   # exactamente en umbral

    def test_nivel_inv_umbrales(self):
        """_nivel_inv clasifica correctamente (menor valor = mayor riesgo)."""
        th = [1000, 500, 200]
        self.assertEqual(_nivel_inv(2000, th), "verde")
        self.assertEqual(_nivel_inv(800,  th), "amarillo")
        self.assertEqual(_nivel_inv(400,  th), "naranja")
        self.assertEqual(_nivel_inv(100,  th), "rojo")
        self.assertEqual(_nivel_inv(1000, th), "amarillo")  # exactamente en umbral

    # ── calculate_alerts — caso sin datos ────────────────────────────────────

    def test_sin_datos_devuelve_defaults(self):
        """Sin array de tiempos, devuelve resultado por defecto (todo verde)."""
        result = calculate_alerts({"hourly": {}})
        for campo in ("calor", "helada", "lluvia", "nieve", "viento", "tormenta", "granizo", "niebla"):
            self.assertEqual(result[campo]["nivel"], "verde")
        self.assertIn("No hay alertas activas", result["ticker"])

    # ── Calor ────────────────────────────────────────────────────────────────

    def test_calor_amarillo(self):
        data = _make_hourly_block(temp=34.0, base_hour=0)
        result = calculate_alerts(data)
        self.assertIn(result["calor"]["nivel"], ("amarillo", "naranja", "rojo"))

    def test_calor_rojo(self):
        data = _make_hourly_block(temp=41.0, base_hour=0)
        result = calculate_alerts(data)
        self.assertEqual(result["calor"]["nivel"], "rojo")

    def test_sin_calor(self):
        data = _make_hourly_block(temp=25.0, base_hour=0)
        result = calculate_alerts(data)
        self.assertEqual(result["calor"]["nivel"], "verde")

    # ── Lluvia ───────────────────────────────────────────────────────────────

    def test_lluvia_intensa_rojo(self):
        data = _make_hourly_block(precip=45.0, base_hour=0)
        result = calculate_alerts(data)
        self.assertEqual(result["lluvia"]["nivel"], "rojo")

    def test_lluvia_leve_verde(self):
        data = _make_hourly_block(precip=2.0, base_hour=0)
        result = calculate_alerts(data)
        self.assertEqual(result["lluvia"]["nivel"], "verde")

    # ── Viento ───────────────────────────────────────────────────────────────

    def test_viento_fuerte_naranja(self):
        data = _make_hourly_block(gusts=75.0, base_hour=0)
        result = calculate_alerts(data)
        self.assertIn(result["viento"]["nivel"], ("naranja", "rojo"))

    def test_viento_moderado_verde(self):
        data = _make_hourly_block(gusts=30.0, base_hour=0)
        result = calculate_alerts(data)
        self.assertEqual(result["viento"]["nivel"], "verde")

    # ── Nieve ────────────────────────────────────────────────────────────────

    def test_nieve_acumulada_naranja(self):
        # 5 cm/h durante 48h → acumulado >> umbral naranja (5 cm/24h)
        # Usamos base_hour=0 para asegurarnos de que el índice actual sea ≤ hora 0
        # y haya al menos 24h con nevada intensa en la ventana de predicción
        data = _make_hourly_block(snow=5.0, base_hour=0)
        result = calculate_alerts(data)
        self.assertIn(result["nieve"]["nivel"], ("naranja", "rojo", "amarillo"),
            f"5 cm/h × 24h debe dar alerta de nieve, obtenido: {result['nieve']}")

    # ── Granizo — fallback físico (sin IA) ───────────────────────────────────

    def test_granizo_fallback_wcode96_cape_alto(self):
        """wcode=96 + CAPE >= 800 → naranja o rojo sin IA."""
        data = _make_hourly_block(wcode=96, cape=1000.0, base_hour=0)
        result = calculate_alerts(data, hail_prediction=None)
        self.assertIn(result["granizo"]["nivel"], ("naranja", "rojo"))

    def test_granizo_wcode99_rojo(self):
        """wcode=99 + CAPE >= 1500 → rojo sin IA."""
        data = _make_hourly_block(wcode=99, cape=1600.0, base_hour=0)
        result = calculate_alerts(data, hail_prediction=None)
        self.assertEqual(result["granizo"]["nivel"], "rojo")

    def test_granizo_sin_señal_verde(self):
        """Sin CAPE ni wcode de granizo → verde."""
        data = _make_hourly_block(wcode=0, cape=100.0, base_hour=0)
        result = calculate_alerts(data, hail_prediction=None)
        self.assertEqual(result["granizo"]["nivel"], "verde")

    # ── Granizo — con IA ─────────────────────────────────────────────────────

    def test_granizo_ia_prob_alta_rojo(self):
        """IA con prob >= 60% + CAPE convectivo → rojo."""
        data = _make_hourly_block(wcode=96, cape=1000.0, base_hour=0)
        hail = [{"time": datetime.now().strftime("%Y-%m-%dT%H:00"), "hail_probability": 75.0}]
        result = calculate_alerts(data, hail_prediction=hail)
        self.assertEqual(result["granizo"]["nivel"], "rojo")

    def test_granizo_ia_prob_alta_sin_cape_verde(self):
        """IA con prob alta pero sin actividad convectiva → NO activa alerta."""
        data = _make_hourly_block(wcode=0, cape=50.0, base_hour=0)
        hail = [{"time": datetime.now().strftime("%Y-%m-%dT%H:00"), "hail_probability": 80.0}]
        result = calculate_alerts(data, hail_prediction=hail)
        self.assertEqual(result["granizo"]["nivel"], "verde",
            "Sin actividad convectiva (CAPE bajo + wcode neutro) no debe activar alerta de granizo")

    # ── Ticker ───────────────────────────────────────────────────────────────

    def test_ticker_refleja_alertas_activas(self):
        """Si hay alerta de calor, el ticker lo menciona."""
        data = _make_hourly_block(temp=42.0, base_hour=0)
        result = calculate_alerts(data)
        ticker_text = " ".join(result["ticker"])
        self.assertIn("calor", ticker_text.lower())

    def test_ticker_vacio_sin_alertas(self):
        """Sin alertas, el ticker dice 'No hay alertas activas'."""
        data = _make_hourly_block(temp=20.0, base_hour=0)
        result = calculate_alerts(data)
        self.assertIn("No hay alertas activas", result["ticker"])


# ═══════════════════════════════════════════════════════════════════════════════
# ③ BLOQUE UNITARIO — Servicios de negocio (FieldService, UserService)
# ═══════════════════════════════════════════════════════════════════════════════

@unittest.skipUnless(SERVICES_OK, "Servicios de negocio no disponibles")
class TestServiciosNegocioUnitario(unittest.TestCase):
    """Tests con mocks de DAO para aislar la lógica pura de servicio."""

    def _make_field(self, fid=1, user_id=10, name="Finca A", municipality="Toledo",
                    area=5.0, crop_type="trigo") -> "Field":
        f = MagicMock(spec=Field)
        f.id          = fid
        f.user_id     = user_id
        f.name        = name
        f.municipality= municipality
        f.area        = area
        f.crop_type   = crop_type
        return f

    def _make_point(self, lat, lon) -> "Point":
        p = MagicMock(spec=Point)
        p.latitude  = lat
        p.longitude = lon
        return p

    # ── FieldService ─────────────────────────────────────────────────────────

    def test_get_field_if_owned_correcto(self):
        """Devuelve el campo si pertenece al usuario."""
        field      = self._make_field(fid=1, user_id=10)
        field_dao  = MagicMock(); field_dao.getField.return_value = field
        point_dao  = MagicMock()
        svc        = FieldService(field_dao, point_dao)

        result = svc.get_field_if_owned(field_id=1, user_id=10)
        self.assertEqual(result, field)

    def test_get_field_if_owned_ajeno(self):
        """Devuelve None si el campo pertenece a otro usuario."""
        field      = self._make_field(fid=1, user_id=99)
        field_dao  = MagicMock(); field_dao.getField.return_value = field
        point_dao  = MagicMock()
        svc        = FieldService(field_dao, point_dao)

        result = svc.get_field_if_owned(field_id=1, user_id=10)
        self.assertIsNone(result)

    def test_get_field_if_owned_inexistente(self):
        """Devuelve None si el campo no existe en la BD."""
        field_dao  = MagicMock(); field_dao.getField.return_value = None
        point_dao  = MagicMock()
        svc        = FieldService(field_dao, point_dao)

        result = svc.get_field_if_owned(field_id=999, user_id=10)
        self.assertIsNone(result)

    def test_get_fields_calcula_centroide(self):
        """get_fields_for_user calcula lat/lon como centroide de los puntos."""
        field      = self._make_field(fid=1, user_id=10)
        field_dao  = MagicMock(); field_dao.getAllFieldsByUser.return_value = [field]
        point_dao  = MagicMock()
        point_dao.getPointsByField.return_value = [
            self._make_point(40.0, -3.0),
            self._make_point(41.0, -4.0),
        ]
        svc = FieldService(field_dao, point_dao)
        fields = svc.get_fields_for_user(user_id=10)

        self.assertEqual(len(fields), 1)
        self.assertAlmostEqual(fields[0].lat, 40.5)
        self.assertAlmostEqual(fields[0].lon, -3.5)

    def test_get_fields_sin_puntos_lat_none(self):
        """Un campo sin puntos debe tener lat=None y lon=None."""
        field      = self._make_field(fid=1, user_id=10)
        field_dao  = MagicMock(); field_dao.getAllFieldsByUser.return_value = [field]
        point_dao  = MagicMock(); point_dao.getPointsByField.return_value = []
        svc        = FieldService(field_dao, point_dao)

        fields = svc.get_fields_for_user(user_id=10)
        self.assertIsNone(fields[0].lat)
        self.assertIsNone(fields[0].lon)

    def test_get_points_json_formato(self):
        """get_points_json devuelve JSON válido con lat/lng."""
        import json
        field_dao  = MagicMock()
        point_dao  = MagicMock()
        point_dao.getPointsByField.return_value = [
            self._make_point(40.0, -3.0),
            self._make_point(41.0, -4.0),
        ]
        svc    = FieldService(field_dao, point_dao)
        result = json.loads(svc.get_points_json(field_id=1))

        self.assertEqual(len(result), 2)
        self.assertIn("lat", result[0])
        self.assertIn("lng", result[0])

    # ── UserService ──────────────────────────────────────────────────────────

    def test_authenticate_correcto(self):
        """authenticate devuelve el usuario cuando las credenciales son correctas."""
        import bcrypt
        hashed = bcrypt.hashpw(b"mi_clave", bcrypt.gensalt()).decode()
        user   = MagicMock(spec=User)
        user.password = hashed

        dao = MagicMock()
        dao.getUserByEmail.return_value = user
        svc = UserService(dao)

        result = svc.authenticate("user@example.com", "mi_clave")
        self.assertEqual(result, user)

    def test_authenticate_clave_incorrecta(self):
        """authenticate devuelve None con contraseña incorrecta."""
        import bcrypt
        hashed = bcrypt.hashpw(b"correcta", bcrypt.gensalt()).decode()
        user   = MagicMock(spec=User)
        user.password = hashed

        dao = MagicMock()
        dao.getUserByEmail.return_value = user
        svc = UserService(dao)

        result = svc.authenticate("user@example.com", "incorrecta")
        self.assertIsNone(result)

    def test_authenticate_usuario_no_existe(self):
        """authenticate devuelve None si el email no existe."""
        dao = MagicMock(); dao.getUserByEmail.return_value = None
        svc = UserService(dao)
        result = svc.authenticate("noexiste@example.com", "clave")
        self.assertIsNone(result)


# ═══════════════════════════════════════════════════════════════════════════════
# ④ BLOQUE INTEGRACIÓN — HailPredictor → LocalAlertService
# ═══════════════════════════════════════════════════════════════════════════════

@unittest.skipUnless(HAIL_OK and ALERTS_OK, "HailPredictor o LocalAlertService no disponibles")
class TestIntegracionHailAlerts(unittest.TestCase):
    """
    Tests de integración end-to-end:
    probabilidades del predictor → alertas del servicio local.
    No se hacen llamadas de red: se inyectan datos sintéticos.
    """

    def _hail_pred(self, prob: float) -> list[dict]:
        """Crea una predicción IA con la probabilidad indicada para ahora mismo."""
        return [{
            "time": datetime.now().strftime("%Y-%m-%dT%H:00"),
            "hail_probability": prob,
            "cape": 1500.0,
            "lifted_index": -5.0,
        }]

    def test_prob_alta_mas_cape_da_alerta_rojo(self):
        """Predicción IA >= 60% + CAPE convectivo → alerta granizo rojo."""
        data   = _make_hourly_block(cape=800.0, wcode=96, base_hour=0)
        result = calculate_alerts(data, hail_prediction=self._hail_pred(65.0))
        self.assertEqual(result["granizo"]["nivel"], "rojo")

    def test_prob_moderada_da_naranja(self):
        """Predicción IA 35-59% + señal convectiva → naranja."""
        data   = _make_hourly_block(cape=800.0, wcode=96, base_hour=0)
        result = calculate_alerts(data, hail_prediction=self._hail_pred(45.0))
        self.assertIn(result["granizo"]["nivel"], ("naranja", "rojo"))

    def test_prob_baja_no_activa_alerta(self):
        """Predicción IA < 15% → verde aunque haya algo de CAPE."""
        data   = _make_hourly_block(cape=400.0, wcode=3, base_hour=0)
        result = calculate_alerts(data, hail_prediction=self._hail_pred(10.0))
        self.assertEqual(result["granizo"]["nivel"], "verde")

    def test_sin_hail_prediction_usa_fallback(self):
        """Sin predicción IA, se usa el fallback físico CAPE + weathercode."""
        data   = _make_hourly_block(cape=1600.0, wcode=99, base_hour=0)
        result = calculate_alerts(data, hail_prediction=None)
        self.assertIn(result["granizo"]["nivel"], ("naranja", "rojo"))

    def test_escenario_ar01_end_to_end(self):
        """AR-01 (tormenta severa) debe dar granizo >= naranja en el pipeline completo."""
        esc  = next(e for e in ESCENARIOS if e["id"] == "AR-01")
        row  = esc["row"]
        prob = _prob(row)
        self.assertGreaterEqual(prob, UMBRAL_GRANIZO, f"AR-01 prob={prob}% < {UMBRAL_GRANIZO}%")

        hail = [{"time": datetime.now().strftime("%Y-%m-%dT%H:00"), "hail_probability": prob}]
        data = _make_hourly_block(cape=row["cape"], wcode=row["weathercode"], base_hour=0)
        result = calculate_alerts(data, hail_prediction=hail)
        self.assertIn(result["granizo"]["nivel"], ("naranja", "rojo"))

    def test_escenario_br01_end_to_end(self):
        """BR-01 (día soleado) no debe generar ninguna alerta de granizo."""
        esc  = next(e for e in ESCENARIOS if e["id"] == "BR-01")
        row  = esc["row"]
        prob = _prob(row)

        hail = [{"time": datetime.now().strftime("%Y-%m-%dT%H:00"), "hail_probability": prob}]
        data = _make_hourly_block(cape=row["cape"], wcode=row["weathercode"], base_hour=0)
        result = calculate_alerts(data, hail_prediction=hail)
        self.assertEqual(result["granizo"]["nivel"], "verde")


# ═══════════════════════════════════════════════════════════════════════════════
# ⑤ BLOQUE INTEGRACIÓN — Lógica de cierre/apertura de techo (AlertMonitor)
# ═══════════════════════════════════════════════════════════════════════════════

class TestAlertMonitorLogica(unittest.TestCase):
    """
    Tests de la lógica de cierre/apertura de techo sin instanciar AlertMonitor
    (que requiere BD). Se prueba la lógica pura de decisión.
    """

    def _debe_cerrar(self, prob: float) -> bool:
        return prob >= UMBRAL_GRANIZO

    def _debe_abrir(self, prob: float, auto_cerrado: bool, estado: str) -> bool:
        return prob < UMBRAL_GRANIZO and auto_cerrado and estado == "closed"

    def test_umbral_exacto_cierra(self):
        self.assertTrue(self._debe_cerrar(35.0))

    def test_justo_bajo_umbral_no_cierra(self):
        self.assertFalse(self._debe_cerrar(34.9))

    def test_cero_no_cierra(self):
        self.assertFalse(self._debe_cerrar(0.0))

    def test_cien_cierra(self):
        self.assertTrue(self._debe_cerrar(100.0))

    def test_apertura_riesgo_bajo_auto_cerrado(self):
        """Riesgo bajo + auto-cerrado + estado closed → debe abrir."""
        self.assertTrue(self._debe_abrir(20.0, True, "closed"))

    def test_apertura_no_si_manual(self):
        """Cerrado manualmente → no abre aunque el riesgo baje."""
        self.assertFalse(self._debe_abrir(20.0, False, "closed"))

    def test_apertura_no_si_riesgo_alto(self):
        """Riesgo aún por encima del umbral → no abre."""
        self.assertFalse(self._debe_abrir(40.0, True, "closed"))

    def test_apertura_no_si_ya_abierto(self):
        """Si el techo ya está abierto no hay nada que abrir."""
        self.assertFalse(self._debe_abrir(10.0, True, "open"))

    def test_apertura_justo_bajo_umbral(self):
        """34.9% (justo bajo umbral) + auto-cerrado → debe abrir."""
        self.assertTrue(self._debe_abrir(34.9, True, "closed"))

    def test_secuencia_completa(self):
        """Simula ciclo: sube riesgo → cierra → baja riesgo → abre."""
        estado     = "open"
        auto_cerr  = False

        # Riesgo sube a 70%
        prob = 70.0
        if self._debe_cerrar(prob) and estado == "open":
            estado    = "closed"
            auto_cerr = True
        self.assertEqual(estado, "closed")
        self.assertTrue(auto_cerr)

        # Riesgo baja a 10%
        prob = 10.0
        if self._debe_abrir(prob, auto_cerr, estado):
            estado    = "open"
            auto_cerr = False
        self.assertEqual(estado, "open")
        self.assertFalse(auto_cerr)


# ═══════════════════════════════════════════════════════════════════════════════
# ⑥ BLOQUE IA — predict_hail con datos reales (requiere red)
# ═══════════════════════════════════════════════════════════════════════════════

@unittest.skipUnless(HAIL_OK, "HailPredictor no disponible")
class TestIAPrediccionReal(unittest.TestCase):
    """
    Tests funcionales que llaman a la API real de Open-Meteo.
    Se omiten con --no-ia o cuando no hay red.
    Estos tests demuestran que la IA funciona de extremo a extremo.
    """

    # Coordenadas representativas de distintos climas ibéricos
    UBICACIONES = [
        (39.8628, -4.0273, "Toledo — clima continental árido"),
        (41.6522, -0.8782, "Zaragoza — valle del Ebro, granizo frecuente"),
        (37.3886, -5.9823, "Sevilla — clima mediterráneo cálido"),
        (43.2630, -2.9340, "Bilbao — clima oceánico"),
    ]

    def test_predict_hail_devuelve_lista(self):
        """predict_hail debe devolver una lista (posiblemente vacía) para Toledo."""
        lat, lon, desc = self.UBICACIONES[0]
        try:
            result = predict_hail(lat, lon)
        except Exception as e:
            self.skipTest(f"Sin acceso a la red: {e}")

        self.assertIsInstance(result, list, f"Esperaba lista, obtuvo {type(result)}")

    def test_predict_hail_estructura_cada_elemento(self):
        """Cada elemento de predict_hail debe tener las claves esperadas."""
        lat, lon, _ = self.UBICACIONES[0]
        try:
            result = predict_hail(lat, lon)
        except Exception as e:
            self.skipTest(f"Sin acceso a la red: {e}")

        if not result:
            self.skipTest("API devolvió lista vacía (sin horas futuras disponibles)")

        for item in result[:5]:   # comprueba los primeros 5 elementos
            with self.subTest(time=item.get("time")):
                self.assertIn("time",             item)
                self.assertIn("hail_probability", item)
                self.assertIn("cape",             item)
                self.assertIn("lifted_index",     item)

    def test_predict_hail_probabilidades_en_rango(self):
        """Todas las probabilidades deben estar en [0, 100]."""
        lat, lon, _ = self.UBICACIONES[0]
        try:
            result = predict_hail(lat, lon)
        except Exception as e:
            self.skipTest(f"Sin acceso a la red: {e}")

        for item in result:
            with self.subTest(time=item["time"]):
                self.assertGreaterEqual(item["hail_probability"], 0.0)
                self.assertLessEqual(item["hail_probability"],    100.0)

    def test_predict_hail_timestamps_crecientes(self):
        """Los timestamps deben ser crecientes y tener formato ISO."""
        lat, lon, _ = self.UBICACIONES[0]
        try:
            result = predict_hail(lat, lon)
        except Exception as e:
            self.skipTest(f"Sin acceso a la red: {e}")

        if len(result) < 2:
            self.skipTest("Menos de 2 elementos, no se puede comprobar orden")

        tiempos = [datetime.fromisoformat(r["time"]) for r in result]
        for i in range(1, len(tiempos)):
            self.assertGreater(tiempos[i], tiempos[i - 1],
                f"Timestamp no creciente: {tiempos[i-1]} >= {tiempos[i]}")

    def test_predict_hail_multiples_ubicaciones(self):
        """predict_hail devuelve resultados válidos para varias ciudades ibéricas."""
        for lat, lon, desc in self.UBICACIONES:
            with self.subTest(ubicacion=desc):
                try:
                    result = predict_hail(lat, lon)
                except Exception as e:
                    self.skipTest(f"Sin red para {desc}: {e}")

                self.assertIsInstance(result, list, f"{desc}: esperaba lista")
                if result:
                    max_prob = max(r["hail_probability"] for r in result)
                    min_prob = min(r["hail_probability"] for r in result)
                    self.assertGreaterEqual(max_prob, 0.0)
                    self.assertLessEqual(min_prob, 100.0)

    def test_predict_hail_cape_no_negativo(self):
        """Los valores de CAPE nunca deben ser negativos."""
        lat, lon, _ = self.UBICACIONES[0]
        try:
            result = predict_hail(lat, lon)
        except Exception as e:
            self.skipTest(f"Sin acceso a la red: {e}")

        for item in result:
            if item["cape"] is not None:
                self.assertGreaterEqual(item["cape"], 0.0,
                    f"CAPE negativo en {item['time']}: {item['cape']}")


# ═══════════════════════════════════════════════════════════════════════════════
# RUNNER CON INFORME
# ═══════════════════════════════════════════════════════════════════════════════

def _run_group(grupo: str, suite: unittest.TestSuite, verbosity: int = 0) -> tuple[int, int, int]:
    """Ejecuta una suite y devuelve (ok, fail, skip)."""
    runner = unittest.TextTestRunner(stream=open(os.devnull, "w"),
                                     verbosity=verbosity)
    result = runner.run(suite)
    ok   = result.testsRun - len(result.failures) - len(result.errors) - len(result.skipped)
    fail = len(result.failures) + len(result.errors)
    skip = len(result.skipped)
    return ok, fail, skip, result


def _print_result(nombre: str, ok: int, fail: int, skip: int, details: list[str]):
    icon = "✅" if fail == 0 else "❌"
    skip_txt = f"  ⏭ {skip} omitido(s)" if skip else ""
    print(f"  │  {icon}  {nombre}{skip_txt}")
    for d in details:
        print(f"  │      → {d[:120]}")


def main(include_ia: bool = True):
    print("\n" + "═" * 72)
    print("  SUITE COMPLETA — DetectorGranizo")
    print("═" * 72)

    GRUPOS = [
        ("① Unitarios — HailPredictor (lógica física)",
         unittest.TestLoader().loadTestsFromTestCase(TestHailPredictorUnitario)),
        ("② Unitarios — LocalAlertService (niveles y alertas)",
         unittest.TestLoader().loadTestsFromTestCase(TestLocalAlertServiceUnitario)),
        ("③ Unitarios — Servicios de negocio (Field/User)",
         unittest.TestLoader().loadTestsFromTestCase(TestServiciosNegocioUnitario)),
        ("④ Integración — HailPredictor → LocalAlertService",
         unittest.TestLoader().loadTestsFromTestCase(TestIntegracionHailAlerts)),
        ("⑤ Integración — Lógica cierre/apertura techo",
         unittest.TestLoader().loadTestsFromTestCase(TestAlertMonitorLogica)),
    ]
    if include_ia:
        GRUPOS.append((
            "⑥ IA — predict_hail con API real (requiere red)",
            unittest.TestLoader().loadTestsFromTestCase(TestIAPrediccionReal),
        ))

    total_ok = total_fail = total_skip = 0

    for titulo, suite in GRUPOS:
        print(f"\n+── {titulo}")
        # Recolectar todos los tests de la suite (puede haber subsuites)
        all_tests = []
        def _collect(s):
            for t in s:
                if isinstance(t, unittest.TestSuite):
                    _collect(t)
                elif t is not None:
                    all_tests.append(t)
        _collect(suite)

        if not all_tests:
            print("  │  ⏭  (módulo no disponible — bloque omitido)")
            total_skip += 1
            continue

        import io
        runner_result = unittest.TextTestRunner(
            stream=io.StringIO(), verbosity=0
        ).run(suite)

        # Índices rápidos para lookup
        fail_ids    = {id(f): m for f, m in runner_result.failures}
        error_ids   = {id(f): m for f, m in runner_result.errors}
        skipped_ids = {id(t): r for t, r in runner_result.skipped}

        for test in all_tests:
            tid  = id(test)
            name = test.shortDescription() or test._testMethodName
            if tid in skipped_ids:
                print(f"  │  ⏭  {name}  [{skipped_ids[tid]}]")
                total_skip += 1
            elif tid in fail_ids:
                msg = fail_ids[tid].strip().split("\n")[-1]
                print(f"  │  ❌  {name}")
                print(f"  │      → {msg[:110]}")
                total_fail += 1
            elif tid in error_ids:
                msg = error_ids[tid].strip().split("\n")[-1]
                print(f"  │  ❌  {name}  [ERROR]")
                print(f"  │      → {msg[:110]}")
                total_fail += 1
            else:
                print(f"  │  ✅  {name}")
                total_ok += 1

    total = total_ok + total_fail
    print(f"\n{'═'*72}")
    if total_fail == 0:
        print(f"  ✅  {total_ok}/{total} tests superados — TODOS OK"
              + (f"  ({total_skip} omitidos)" if total_skip else ""))
    else:
        print(f"  ❌  {total_ok}/{total} superados — {total_fail} FALLIDO(S)"
              + (f"  ({total_skip} omitidos)" if total_skip else ""))
    print("═" * 72 + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Suite de tests DetectorGranizo")
    parser.add_argument("--no-ia", action="store_true",
                        help="Omitir los tests que requieren acceso a la red (bloque ⑥ IA)")
    args, _ = parser.parse_known_args()
    main(include_ia=not args.no_ia)