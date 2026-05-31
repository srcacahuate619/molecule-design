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

import json

def build_ai_messages(request: AIReportRequest) -> list[dict]:
    smiles = request.molecule_smiles
    receptor = request.target_name
    score = round(request.score_breakdown.total_score, 1) if request.score_breakdown else "N/A"
    afinidad = round(request.affinity_kcal, 2)
    le = round(request.score_breakdown.ligand_efficiency, 3) if request.score_breakdown and request.score_breakdown.ligand_efficiency else "N/A"
    lle = round(request.score_breakdown.lipophilic_efficiency, 2) if request.score_breakdown and request.score_breakdown.lipophilic_efficiency else "N/A"
    sa_score = round(request.properties.sa_score, 2)
    hotspots = request.hotspots_hit if request.hotspots_hit else []

    system_prompt = f"""Eres un experto en química medicinal. Escribe un único párrafo analizando el potencial de la molécula como fármaco contra el receptor {receptor}, basándote ESTRICTAMENTE en el JSON proporcionado.
REGLAS CRÍTICAS:
1. NUNCA inventes números. Usa exactamente los valores del JSON.
2. Si la lista "residuos_clave_alcanzados" está vacía ([]), DEBES decir explícitamente que la molécula fracasó en tocar los hotspots.
3. No uses saludos, viñetas ni títulos. Escribe un solo párrafo continuo."""

    data = {
        "molecula": smiles,
        "score_general_sobre_100": score,
        "afinidad_kcal_mol": afinidad,
        "eficiencia_ligando_LE": le,
        "eficiencia_lipofilica_LLE": lle,
        "accesibilidad_sintetica_SA": sa_score,
        "residuos_clave_alcanzados": hotspots
    }
    
    user_prompt = f"```json\n{json.dumps(data, indent=2)}\n```"
    
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]

def build_ai_prompt(request: AIReportRequest) -> str:
    messages = build_ai_messages(request)
    return messages[0]["content"] + "\n\n" + messages[1]["content"]

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

async def generate_ollama_report(request: AIReportRequest) -> str | None:
    """Genera reporte usando Ollama localmente en el servidor Ubuntu."""
    if not settings.ollama_base_url:
        return None

    url = f"{settings.ollama_base_url.rstrip('/')}/api/chat"
    payload = {
        "model": settings.ollama_model,
        "messages": build_ai_messages(request),
        "stream": False,
        "options": {
            "temperature": 0.1,
            "num_predict": 800
        }
    }

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            res = await client.post(url, json=payload)
            if res.status_code != 200:
                log.error("Error en Ollama API", status=res.status_code, body=res.text)
                return None
            
            data = res.json()
            return data.get('message', {}).get('content', '').strip()
    except Exception as e:
        log.error("Excepción en Ollama API", error=str(e))
        return None

async def stream_ollama_report(request: AIReportRequest):
    """
    Generador asíncrono para streaming de Ollama (SSE).
    Hace yield de cada token a medida que llega.
    """
    yield "Módulo de IA desactivado temporalmente."
    return

    url = f"{settings.ollama_base_url.rstrip('/')}/api/chat"
    payload = {
        "model": settings.ollama_model,
        "messages": build_ai_messages(request),
        "stream": True,
        "options": {
            "temperature": 0.1,
            "num_predict": 800
        }
    }

    try:
        import json
        async with httpx.AsyncClient(timeout=120.0) as client:
            async with client.stream("POST", url, json=payload) as response:
                if response.status_code != 200:
                    yield "Error conectando con la IA local."
                    return
                
                async for line in response.aiter_lines():
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                        if "message" in data and "content" in data["message"]:
                            yield data["message"]["content"]
                    except json.JSONDecodeError:
                        pass
    except Exception as e:
        log.error("Excepción en Ollama API Streaming", error=str(e))
        yield "Error en la generación del reporte (Timeout/Desconexión)."

async def generate_ai_report(request: AIReportRequest) -> str | None:
    """
    Orquestador de reportes con fallback automático.
    Prioridad: Ollama (Local) -> Claude -> Gemini.
    """
    # Intentar con Ollama (Gemma3) primero
    report = await generate_ollama_report(request)
    if report:
        log.info(f"Reporte generado con Ollama ({settings.ollama_model})")
        return report

    # Si falla, intentar con Claude
    log.info("Saltando a fallback de Claude...")
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
    return "Módulo de IA desactivado temporalmente."
