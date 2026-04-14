"""
services/ai/interpreter.py

Interpretación narrativa opcional del EvaluationResult.

Regla central:
la IA no calcula química ni altera números. Solo transforma resultados ya
calculados en una explicación farmacológica prudente.
"""

from __future__ import annotations

from typing import Any

try:
    import anthropic  # type: ignore
except Exception:  # pragma: no cover - depende del entorno
    anthropic = None

from core.config import get_settings
from core.exceptions import AIServiceError
from core.models import AIReportRequest, MutationType, PhysicochemicalProperties, ScoreBreakdown
from utils.logger import get_logger

settings = get_settings()
log = get_logger(__name__)

# Singleton del cliente Anthropic. Se crea una sola vez para reutilizar
# el pool de conexiones HTTP entre llamadas al servicio de IA.
_anthropic_client = None


def _get_anthropic_client():
    """Lazy initialization del cliente Anthropic."""
    global _anthropic_client
    if _anthropic_client is None and anthropic is not None and settings.anthropic_api_key:
        _anthropic_client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
    return _anthropic_client


def build_ai_prompt(request: AIReportRequest) -> str:
    mutation_context = (
        f"Mutación aplicada: {request.mutation_type.value}."
        if request.mutation_type is not None
        else "Mutación aplicada: no especificada."
    )
    parent_context = (
        f"SMILES padre: {request.parent_smiles}."
        if request.parent_smiles
        else "No hay molécula padre para comparación."
    )

    return f"""
Eres un intérprete científico farmacológico de MolDesign.

REGLAS OBLIGATORIAS:
- No alteres ningún valor numérico.
- No inventes propiedades no calculadas.
- No presentes docking como validación experimental.
- Distingue observación, interpretación e hipótesis.
- Usa lenguaje prudente: 'sugiere', 'podría indicar', 'merece evaluación adicional'.
- No uses lenguaje como 'demuestra', 'confirma eficacia' o 'garantiza actividad'.

DATOS DE ENTRADA:
- Molécula (SMILES): {request.molecule_smiles}
- Target: {request.target_name}
- Afinidad de docking: {request.affinity_kcal} kcal/mol
- Score de afinidad: {request.affinity_score}/100
- Score ADME: {request.score_breakdown.adme_score}/100
- Score drug-likeness: {request.score_breakdown.druglikeness_score}/100
- Score total: {request.score_breakdown.total_score}/100
- Propiedades: MW={request.properties.molecular_weight} Da, logP={request.properties.log_p}, TPSA={request.properties.tpsa} Å², HBD={request.properties.hbd}, HBA={request.properties.hba}, RotBonds={request.properties.rotatable_bonds}
- Lipinski pass: {request.properties.lipinski_pass}
- Veber pass: {request.properties.veber_pass}
- Dimensión más fuerte: {request.score_breakdown.strongest_dimension}
- Dimensión más débil: {request.score_breakdown.weakest_dimension}
- Hint de mejora: {request.score_breakdown.improvement_hint}
- {mutation_context}
- {parent_context}

FORMATO DE SALIDA:
1. Observación breve del resultado computacional.
2. Interpretación fisicoquímica/ADME.
3. Limitaciones y cautelas metodológicas.
4. Hipótesis de siguiente paso.
""".strip()


async def generate_ai_report(request: AIReportRequest) -> str | None:
    """
    Genera reporte IA si el entorno lo soporta; si no, retorna None.

    Este comportamiento es deliberado: la capa IA no debe bloquear el pipeline.
    """
    if not settings.anthropic_api_key:
        log.info("IA no configurada: ANTHROPIC_API_KEY ausente")
        return None

    if anthropic is None:
        log.warning("anthropic SDK no disponible; degradando ai_report=None")
        return None

    prompt = build_ai_prompt(request)

    try:
        client = _get_anthropic_client()
        if client is None:
            log.warning("no se pudo crear cliente Anthropic; degradando ai_report=None")
            return None

        message = await client.messages.create(
            model=settings.anthropic_model,
            max_tokens=settings.anthropic_max_tokens,
            messages=[
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
        )

        parts = getattr(message, "content", [])
        text_parts = [getattr(part, "text", "") for part in parts if getattr(part, "text", "")]
        report = "\n".join(text_parts).strip()
        return report or None

    except Exception as e:
        raise AIServiceError(detail=str(e)) from e


async def safe_generate_ai_report(request: AIReportRequest) -> str | None:
    try:
        return await generate_ai_report(request)
    except AIServiceError as e:
        log.warning("falló generación de reporte IA; degradando", detail=e.detail)
        return None
