"""
OllamaAgent.py
Genera los 8 textos interpretativos de las tarjetas agronómicas usando un LLM
local vía Ollama, sustituyendo los textos hardcodeados del AgroAgent.

Estrategia:
  - Una sola llamada al LLM con todos los datos → JSON con las 8 claves
  - Si Ollama no está disponible → fallback transparente al AgroAgent (reglas)
  - Temperatura 0.2 para respuestas consistentes y concretas

Modelos recomendados:
  - llama3.2      → 3B, ~2 GB RAM, muy bueno en español
  - gemma2:2b     → más ligero
  - mistral       → mejor razonamiento, ~4 GB RAM

Instalación:
  1. https://ollama.com/download
  2. ollama pull llama3.2
  3. ollama serve
"""

import json
import logging
import requests

logger = logging.getLogger(__name__)

OLLAMA_URL     = "http://localhost:11434/api/generate"
OLLAMA_MODEL   = "llama3.2"
OLLAMA_TIMEOUT = 60


# ──────────────────────────────────────────
# PROMPT
# ──────────────────────────────────────────
def _build_cards_prompt(data: dict, crop_type: str) -> str:
    crop = crop_type or "cultivo genérico"

    def _fmt(val, unit="", decimals=1):
        if val is None:
            return "no disponible"
        return f"{round(float(val), decimals)}{unit}"

    soil_pct = (
        f"{round(data.get('soil_moisture_0', 0) * 100, 0):.0f}%"
        if data.get("soil_moisture_0") is not None else "no disponible"
    )

    return f"""Eres un agrónomo experto. Analiza estos datos para una parcela de {crop} y genera exactamente 8 textos cortos de interpretación agronómica, uno por indicador.

DATOS:
- ET0 hoy: {_fmt(data.get("et0_today"), " mm/dia")}
- UV maximo hoy: {_fmt(data.get("uv_max_today"))}
- Presion atmosferica: {_fmt(data.get("pressure"), " hPa")}
- Radiacion solar: {_fmt(data.get("solar_radiation"), " W/m2")}
- Humedad suelo 0-1cm: {soil_pct}
- Temperatura suelo superficie: {_fmt(data.get("soil_temp_surface"), " C")}
- Horas de frio ultimas 24h: {_fmt(data.get("cold_hours_24h"), "h", 0)}
- Riesgo granizo proximas 6h: {_fmt(data.get("hail_risk_6h", 0), "%", 0)}
- Lluvia 24h: {_fmt(data.get("rain_24h"), " mm")}
- Balance hidrico 7d: {_fmt(data.get("water_balance_7d"), " mm")}
- Riesgo hongos: {["bajo", "moderado", "alto"][min(int(data.get("fungus_risk", 0)), 2)]}
- Temperatura max/min hoy: {_fmt(data.get("temp_max_today"), "C")} / {_fmt(data.get("temp_min_today"), "C")}

INSTRUCCIONES:
- Cada texto debe ser una frase corta y directa (maximo 12 palabras)
- Incluye siempre una recomendacion concreta o advertencia especifica para {crop}
- Usa un emoji al inicio de cada texto
- Responde UNICAMENTE con un objeto JSON valido, sin texto adicional, sin markdown
- Las claves deben ser exactamente estas 8: et0, uv, pressure, radiation, soil, soiltemp, coldhours, hail

Responde solo con el JSON, sin nada mas:"""


# ──────────────────────────────────────────
# PARSEO SEGURO
# ──────────────────────────────────────────
_REQUIRED_KEYS = {"et0", "uv", "pressure", "radiation", "soil", "soiltemp", "coldhours", "hail"}


def _parse_cards(raw: str) -> dict | None:
    raw = raw.strip()

    # Intento directo
    try:
        parsed = json.loads(raw)
        if _REQUIRED_KEYS.issubset(parsed.keys()):
            return parsed
    except json.JSONDecodeError:
        pass

    # Extraer primer bloque {...}
    start = raw.find("{")
    end   = raw.rfind("}") + 1
    if start != -1 and end > start:
        try:
            parsed = json.loads(raw[start:end])
            if _REQUIRED_KEYS.issubset(parsed.keys()):
                return parsed
        except json.JSONDecodeError:
            pass

    logger.warning("[OllamaAgent] JSON no parseable: %s", raw[:300])
    return None


# ──────────────────────────────────────────
# TEXTOS DE TARJETA — función principal
# ──────────────────────────────────────────
def get_card_insights_llm(data: dict, crop_type: str) -> dict:
    """
    Genera los 8 textos de tarjeta con el LLM.
    Devuelve {} si Ollama no está disponible → el llamador usa AgroAgent como fallback.
    """
    prompt = _build_cards_prompt(data, crop_type)

    try:
        response = requests.post(
            OLLAMA_URL,
            json={
                "model":  OLLAMA_MODEL,
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": 0.2, "num_predict": 350},
            },
            timeout=OLLAMA_TIMEOUT,
        )
        response.raise_for_status()
        raw    = response.json().get("response", "")
        parsed = _parse_cards(raw)

        if parsed:
            logger.info("[OllamaAgent] Cards OK con %s para '%s'", OLLAMA_MODEL, crop_type)
            return parsed

        logger.warning("[OllamaAgent] JSON inválido — fallback AgroAgent")
        return {}

    except requests.exceptions.ConnectionError:
        logger.info("[OllamaAgent] No disponible — fallback AgroAgent")
        return {}
    except requests.exceptions.Timeout:
        logger.warning("[OllamaAgent] Timeout %ds — fallback AgroAgent", OLLAMA_TIMEOUT)
        return {}
    except Exception as e:
        logger.error("[OllamaAgent] Error: %s — fallback AgroAgent", e)
        return {}


# ──────────────────────────────────────────
# RESUMEN GENERAL (bloque aparte en la UI)
# ──────────────────────────────────────────
def get_agro_summary(data: dict, crop_type: str, card_insights: dict | None = None) -> dict:
    """Genera un resumen en prosa de 2-3 frases para el bloque de resumen global."""
    crop = crop_type or "cultivo genérico"

    def _fmt(val, unit="", decimals=1):
        if val is None:
            return "no disponible"
        return f"{round(float(val), decimals)}{unit}"

    cards_ctx = ""
    if card_insights:
        cards_ctx = "\n".join(
            f"  - {k}: {v.get('text', v) if isinstance(v, dict) else v}"
            for k, v in card_insights.items()
        )

    prompt = f"""Eres un agrónomo experto. Genera un resumen ejecutivo en 2-3 frases sobre el estado de una parcela de {crop}.

Datos: ET0={_fmt(data.get('et0_today'), ' mm/dia')}, lluvia 7d={_fmt(data.get('rain_7d'), ' mm')}, balance hidrico={_fmt(data.get('water_balance_7d'), ' mm')}, granizo={_fmt(data.get('hail_risk_6h', 0), '%', 0)}, hongos={["bajo","moderado","alto"][min(int(data.get('fungus_risk',0)),2)]}.
{f'Diagnostico por indicador:{chr(10)}{cards_ctx}' if cards_ctx else ''}

Escribe en espanol, en prosa directa, sin listas. Maximo 3 frases."""

    try:
        response = requests.post(
            OLLAMA_URL,
            json={
                "model":  OLLAMA_MODEL,
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": 0.3, "num_predict": 200},
            },
            timeout=OLLAMA_TIMEOUT,
        )
        response.raise_for_status()
        summary = response.json().get("response", "").strip()
        return {"summary": summary, "model": OLLAMA_MODEL, "available": True}

    except requests.exceptions.ConnectionError:
        return {"summary": None, "model": OLLAMA_MODEL, "available": False,
                "error": "Ollama no está en ejecución."}
    except Exception as e:
        return {"summary": None, "model": OLLAMA_MODEL, "available": False, "error": str(e)}


# ──────────────────────────────────────────
# STATUS
# ──────────────────────────────────────────
def check_ollama_status() -> dict:
    try:
        r = requests.get("http://localhost:11434/api/tags", timeout=5)
        r.raise_for_status()
        models = [m["name"] for m in r.json().get("models", [])]
        return {"available": True, "models": models}
    except Exception:
        return {"available": False, "models": []}