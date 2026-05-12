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

import anthropic

async def generate_ai_report(request: AIReportRequest) -> str | None:
    """
    Genera reporte IA usando Anthropic (Claude).
    """
    if not settings.anthropic_api_key:
        log.error("Clave de API de Anthropic no configurada.")
        return None

    prompt = build_ai_prompt(request)
    
    try:
        client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
        
        response = await client.messages.create(
            model=settings.anthropic_model,
            max_tokens=1500,
            temperature=0.5,
            messages=[
                {"role": "user", "content": prompt}
            ]
        )
        
        report = response.content[0].text.strip()
        
        log.info(
            "Reporte IA generado vía Anthropic", 
            chars=len(report),
            model=settings.anthropic_model
        )
        return report

    except Exception as e:
        log.error("Excepción al llamar a Anthropic", error=str(e), error_type=type(e).__name__)
        return None

async def safe_generate_ai_report(request: AIReportRequest) -> str | None:
    """
    Wrapper seguro para evitar que fallos en la IA bloqueen el pipeline de evaluación.
    """
    try:
        return await generate_ai_report(request)
    except Exception as e:
        log.warning("Fallo silencioso en generación de reporte IA", error=str(e))
        return None
