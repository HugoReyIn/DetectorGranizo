"""
OllamaAgent.py
Genera un resumen agronómico general usando un LLM local vía Ollama.

Estrategia híbrida:
  - AgroAgent (reglas if/else) → 8 textos de tarjeta, instantáneo
  - OllamaAgent (LLM local)   → 1 resumen global, asíncrono, sin coste

Modelos recomendados (instalar con `ollama pull <modelo>`):
  - llama3.2        → 3B params, ~2 GB RAM, muy bueno para español
  - gemma2:2b       → más ligero, buena calidad
  - mistral         → mejor razonamiento, ~4 GB RAM

Instalación:
  1. Descargar Ollama: https://ollama.com
  2. ollama pull llama3.2
  3. Asegurarse de que el servidor corre: ollama serve

El agente usa fallback silencioso si Ollama no está disponible.
"""

import requests
import logging

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────
# CONFIGURACIÓN
# ──────────────────────────────────────────
OLLAMA_URL    = "http://localhost:11434/api/generate"
OLLAMA_MODEL  = "llama3.2"   # cambiar según el modelo instalado
OLLAMA_TIMEOUT = 45           # segundos — los LLMs pequeños pueden tardar


def _build_prompt(data: dict, crop_type: str, card_insights: dict) -> str:
    """
    Construye el prompt con todos los datos disponibles.
    Los card_insights del AgroAgent se incluyen como contexto
    para que el LLM pueda hacer referencia a ellos sin repetirlos.
    """
    crop_name = crop_type or "cultivo genérico"

    # Formatear datos numéricos con unidades legibles
    et0      = f"{data.get('et0_today')} mm/día"       if data.get('et0_today')       is not None else "no disponible"
    uv       = f"{data.get('uv_max_today')}"            if data.get('uv_max_today')    is not None else "no disponible"
    pressure = f"{data.get('pressure')} hPa"            if data.get('pressure')        is not None else "no disponible"
    rad      = f"{data.get('solar_radiation')} W/m²"    if data.get('solar_radiation') is not None else "no disponible"
    soil_m   = f"{round(data.get('soil_moisture_0', 0) * 100, 1)}%" if data.get('soil_moisture_0') is not None else "no disponible"
    soil_t   = f"{data.get('soil_temp_surface')} °C"    if data.get('soil_temp_surface') is not None else "no disponible"
    cold_h   = f"{data.get('cold_hours_24h')}h"         if data.get('cold_hours_24h')  is not None else "no disponible"
    hail_r   = f"{data.get('hail_risk_6h', 0):.0f}%"
    rain_24h = f"{data.get('rain_24h', 0)} mm"
    rain_7d  = f"{data.get('rain_7d', 0)} mm"
    et0_7d   = f"{data.get('et0_7d', 0)} mm"
    balance  = f"{data.get('water_balance_7d', 0)} mm"
    fungus   = ["bajo", "moderado", "alto"][min(data.get('fungus_risk', 0), 2)]
    tmax     = f"{data.get('temp_max_today')} °C"       if data.get('temp_max_today')  is not None else "no disponible"
    tmin     = f"{data.get('temp_min_today')} °C"       if data.get('temp_min_today')  is not None else "no disponible"
    vpd      = f"{data.get('vpd')} kPa"                 if data.get('vpd')             is not None else "no disponible"

    # Resumen de alertas de los cards para dar contexto al LLM
    cards_ctx = "\n".join(
        f"  - {k}: {v}"
        for k, v in (card_insights or {}).items()
        if v and "no disponible" not in v.lower()
    )

    return f"""Eres un agrónomo experto y conciso. Analiza los siguientes datos meteorológicos y agronómicos para una parcela de {crop_name} y genera un resumen ejecutivo práctico.

DATOS ACTUALES:
- ET₀ hoy: {et0}
- Lluvia 24h: {rain_24h} | Lluvia 7 días: {rain_7d}
- Balance hídrico 7d (lluvia - ET₀): {balance}
- Temperatura: {tmin} / {tmax}
- UV máx: {uv}
- Presión atmosférica: {pressure}
- Radiación solar: {rad}
- VPD: {vpd}
- Humedad suelo (0-1cm): {soil_m}
- Temperatura suelo: {soil_t}
- Horas de frío últimas 24h: {cold_h}
- Riesgo granizo próximas 6h: {hail_r}
- Riesgo de hongos (mildiu/botrytis): {fungus}
- ET₀ acumulada 7 días: {et0_7d}

DIAGNÓSTICO PREVIO POR INDICADOR:
{cards_ctx if cards_ctx else "  (no disponible)"}

INSTRUCCIONES:
1. Identifica el factor más crítico para este cultivo HOY.
2. Da 2-3 recomendaciones concretas y accionables (riego, tratamientos, labores).
3. Menciona si hay algún riesgo inminente que requiera atención urgente.
4. Usa lenguaje directo, sin tecnicismos innecesarios. Sin listas con guiones, escribe en prosa fluida.
5. Máximo 4 frases. No repitas los datos numéricos ya listados.
6. Responde en español."""


def get_agro_summary(data: dict, crop_type: str,
                     card_insights: dict | None = None) -> dict:
    """
    Genera un resumen agronómico usando el LLM local (Ollama).

    Returns:
        {
            "summary":   str   — resumen generado por el LLM,
            "model":     str   — modelo usado,
            "available": bool  — False si Ollama no está disponible,
            "error":     str   — mensaje de error si falla (opcional)
        }
    """
    prompt = _build_prompt(data, crop_type, card_insights or {})

    try:
        response = requests.post(
            OLLAMA_URL,
            json={
                "model":  OLLAMA_MODEL,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0.3,   # respuestas más consistentes y precisas
                    "num_predict": 250,   # máximo ~250 tokens de salida
                }
            },
            timeout=OLLAMA_TIMEOUT,
        )
        response.raise_for_status()
        result = response.json()
        summary_text = result.get("response", "").strip()

        if not summary_text:
            return {"summary": None, "model": OLLAMA_MODEL,
                    "available": True, "error": "Respuesta vacía del modelo"}

        logger.info("[OllamaAgent] Resumen generado (%d chars) con %s",
                    len(summary_text), OLLAMA_MODEL)

        return {
            "summary":   summary_text,
            "model":     OLLAMA_MODEL,
            "available": True,
        }

    except requests.exceptions.ConnectionError:
        logger.warning("[OllamaAgent] Ollama no está disponible en %s", OLLAMA_URL)
        return {
            "summary":   None,
            "model":     OLLAMA_MODEL,
            "available": False,
            "error":     "Ollama no está en ejecución. Inicia el servidor con: ollama serve",
        }

    except requests.exceptions.Timeout:
        logger.warning("[OllamaAgent] Timeout tras %ds", OLLAMA_TIMEOUT)
        return {
            "summary":   None,
            "model":     OLLAMA_MODEL,
            "available": True,
            "error":     f"El modelo tardó más de {OLLAMA_TIMEOUT}s. Prueba con un modelo más ligero (gemma2:2b).",
        }

    except Exception as e:
        logger.error("[OllamaAgent] Error inesperado: %s", e)
        return {
            "summary":   None,
            "model":     OLLAMA_MODEL,
            "available": False,
            "error":     str(e),
        }


def check_ollama_status() -> dict:
    """Comprueba si Ollama está disponible y qué modelos hay instalados."""
    try:
        r = requests.get("http://localhost:11434/api/tags", timeout=5)
        r.raise_for_status()
        models = [m["name"] for m in r.json().get("models", [])]
        return {"available": True, "models": models}
    except Exception:
        return {"available": False, "models": []}