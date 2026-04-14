"""
scoring/engine.py

Motor de score compuesto del MVP.

Combina:
- afinidad de docking (Vina),
- score ADME explícito,
- drug-likeness explícito.

El resultado es una heurística de priorización, no una afirmación de eficacia.
"""

from __future__ import annotations

import uuid
from typing import Any

from chem.properties import get_lipinski_violations, get_veber_violations
from core.config import get_settings
from core.exceptions import ScoringError
from core.models import DockingResult, PhysicochemicalProperties, ScoreBreakdown
from db.repository import Repository
from scoring.normalizer import (
    calculate_adme_score,
    calculate_druglikeness_score,
    clamp_score,
    normalize_affinity,
)
from utils.logger import get_logger

settings = get_settings()
log = get_logger(__name__)


def _pick_dimensions(
    affinity_score: float,
    adme_score: float,
    druglikeness_score: float,
) -> tuple[str, str]:
    dimensions = {
        "affinity": affinity_score,
        "ADME": adme_score,
        "drug-likeness": druglikeness_score,
    }
    strongest = max(dimensions, key=dimensions.get)
    weakest = min(dimensions, key=dimensions.get)
    return strongest, weakest


def _build_improvement_hint(
    properties: PhysicochemicalProperties,
    weakest_dimension: str,
) -> str:
    lipinski = get_lipinski_violations(properties)
    veber = get_veber_violations(properties)

    if weakest_dimension == "affinity":
        return (
            "La afinidad de docking es la dimensión más débil; conviene explorar "
            "modificaciones estructurales que mejoren complementariedad con el sitio activo."
        )

    if weakest_dimension == "ADME":
        if properties.log_p > 5:
            return "Reduce el logP para mejorar el balance entre permeabilidad y lipofilia."
        if properties.tpsa > 140:
            return "Reduce TPSA para favorecer absorción oral potencial."
        if properties.rotatable_bonds > 10:
            return "Reduce flexibilidad molecular para mejorar el perfil ADME heurístico."
        return "Optimiza logP, TPSA y flexibilidad para reforzar el perfil ADME."

    if lipinski or veber:
        joined = "; ".join([*lipinski, *veber])
        return f"Mejora las violaciones detectadas: {joined}."

    return (
        "El perfil general es balanceado; cualquier mejora futura debería priorizar "
        "afinidad o selectividad sin degradar el perfil fisicoquímico."
    )


def calculate_score_breakdown(
    docking: DockingResult,
    properties: PhysicochemicalProperties,
) -> ScoreBreakdown:
    """Calcula el breakdown completo del score para una evaluación."""
    affinity_score = normalize_affinity(docking.best_affinity)
    adme_score = calculate_adme_score(properties)
    druglikeness_score = calculate_druglikeness_score(properties)

    total_score = clamp_score(
        (affinity_score * settings.score_weight_affinity)
        + (adme_score * settings.score_weight_adme)
        + (druglikeness_score * settings.score_weight_druglikeness)
    )

    strongest, weakest = _pick_dimensions(
        affinity_score,
        adme_score,
        druglikeness_score,
    )

    return ScoreBreakdown(
        affinity_score=affinity_score,
        adme_score=adme_score,
        druglikeness_score=druglikeness_score,
        total_score=total_score,
        weight_affinity=settings.score_weight_affinity,
        weight_adme=settings.score_weight_adme,
        weight_druglikeness=settings.score_weight_druglikeness,
        strongest_dimension=strongest,
        weakest_dimension=weakest,
        improvement_hint=_build_improvement_hint(properties, weakest),
    )


async def score_and_persist(
    repository: Repository,
    molecule_id: uuid.UUID,
    docking: DockingResult,
    properties: PhysicochemicalProperties,
) -> ScoreBreakdown:
    """
    Calcula el score y persiste los resultados normalizados.
    """
    try:
        breakdown = calculate_score_breakdown(docking, properties)
        await repository.upsert_evaluation_result(
            molecule_id=molecule_id,
            properties=properties,
            docking=docking,
            scores=breakdown.model_dump(),
        )
        return breakdown
    except Exception as e:
        raise ScoringError(
            molecule_id=str(molecule_id),
            detail=str(e),
        ) from e


def breakdown_to_result_dict(breakdown: ScoreBreakdown) -> dict[str, Any]:
    # Ensure all numerics are native Python types
    return {
        "affinity_score": float(breakdown.affinity_score),
        "adme_score": float(breakdown.adme_score),
        "druglikeness_score": float(breakdown.druglikeness_score),
        "total_score": float(breakdown.total_score),
        "strongest_dimension": str(breakdown.strongest_dimension),
        "weakest_dimension": str(breakdown.weakest_dimension),
        "improvement_hint": str(breakdown.improvement_hint),
    }
