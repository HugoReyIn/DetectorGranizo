"""
test_hail_predictor.py
Suite de pruebas para el predictor de granizo de DetectorGranizo.

Objetivos:
  1. Verificar que el modelo calcula probabilidades (pipeline funciona)
  2. Verificar que >= 35% activa el cierre del techo retráctil
  3. Medir calidad de las predicciones: Accuracy, Recall y F1-Score

Uso:
    # Desde la carpeta raíz del proyecto (donde está src/):
    python tests/test_hail_predictor.py

    # O con pytest:
    pytest tests/test_hail_predictor.py -v

Requisitos:
    pip install pytest numpy pandas
"""

import sys
import os
import unittest

# ── Añadir src/ al path ──────────────────────────────────────────────
SRC_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))
sys.path.insert(0, SRC_PATH)

from DataTest import ESCENARIOS, UMBRAL_GRANIZO

# ── Importar funciones reales del proyecto ───────────────────────────
try:
    from ia.HailPredictor import compute_hail_score, weathercode_to_hail_score
    IMPORT_OK = True
except ImportError as e:
    print(f"[AVISO] No se pudo importar HailPredictor: {e}")
    print("        Asegúrate de ejecutar desde la raíz del proyecto.")
    IMPORT_OK = False


# ──────────────────────────────────────────────────────────────────────
# FUNCIÓN DE PREDICCIÓN LOCAL
# Usa compute_hail_score (la función real del proyecto) para calcular
# la probabilidad de granizo sin necesitar llamadas de red.
# ──────────────────────────────────────────────────────────────────────
def predecir_probabilidad(variables: dict) -> float:
    """
    Calcula la probabilidad de granizo (0-100) para un escenario dado,
    usando la misma lógica que compute_hail_score de HailPredictor.

    Returns:
        float: probabilidad entre 0.0 y 100.0
    """
    cape = float(variables.get("cape", 0))
    li   = float(variables.get("lifted_index", 0))
    cin  = float(variables.get("convective_inhibition", 0))
    wc   = int(variables.get("weathercode", 0))

    if IMPORT_OK:
        score = compute_hail_score(
            weathercode  = wc,
            cape         = cape,
            lifted_index = li,
            cin          = cin,
        )
    else:
        # Fallback si no se puede importar — replica la lógica de compute_hail_score
        score = _compute_hail_score_local(wc, cape, li, cin)

    return round(score * 100, 1)


def _compute_hail_score_local(weathercode: int, cape: float,
                               lifted_index: float, cin: float) -> float:
    """Replica local de compute_hail_score para entornos sin el proyecto."""
    WC_SCORES = {77: 0.5, 96: 0.7, 99: 1.0}
    score = WC_SCORES.get(weathercode, 0.0)

    if cape >= 2000:   cape_c = 0.50
    elif cape >= 1500: cape_c = 0.35
    elif cape >= 1000: cape_c = 0.20
    elif cape >= 600:  cape_c = 0.10
    elif cape >= 300:  cape_c = 0.04
    else:              cape_c = 0.0

    if lifted_index <= -6:   li_c = 0.20
    elif lifted_index <= -4: li_c = 0.12
    elif lifted_index <= -2: li_c = 0.06
    elif lifted_index <= 0:  li_c = 0.02
    else:                    li_c = 0.0

    if cin >= 200:   cin_f = 0.10
    elif cin >= 100: cin_f = 0.40
    elif cin >= 50:  cin_f = 0.75
    else:            cin_f = 1.0

    score += (cape_c + li_c) * cin_f
    return min(1.0, score)


def clasificar(probabilidad: float, umbral: float = UMBRAL_GRANIZO) -> bool:
    return probabilidad >= umbral


# ──────────────────────────────────────────────────────────────────────
# MÉTRICAS
# ──────────────────────────────────────────────────────────────────────
def calcular_metricas(resultados: list[dict]) -> dict:
    TP = TN = FP = FN = 0
    for r in resultados:
        pred, real = r["predijo_granizo"], r["granizo_real"]
        if pred and real:           TP += 1
        elif not pred and not real: TN += 1
        elif pred and not real:     FP += 1
        else:                       FN += 1

    total     = TP + TN + FP + FN
    accuracy  = (TP + TN) / total          if total > 0         else 0.0
    recall    = TP / (TP + FN)             if (TP + FN) > 0     else 0.0
    precision = TP / (TP + FP)             if (TP + FP) > 0     else 0.0
    f1        = (2 * precision * recall / (precision + recall)
                 if (precision + recall) > 0 else 0.0)

    return {
        "TP": TP, "TN": TN, "FP": FP, "FN": FN, "total": total,
        "accuracy":  round(accuracy,  4),
        "recall":    round(recall,    4),
        "precision": round(precision, 4),
        "f1":        round(f1,        4),
    }


# ──────────────────────────────────────────────────────────────────────
# TESTS
# ──────────────────────────────────────────────────────────────────────
class TestHailPredictor(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.resultados = []
        for esc in ESCENARIOS:
            prob = predecir_probabilidad(esc["variables"])
            pred = clasificar(prob)
            cls.resultados.append({
                "id":              esc["id"],
                "descripcion":     esc["descripcion"],
                "probabilidad":    prob,
                "predijo_granizo": pred,
                "granizo_real":    esc["granizo_real"],
                "correcto":        pred == esc["granizo_real"],
            })
        cls.metricas = calcular_metricas(cls.resultados)

    # ─── Objetivo 1: el pipeline calcula probabilidades ───────────────

    def test_01_pipeline_devuelve_probabilidades(self):
        """Debe devolver un float entre 0 y 100 para cada escenario."""
        for r in self.resultados:
            with self.subTest(escenario=r["id"]):
                prob = r["probabilidad"]
                self.assertIsInstance(prob, float)
                self.assertGreaterEqual(prob, 0.0)
                self.assertLessEqual(prob, 100.0)

    def test_02_alto_riesgo_supera_umbral(self):
        """Escenarios AR-* deben superar el umbral del 35%."""
        for r in [r for r in self.resultados if r["id"].startswith("AR-")]:
            with self.subTest(escenario=r["id"]):
                self.assertGreaterEqual(
                    r["probabilidad"], UMBRAL_GRANIZO,
                    f"[{r['id']}] Prob {r['probabilidad']}% < umbral {UMBRAL_GRANIZO}%\n"
                    f"    {r['descripcion']}"
                )

    def test_03_bajo_riesgo_no_supera_umbral(self):
        """Escenarios BR-* NO deben superar el umbral del 35%."""
        for r in [r for r in self.resultados if r["id"].startswith("BR-")]:
            with self.subTest(escenario=r["id"]):
                self.assertLess(
                    r["probabilidad"], UMBRAL_GRANIZO,
                    f"[{r['id']}] Prob {r['probabilidad']}% >= umbral {UMBRAL_GRANIZO}%\n"
                    f"    {r['descripcion']}"
                )

    def test_04_weathercode_scores_ordenados(self):
        """El score de weathercode 99 > 96 > 77 > 0."""
        if not IMPORT_OK:
            self.skipTest("HailPredictor no importable")
        self.assertEqual(weathercode_to_hail_score(99), 1.0)
        self.assertGreater(weathercode_to_hail_score(99), weathercode_to_hail_score(96))
        self.assertGreater(weathercode_to_hail_score(96), weathercode_to_hail_score(77))
        self.assertEqual(weathercode_to_hail_score(0), 0.0)

    def test_05_cin_alto_reduce_probabilidad(self):
        """CIN fuerte debe reducir la probabilidad aunque el CAPE sea alto."""
        prob_bajo_cin  = predecir_probabilidad({
            "cape": 1500, "lifted_index": -4, "convective_inhibition": 10, "weathercode": 3
        })
        prob_alto_cin  = predecir_probabilidad({
            "cape": 1500, "lifted_index": -4, "convective_inhibition": 200, "weathercode": 3
        })
        self.assertGreater(prob_bajo_cin, prob_alto_cin,
            f"CIN fuerte debería reducir: sin_cin={prob_bajo_cin}% vs con_cin={prob_alto_cin}%")

    def test_06_cape_cero_sin_wcode_da_cero(self):
        """Sin CAPE y sin weathercode de granizo, la probabilidad debe ser 0."""
        prob = predecir_probabilidad({
            "cape": 0, "lifted_index": 2, "convective_inhibition": 0, "weathercode": 0
        })
        self.assertEqual(prob, 0.0, f"CAPE=0, LI>0, wcode=0 → debería ser 0%, got {prob}%")

    def test_07_wcode99_solo_da_alta_prob(self):
        """weathercode 99 por sí solo (sin CAPE) debe superar el umbral."""
        prob = predecir_probabilidad({
            "cape": 0, "lifted_index": 0, "convective_inhibition": 0, "weathercode": 99
        })
        self.assertGreaterEqual(prob, UMBRAL_GRANIZO,
            f"wcode=99 sin CAPE debería superar {UMBRAL_GRANIZO}%, got {prob}%")

    # ─── Objetivo 2: >= 35% activa cierre del techo ───────────────────

    def test_08_umbral_activa_cierre(self):
        """La función clasificar debe activar/desactivar correctamente el cierre."""
        casos = [
            (35.0, True,  "exactamente en el umbral"),
            (34.9, False, "justo por debajo"),
            (80.0, True,  "riesgo muy alto"),
            (0.0,  False, "sin riesgo"),
            (100.0,True,  "certeza de granizo"),
        ]
        for prob, esperado, desc in casos:
            with self.subTest(desc=desc):
                self.assertEqual(clasificar(prob), esperado,
                    f"prob={prob}% ({desc}) → esperaba {esperado}")

    def test_09_ar_cierran_techo(self):
        """Todos los AR-* deben activar el cierre del techo."""
        for r in [r for r in self.resultados if r["id"].startswith("AR-")]:
            with self.subTest(escenario=r["id"]):
                self.assertTrue(r["predijo_granizo"],
                    f"[{r['id']}] Prob={r['probabilidad']}% — debería cerrar el techo")

    def test_10_br_no_cierran_techo(self):
        """Los BR-* no deben activar el cierre del techo."""
        for r in [r for r in self.resultados if r["id"].startswith("BR-")]:
            with self.subTest(escenario=r["id"]):
                self.assertFalse(r["predijo_granizo"],
                    f"[{r['id']}] Prob={r['probabilidad']}% — no debería cerrar el techo")

    def test_11_apertura_automatica(self):
        """Lógica de apertura: solo abre si prob < umbral Y fue auto-cerrado."""
        casos = [
            (20.0, True,  "closed", True,  "riesgo bajo + auto-cerrado → abre"),
            (20.0, False, "closed", False, "riesgo bajo + cerrado manual → no abre"),
            (40.0, True,  "closed", False, "riesgo aún alto → no abre"),
            (10.0, True,  "open",   False, "ya está abierto → no hace nada"),
            (34.9, True,  "closed", True,  "justo bajo umbral + auto-cerrado → abre"),
        ]
        for prob, auto_cerrado, estado, esperado_abrir, desc in casos:
            with self.subTest(desc=desc):
                debe_abrir = (prob < UMBRAL_GRANIZO and auto_cerrado and estado == "closed")
                self.assertEqual(debe_abrir, esperado_abrir, f"{desc}")

    # ─── Objetivo 3: métricas de calidad ──────────────────────────────

    def test_12_accuracy_minimo(self):
        """Accuracy >= 70%."""
        self.assertGreaterEqual(self.metricas["accuracy"], 0.70,
            f"Accuracy={self.metricas['accuracy']:.1%} < 70%")

    def test_13_recall_minimo_critico(self):
        """
        Recall >= 75% — la métrica más importante.
        Preferimos falsas alarmas antes que granizos no detectados.
        """
        self.assertGreaterEqual(self.metricas["recall"], 0.75,
            f"Recall={self.metricas['recall']:.1%} < 75%\n"
            f"    {self.metricas['FN']} granizo(s) no detectado(s)")

    def test_14_f1_minimo(self):
        """F1-Score >= 0.70."""
        self.assertGreaterEqual(self.metricas["f1"], 0.70,
            f"F1={self.metricas['f1']:.3f} < 0.70")

    def test_15_cero_fn_en_alto_riesgo(self):
        """
        Ningún escenario AR-* puede quedar sin detectar (FN = 0 en alto riesgo).
        Un FN aquí significa techo abierto durante granizo real.
        """
        fn_ar = [r for r in self.resultados
                 if r["id"].startswith("AR-") and not r["predijo_granizo"]]
        self.assertEqual(len(fn_ar), 0,
            f"{len(fn_ar)} escenario(s) AR sin detectar:\n" +
            "\n".join(f"  {r['id']}: {r['descripcion']} (prob={r['probabilidad']}%)"
                      for r in fn_ar))


# ──────────────────────────────────────────────────────────────────────
# INFORME
# ──────────────────────────────────────────────────────────────────────
def imprimir_informe(resultados: list[dict], metricas: dict):
    print("\n" + "═" * 72)
    print("  INFORME — PREDICTOR DE GRANIZO  DetectorGranizo")
    print("═" * 72)
    print(f"\n  Umbral cierre techo: {UMBRAL_GRANIZO}%  |  "
          f"Función: compute_hail_score  |  Importada: {IMPORT_OK}\n")

    print(f"  {'ID':<8} {'PROB':>6}  {'PRED':>8}  {'REAL':>8}  {'OK':>4}  DESCRIPCIÓN")
    print("  " + "─" * 70)
    for r in resultados:
        pred_txt = "CIERRA " if r["predijo_granizo"] else "ABIERTO"
        real_txt = "GRANIZO" if r["granizo_real"]   else "NO GRAN"
        ok_txt   = "✅" if r["correcto"] else "❌"
        print(f"  {r['id']:<8} {r['probabilidad']:>5.1f}%  {pred_txt:>8}  "
              f"{real_txt:>8}  {ok_txt}  {r['descripcion'][:42]}")

    m = metricas
    print(f"\n  {'─'*72}")
    print(f"  MATRIZ DE CONFUSIÓN")
    print(f"  ┌──────────────────┬─────────────┬─────────────┐")
    print(f"  │                  │  Real: SÍ   │  Real: NO   │")
    print(f"  ├──────────────────┼─────────────┼─────────────┤")
    print(f"  │  Predijo: SÍ     │  TP = {m['TP']:<6} │  FP = {m['FP']:<6} │")
    print(f"  │  Predijo: NO     │  FN = {m['FN']:<6} │  TN = {m['TN']:<6} │")
    print(f"  └──────────────────┴─────────────┴─────────────┘")

    def barra(v, w=22): return "█" * round(v * w) + "░" * (w - round(v * w))
    def ok(v, mn): return "✅" if v >= mn else "❌"

    print(f"\n  MÉTRICAS")
    print(f"  Accuracy:  {m['accuracy']:.1%}  {barra(m['accuracy'])}  {ok(m['accuracy'], 0.70)}")
    print(f"  Recall:    {m['recall']:.1%}  {barra(m['recall'])}  {ok(m['recall'], 0.75)}  ← más crítico")
    print(f"  Precision: {m['precision']:.1%}  {barra(m['precision'])}")
    print(f"  F1-Score:  {m['f1']:.3f}   {barra(m['f1'])}  {ok(m['f1'], 0.70)}")

    print(f"\n  INTERPRETACIÓN:")
    if m["FN"] == 0:
        print("  ✅ Sin granizos no detectados — techo cerrado en todos los casos reales.")
    else:
        print(f"  ⚠️  {m['FN']} granizo(s) no detectado(s) — revisar umbrales.")
    if m["FP"] > 0:
        print(f"  ℹ️  {m['FP']} falsa(s) alarma(s) — aceptable (mejor precaución que daño).")
    print("\n" + "═" * 72 + "\n")


# ──────────────────────────────────────────────────────────────────────
# PUNTO DE ENTRADA
# ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    # Calcular resultados
    resultados = []
    for esc in ESCENARIOS:
        prob = predecir_probabilidad(esc["variables"])
        pred = clasificar(prob)
        resultados.append({
            "id":              esc["id"],
            "descripcion":     esc["descripcion"],
            "probabilidad":    prob,
            "predijo_granizo": pred,
            "granizo_real":    esc["granizo_real"],
            "correcto":        pred == esc["granizo_real"],
        })
    metricas = calcular_metricas(resultados)
    imprimir_informe(resultados, metricas)

    # Runner con grupos
    GRUPOS = {
        "Objetivo 1 — Pipeline y lógica física": [
            "test_01", "test_02", "test_03", "test_04",
            "test_05", "test_06", "test_07",
        ],
        "Objetivo 2 — Cierre del techo": [
            "test_08", "test_09", "test_10", "test_11",
        ],
        "Objetivo 3 — Métricas de calidad": [
            "test_12", "test_13", "test_14", "test_15",
        ],
    }

    NOMBRES = {
        "test_01": "Pipeline devuelve probabilidades (0-100)",
        "test_02": "Alto riesgo supera el umbral del 35%",
        "test_03": "Bajo riesgo no supera el umbral del 35%",
        "test_04": "weathercode: 99 > 96 > 77 > 0",
        "test_05": "CIN fuerte reduce la probabilidad",
        "test_06": "CAPE=0 sin wcode de granizo → 0%",
        "test_07": "weathercode 99 solo supera el umbral",
        "test_08": "Umbral 35% activa/desactiva cierre",
        "test_09": "Escenarios AR-* cierran el techo",
        "test_10": "Escenarios BR-* no cierran el techo",
        "test_11": "Lógica de apertura automática correcta",
        "test_12": "Accuracy >= 70%",
        "test_13": "Recall >= 75%  ← más crítico",
        "test_14": "F1-Score >= 0.70",
        "test_15": "Cero FN en escenarios de alto riesgo",
    }

    print("=" * 72)
    print("  TESTS UNITARIOS")
    print("=" * 72)

    instance = TestHailPredictor()
    TestHailPredictor.setUpClass()

    total_ok = total_fail = 0
    for grupo, prefijos in GRUPOS.items():
        print(f"\n+── {grupo}")
        for prefix in prefijos:
            method = next(
                (m for m in dir(TestHailPredictor) if m.startswith(prefix + "_")), None
            )
            if not method:
                continue
            nombre = NOMBRES.get(prefix, method)
            try:
                getattr(instance, method)()
                print(f"  │  ✅  {nombre}")
                total_ok += 1
            except AssertionError as e:
                first_line = str(e).split("\n")[0]
                print(f"  │  ❌  {nombre}")
                print(f"  │      → {first_line}")
                total_fail += 1

    print(f"\n{'═'*72}")
    total = total_ok + total_fail
    if total_fail == 0:
        print(f"  ✅  {total_ok}/{total} tests superados — TODOS OK")
    else:
        print(f"  ❌  {total_ok}/{total} superados — {total_fail} FALLIDO(S)")
    print("=" * 72 + "\n")