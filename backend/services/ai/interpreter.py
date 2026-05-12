"""
services/ai/interpreter.py

Interpretación narrativa opcional del EvaluationResult usando Google Gemini 1.5 Flash.

Regla central:
la IA no calcula química ni altera números. Solo transforma resultados ya
calculados en una explicación farmacológica prudente.
"""

from __future__ import annotations

from typing import Any
import httpx
import anthropic

from core.config import get_settings
from core.exceptions import AIServiceError
from core.models import AIReportRequest
from utils.logger import get_logger

settings = get_settings()
log = get_logger(__name__)

def build_ai_prompt(request: AIReportRequest) -> str:
    data_json = request.model_dump_json(indent=2)

    return f"""Escribe un reporte científico BREVE y DIRECTO para la molécula {request.molecule_smiles}. 
Tu análisis debe ser conciso, enfocándose únicamente en la información más útil para un investigador que busca optimizar este compuesto.

DATOS DEL MOTOR DE EVALUACIÓN (JSON):
```json
{data_json}
```

GUÍA DE REDACCIÓN:
- Redacta máximo 2 párrafos concisos (no más de 150 palabras en total).
- Analiza brevemente la información del JSON proporcionado.
- CONTRASTA Y CONTEXTUALIZA estos resultados con información general y literatura científica ("lo que se sabe al respecto" sobre la interacción entre compuestos similares y el target {request.target_name}).
- Proporciona una justificación química directa para la optimización sugerida.
- NO uses introducciones ni presentaciones. Sé directo y profesional.

EMPIEZA TU ANÁLISIS DIRECTAMENTE CON ESTAS PALABRAS:
"El análisis del complejo ligando-receptor revela que..."

REPORTE DETALLADO:""".strip()

async def generate_claude_report(request: AIReportRequest) -> str | None:
    """Genera reporte usando Claude (Anthropic)."""
    if not settings.anthropic_api_key:
        return None
    try:
        client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
        response = await client.messages.create(
            model=settings.anthropic_model,
            max_tokens=800,
            temperature=0.5,
            messages=[{"role": "user", "content": build_ai_prompt(request)}]
        )
        return response.content[0].text.strip()
    except Exception as e:
        log.warning("Fallo en Anthropic (posible falta de saldo)", error=str(e))
        return None

async def generate_gemini_report(request: AIReportRequest) -> str | None:
    """Genera reporte usando Google Gemini 1.5 Flash vía REST API."""
    if not settings.gemini_api_key:
        log.error("Clave de API de Gemini no configurada.")
        return None

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={settings.gemini_api_key}"
    payload = {
        "contents": [{
            "parts": [{"text": build_ai_prompt(request)}]
        }],
        "generationConfig": {
            "temperature": 0.5,
            "maxOutputTokens": 800
        }
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            res = await client.post(url, json=payload)
            if res.status_code != 200:
                log.error("Error en Gemini API", status=res.status_code, body=res.text)
                return None
            
            data = res.json()
            return data['candidates'][0]['content']['parts'][0]['text'].strip()
    except Exception as e:
        log.error("Excepción en Gemini API", error=str(e))
        return None

async def generate_ai_report(request: AIReportRequest) -> str | None:
    """
    Orquestador de reportes con fallback automático.
    Prioridad: Claude -> Gemini.
    """
    # Intentar con Claude primero
    report = await generate_claude_report(request)
    if report:
        log.info("Reporte generado con Claude")
        return report
    
    # Si falla o no hay saldo, intentar con Gemini
    log.info("Saltando a fallback de Gemini...")
    report = await generate_gemini_report(request)
    if report:
        log.info("Reporte generado con Gemini")
        return report

    return "No se pudo generar el reporte IA en este momento. Por favor revisa los créditos de API."

async def safe_generate_ai_report(request: AIReportRequest) -> str | None:
    try:
        return await generate_ai_report(request)
    except Exception as e:
        log.warning("Fallo total en IA", error=str(e))
        return "Error de conexión con el servicio de IA."
