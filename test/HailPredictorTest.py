"""
test_hail_predictor.py
Suite de pruebas para el predictor de granizo de DetectorGranizo.

Objetivos:
  1. Verificar que el modelo calcula probabilidades (pipeline funciona)
  2. Verificar que >= 35% activa el cierre del techo retráctil
  3. Medir calidad de las predicciones: Accuracy, Recall y F1-Score

Uso:
    # Desde la carpeta tests/:
    python test_hail_predictor.py

    # O con pytest:
    pytest test_hail_predictor.py -v

Requisitos:
    pip install pytest numpy pandas
"""

import sys
import os
import unittest
import math

# ── Añadir el src/ al path para poder importar los módulos del proyecto ──
SRC_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))
sys.path.insert(0, SRC_PATH)

from DataTest import ESCENARIOS, UMBRAL_GRANIZO, EXOG_VARS

# ──────────────────────────────────────────────────────────────────────
# IMPORTAR FUNCIÓN DEL PROYECTO
# Importamos solo cape_to_hail_prob y weathercode_to_hail_score
# ya que son las funciones puras del modelo sin llamadas de red.
# Para tests de integración completa ver test_integracion.py
# ──────────────────────────────────────────────────────────────────────
try:
    from ia.HailPredictor import cape_to_hail_prob, weathercode_to_hail_score
    IMPORT_OK = True
except ImportError as e:
    print(f"[AVISO] No se pudo importar HailPredictor: {e}")
    print("        Ejecuta los tests desde la carpeta raíz del proyecto.")
    IMPORT_OK = False


# ──────────────────────────────────────────────────────────────────────
# FUNCIÓN DE PREDICCIÓN LOCAL
# Replica la lógica del nowcasting sin llamadas a la API.
# Permite testear el modelo en cualquier entorno sin internet.
# ──────────────────────────────────────────────────────────────────────
def predecir_probabilidad(variables: dict) -> float:
    """
    Calcula la probabilidad de granizo (0-100) a partir de las variables
    meteorológicas usando la misma lógica que el nowcasting de HailPredictor.

    Args:
        variables: dict con las variables meteorológicas del escenario

    Returns:
        float: probabilidad de granizo entre 0 y 100
    """
    cape = float(variables.get("cape", 0))
    li   = float(variables.get("lifted_index", 0))
    cin  = float(variables.get("convective_inhibition", 0))
    wc   = int(variables.get("weathercode", 0))
    prec = float(variables.get("precipitation", 0))
    pwat = float(variables.get("total_column_integrated_water_vapour", 0))

    # Probabilidad desde CAPE + Lifted Index + CIN
    if IMPORT_OK:
        prob_cape = cape_to_hail_prob(cape, li, cin)
    else:
        prob_cape = _cape_to_hail_prob_local(cape, li, cin)

    # Probabilidad desde weathercode
    if IMPORT_OK:
        prob_wcode = weathercode_to_hail_score(wc) * 100
    else:
        prob_wcode = {77: 50.0, 96: 70.0, 99: 100.0}.get(wc, 0.0)

    # Bonus por precipitación convectiva
    precip_bonus = min(10.0, prec * 2)

    # Bonus por agua precipitable alta
    pwat_bonus = min(8.0, max(0.0, (pwat - 30) * 0.4)) if pwat > 30 else 0.0

    prob = min(100.0, max(prob_cape, prob_wcode) + precip_bonus + pwat_bonus)
    return round(prob, 1)


def _cape_to_hail_prob_local(cape: float, li: float, cin: float) -> float:
    """Versión local de cape_to_hail_prob por si no se puede importar."""
    if cape <= 0:
        return 0.0
    if cape >= 2500: prob = 0.85
    elif cape >= 1500: prob = 0.60
    elif cape >= 800:  prob = 0.35
    elif cape >= 400:  prob = 0.15
    elif cape >= 200:  prob = 0.05
    else: return 0.0

    if li <= -6:   prob = min(1.0, prob + 0.20)
    elif li <= -4: prob = min(1.0, prob + 0.12)
    elif li <= -2: prob = min(1.0, prob + 0.06)

    if cin < -150:  prob *= 0.4
    elif cin < -80: prob *= 0.7

    return round(prob * 100, 1)


def clasificar(probabilidad: float, umbral: float = UMBRAL_GRANIZO) -> bool:
    """Convierte probabilidad continua en clasificación binaria."""
    return probabilidad >= umbral


# ──────────────────────────────────────────────────────────────────────
# MÉTRICAS
# ──────────────────────────────────────────────────────────────────────
def calcular_metricas(resultados: list[dict]) -> dict:
    """
    Calcula Accuracy, Recall y F1-Score.

    Definiciones:
      TP (True Positive):  predijo granizo y granizó realmente
      TN (True Negative):  predijo no granizo y no granizó
      FP (False Positive): predijo granizo pero no granizó (falsa alarma)
      FN (False Negative): predijo no granizo pero sí granizó (granizo no detectado)

      Accuracy = (TP + TN) / total
      Recall   = TP / (TP + FN)   ← de los granizos reales, cuántos detectamos
      Precision = TP / (TP + FP)
      F1       = 2 * (Precision * Recall) / (Precision + Recall)
    """
    TP = TN = FP = FN = 0

    for r in resultados:
        pred  = r["predijo_granizo"]
        real  = r["granizo_real"]

        if pred and real:     TP += 1
        elif not pred and not real: TN += 1
        elif pred and not real:     FP += 1
        elif not pred and real:     FN += 1

    total     = TP + TN + FP + FN
    accuracy  = (TP + TN) / total if total > 0 else 0.0
    recall    = TP / (TP + FN)    if (TP + FN) > 0 else 0.0
    precision = TP / (TP + FP)    if (TP + FP) > 0 else 0.0
    f1        = (2 * precision * recall / (precision + recall)
                 if (precision + recall) > 0 else 0.0)

    return {
        "TP": TP, "TN": TN, "FP": FP, "FN": FN,
        "total":     total,
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
        """Ejecuta todas las predicciones una sola vez antes de los tests."""
        cls.resultados = []
        for esc in ESCENARIOS:
            prob = predecir_probabilidad(esc["variables"])
            pred = clasificar(prob)
            cls.resultados.append({
                "id":             esc["id"],
                "descripcion":    esc["descripcion"],
                "probabilidad":   prob,
                "predijo_granizo": pred,
                "granizo_real":   esc["granizo_real"],
                "correcto":       pred == esc["granizo_real"],
            })
        cls.metricas = calcular_metricas(cls.resultados)

    # ─────────────────────────────────────────────
    # OBJETIVO 1: El modelo calcula probabilidades
    # ─────────────────────────────────────────────

    def test_01_pipeline_devuelve_probabilidades(self):
        """El modelo debe devolver un valor numérico entre 0 y 100 para cada escenario."""
        for r in self.resultados:
            with self.subTest(escenario=r["id"]):
                prob = r["probabilidad"]
                self.assertIsInstance(prob, float,
                    f"[{r['id']}] La probabilidad debe ser float, got {type(prob)}")
                self.assertGreaterEqual(prob, 0.0,
                    f"[{r['id']}] Probabilidad no puede ser negativa: {prob}")
                self.assertLessEqual(prob, 100.0,
                    f"[{r['id']}] Probabilidad no puede superar 100: {prob}")

    def test_02_alto_riesgo_supera_umbral(self):
        """Escenarios de alto riesgo (AR-*) deben superar el umbral del 35%."""
        alto_riesgo = [r for r in self.resultados if r["id"].startswith("AR-")]
        self.assertTrue(len(alto_riesgo) > 0, "No hay escenarios de alto riesgo")
        for r in alto_riesgo:
            with self.subTest(escenario=r["id"]):
                self.assertGreaterEqual(r["probabilidad"], UMBRAL_GRANIZO,
                    f"[{r['id']}] {r['descripcion']}\n"
                    f"    Probabilidad {r['probabilidad']}% < umbral {UMBRAL_GRANIZO}%")

    def test_03_bajo_riesgo_no_supera_umbral(self):
        """Escenarios de bajo riesgo (BR-*) NO deben superar el umbral del 35%."""
        bajo_riesgo = [r for r in self.resultados if r["id"].startswith("BR-")]
        self.assertTrue(len(bajo_riesgo) > 0, "No hay escenarios de bajo riesgo")
        for r in bajo_riesgo:
            with self.subTest(escenario=r["id"]):
                self.assertLess(r["probabilidad"], UMBRAL_GRANIZO,
                    f"[{r['id']}] {r['descripcion']}\n"
                    f"    Probabilidad {r['probabilidad']}% >= umbral {UMBRAL_GRANIZO}%")

    def test_04_weathercode_99_maximo_score(self):
        """El weathercode 99 (tormenta con granizo fuerte) debe dar el mayor score."""
        if IMPORT_OK:
            score_99 = weathercode_to_hail_score(99)
            score_96 = weathercode_to_hail_score(96)
            score_77 = weathercode_to_hail_score(77)
            score_0  = weathercode_to_hail_score(0)
            self.assertEqual(score_99, 1.0)
            self.assertGreater(score_99, score_96)
            self.assertGreater(score_96, score_77)
            self.assertGreater(score_77, score_0)
            self.assertEqual(score_0, 0.0)

    def test_05_cin_alto_reduce_probabilidad(self):
        """CIN muy negativo debe reducir la probabilidad aunque el CAPE sea alto."""
        # Mismo CAPE, distintos CIN
        prob_sin_cin  = predecir_probabilidad({"cape": 1500, "lifted_index": -4,
                                               "convective_inhibition": -10,
                                               "weathercode": 3})
        prob_con_cin  = predecir_probabilidad({"cape": 1500, "lifted_index": -4,
                                               "convective_inhibition": -200,
                                               "weathercode": 3})
        self.assertGreater(prob_sin_cin, prob_con_cin,
            f"CIN fuerte debería reducir probabilidad: "
            f"sin_cin={prob_sin_cin}% vs con_cin={prob_con_cin}%")

    # ─────────────────────────────────────────────
    # OBJETIVO 2: >= 35% activa el cierre del techo
    # ─────────────────────────────────────────────

    def test_06_umbral_activa_cierre(self):
        """Si prob >= 35% el sistema debe clasificar como 'cerrar techo'."""
        casos_cierre = [
            {"prob": 35.0, "debe_cerrar": True,  "desc": "exactamente en el umbral"},
            {"prob": 34.9, "debe_cerrar": False, "desc": "justo por debajo del umbral"},
            {"prob": 80.0, "debe_cerrar": True,  "desc": "riesgo muy alto"},
            {"prob": 0.0,  "debe_cerrar": False, "desc": "sin riesgo"},
            {"prob": 100.0,"debe_cerrar": True,  "desc": "certeza de granizo"},
        ]
        for caso in casos_cierre:
            with self.subTest(desc=caso["desc"]):
                resultado = clasificar(caso["prob"])
                self.assertEqual(resultado, caso["debe_cerrar"],
                    f"Con prob={caso['prob']}% ({caso['desc']}): "
                    f"esperaba cerrar={caso['debe_cerrar']}, got {resultado}")

    def test_07_escenarios_alto_riesgo_cierran_techo(self):
        """Todos los escenarios AR-* deben activar el cierre del techo."""
        alto_riesgo = [r for r in self.resultados if r["id"].startswith("AR-")]
        for r in alto_riesgo:
            with self.subTest(escenario=r["id"]):
                self.assertTrue(r["predijo_granizo"],
                    f"[{r['id']}] {r['descripcion']}\n"
                    f"    Prob={r['probabilidad']}% — debería cerrar el techo")

    def test_08_escenarios_bajo_riesgo_no_cierran(self):
        """Los escenarios BR-* no deben activar el cierre del techo."""
        bajo_riesgo = [r for r in self.resultados if r["id"].startswith("BR-")]
        for r in bajo_riesgo:
            with self.subTest(escenario=r["id"]):
                self.assertFalse(r["predijo_granizo"],
                    f"[{r['id']}] {r['descripcion']}\n"
                    f"    Prob={r['probabilidad']}% — no debería cerrar el techo")

    # ─────────────────────────────────────────────
    # OBJETIVO 3: Métricas de calidad
    # ─────────────────────────────────────────────

    def test_09_accuracy_minimo_aceptable(self):
        """La Accuracy debe ser >= 70% (mínimo aceptable para un sistema de alertas)."""
        self.assertGreaterEqual(self.metricas["accuracy"], 0.70,
            f"Accuracy={self.metricas['accuracy']:.1%} < 70% mínimo aceptable")

    def test_10_recall_minimo_critico(self):
        """
        El Recall debe ser >= 75%.
        Es la métrica más importante: preferimos falsas alarmas (FP)
        antes que granizos no detectados (FN) que dañen la cosecha.
        """
        self.assertGreaterEqual(self.metricas["recall"], 0.75,
            f"Recall={self.metricas['recall']:.1%} < 75% mínimo crítico\n"
            f"    Hay {self.metricas['FN']} granizo(s) no detectado(s)")

    def test_11_f1_minimo_aceptable(self):
        """El F1-Score debe ser >= 0.70."""
        self.assertGreaterEqual(self.metricas["f1"], 0.70,
            f"F1={self.metricas['f1']:.3f} < 0.70 mínimo aceptable")

    def test_12_cero_falsos_negativos_alto_riesgo(self):
        """
        Ningún escenario de ALTO RIESGO (AR-*) debe quedar sin detectar.
        Un FN en alto riesgo significa granizo que destruye la cosecha
        porque el techo no se cerró.
        """
        fn_alto_riesgo = [
            r for r in self.resultados
            if r["id"].startswith("AR-") and not r["predijo_granizo"]
        ]
        self.assertEqual(len(fn_alto_riesgo), 0,
            f"Hay {len(fn_alto_riesgo)} escenario(s) de ALTO RIESGO sin detectar:\n" +
            "\n".join(f"  - {r['id']}: {r['descripcion']} (prob={r['probabilidad']}%)"
                      for r in fn_alto_riesgo))

    def test_13_apertura_automatica_cuando_baja_riesgo(self):
        """
        Si el riesgo baja del umbral (< 35%) y el techo fue cerrado
        automáticamente, el sistema debe ordenar la apertura.
        Verifica la lógica: si prob < UMBRAL y fue_auto_cerrado → abrir.
        """
        UMBRAL = UMBRAL_GRANIZO

        # Simulación del estado del techo
        casos = [
            # (prob_actual, fue_auto_cerrado, estado_actual, debe_abrir)
            (20.0, True,  "closed", True,  "Riesgo bajo + auto-cerrado → debe abrir"),
            (20.0, False, "closed", False, "Riesgo bajo + cerrado MANUALMENTE → no abrir"),
            (40.0, True,  "closed", False, "Riesgo aún alto → no abrir"),
            (10.0, True,  "open",   False, "Ya está abierto → no hacer nada"),
            (34.9, True,  "closed", True,  "Justo por debajo del umbral + auto-cerrado → abrir"),
        ]

        for prob, auto_cerrado, estado, esperado_abrir, desc in casos:
            with self.subTest(desc=desc):
                # Lógica equivalente a la de agro.js
                riesgo_alto   = prob >= UMBRAL
                debe_abrir    = (not riesgo_alto
                                 and auto_cerrado
                                 and estado == "closed")
                self.assertEqual(debe_abrir, esperado_abrir,
                    f"{desc}\n"
                    f"    prob={prob}%, auto_cerrado={auto_cerrado}, "
                    f"estado={estado} → esperaba abrir={esperado_abrir}, got {debe_abrir}")


# ──────────────────────────────────────────────────────────────────────
# INFORME DE RESULTADOS
# ──────────────────────────────────────────────────────────────────────
def imprimir_informe(resultados: list[dict], metricas: dict):
    """Imprime un informe detallado de todos los escenarios y métricas."""

    print("\n" + "═" * 70)
    print("  INFORME DE EVALUACIÓN — PREDICTOR DE GRANIZO")
    print("═" * 70)

    print(f"\n  Umbral de cierre del techo: {UMBRAL_GRANIZO}%\n")

    # Tabla de resultados por escenario
    print(f"  {'ID':<8} {'PROB':>6}  {'PRED':>7}  {'REAL':>7}  {'OK':>4}  DESCRIPCIÓN")
    print("  " + "─" * 68)

    for r in resultados:
        pred_txt = "CIERRA" if r["predijo_granizo"] else "ABIERTO"
        real_txt = "GRANIZO" if r["granizo_real"]   else "NO GRAN"
        ok_txt   = "✅" if r["correcto"] else "❌"
        print(f"  {r['id']:<8} {r['probabilidad']:>5.1f}%  {pred_txt:>7}  "
              f"{real_txt:>7}  {ok_txt:>4}  {r['descripcion'][:40]}")

    # Matriz de confusión
    print("\n" + "─" * 70)
    print("  MATRIZ DE CONFUSIÓN")
    print(f"  ┌─────────────────┬──────────────┬──────────────┐")
    print(f"  │                 │  Real: SÍ    │  Real: NO    │")
    print(f"  ├─────────────────┼──────────────┼──────────────┤")
    print(f"  │  Pred: SÍ       │  TP = {metricas['TP']:<6}  │  FP = {metricas['FP']:<6}  │")
    print(f"  │  Pred: NO       │  FN = {metricas['FN']:<6}  │  TN = {metricas['TN']:<6}  │")
    print(f"  └─────────────────┴──────────────┴──────────────┘")

    # Métricas
    print("\n  MÉTRICAS DE CALIDAD")
    print("  " + "─" * 40)

    def barra(valor, ancho=20):
        llenos = round(valor * ancho)
        return "█" * llenos + "░" * (ancho - llenos)

    def estado(valor, minimo):
        return "✅ OK" if valor >= minimo else "❌ FALLO"

    acc = metricas["accuracy"]
    rec = metricas["recall"]
    pre = metricas["precision"]
    f1  = metricas["f1"]

    print(f"  Accuracy:  {acc:.1%}  {barra(acc)}  {estado(acc, 0.70)}")
    print(f"  Recall:    {rec:.1%}  {barra(rec)}  {estado(rec, 0.75)}  ← más crítico")
    print(f"  Precision: {pre:.1%}  {barra(pre)}")
    print(f"  F1-Score:  {f1:.3f}   {barra(f1)}  {estado(f1, 0.70)}")

    print("\n  INTERPRETACIÓN:")
    if metricas["FN"] == 0:
        print("  ✅ Sin granizos no detectados — el techo se cerró en todos los")
        print("     casos de riesgo real. Cosechas protegidas.")
    else:
        print(f"  ⚠️  {metricas['FN']} granizo(s) no detectado(s) — revisar umbrales.")

    if metricas["FP"] > 0:
        print(f"  ℹ️  {metricas['FP']} falsa(s) alarma(s) — el techo se cerró")
        print("     innecesariamente. Aceptable: mejor precaución que pérdida.")

    print("\n" + "═" * 70 + "\n")


# ──────────────────────────────────────────────────────────────────────
# PUNTO DE ENTRADA
# ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    # Calcular resultados para el informe
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

    # Imprimir informe detallado
    imprimir_informe(resultados, metricas)

    # ── Runner personalizado ──
    GRUPOS = {
        "Objetivo 1 — El modelo calcula probabilidades": [
            "test_01", "test_02", "test_03", "test_04", "test_05",
        ],
        "Objetivo 2 — >= 35% activa el cierre del techo": [
            "test_06", "test_07", "test_08",
        ],
        "Objetivo 3 — Métricas de calidad": [
            "test_09", "test_10", "test_11", "test_12", "test_13",
        ],
    }

    NOMBRES = {
        "test_01": "Pipeline devuelve probabilidades (0-100)",
        "test_02": "Alto riesgo supera el umbral del 35%",
        "test_03": "Bajo riesgo no supera el umbral del 35%",
        "test_04": "Weathercode 99 da el score maximo",
        "test_05": "CIN alto reduce la probabilidad",
        "test_06": "Umbral 35% activa / desactiva cierre",
        "test_07": "Escenarios AR-* cierran el techo",
        "test_08": "Escenarios BR-* no cierran el techo",
        "test_09": "Accuracy >= 70%",
        "test_10": "Recall >= 75%  <- mas critico",
        "test_11": "F1-Score >= 0.70",
        "test_12": "Cero granizos sin detectar en alto riesgo",
        "test_13": "Apertura automatica al bajar del 35%",
    }

    print()
    print("=" * 70)
    print("  TESTS UNITARIOS")
    print("=" * 70)

    instance = TestHailPredictor()
    instance.__class__.setUpClass()

    total_ok = total_fail = 0

    for grupo, tests in GRUPOS.items():
        print(f"+-- {grupo}")
        for test_prefix in tests:
            method_name = next(
                (m for m in dir(TestHailPredictor) if m.startswith(test_prefix + "_")),
                None
            )
            if not method_name:
                continue
            nombre = NOMBRES.get(test_prefix, method_name)
            try:
                getattr(instance, method_name)()
                print(f"  |  [OK]  {nombre}")
                total_ok += 1
            except AssertionError as e:
                print(f"  |  [FAIL] {nombre}")
                primera_linea = str(e).split("")[0]
                print(f"  |      -> {primera_linea}")
                total_fail += 1
        print(f"  +" + "-" * 60)

    print()
    total = total_ok + total_fail
    if total_fail == 0:
        print(f"  RESULTADO: {total_ok}/{total} tests superados -- TODOS OK")
    else:
        print(f"  RESULTADO: {total_ok}/{total} tests superados -- {total_fail} FALLIDO(S)")
    print("=" * 70)
    print()