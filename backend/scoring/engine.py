"""
scoring/engine.py

Motor de score compuesto del MVP.

Combina:
- Ligand Efficiency (LE) o Afinidad absoluta
- QED (Quantitative Estimate of Drug-likeness) para propiedades fisicoquímicas

El resultado es una métrica de priorización basada en estándares de la industria.
"""

from __future__ import annotations

import uuid
from typing import Any

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
    # Como adme_score y druglikeness_score son iguales (QED), agrupamos
    dimensions = {
        "afinidad (LE)": affinity_score,
        "propiedades (QED)": adme_score,
    }
    strongest = max(dimensions, key=dimensions.get)
    weakest = min(dimensions, key=dimensions.get)
    return strongest, weakest


def _build_improvement_hint(
    properties: PhysicochemicalProperties,
    weakest_dimension: str,
) -> str:
    if weakest_dimension == "afinidad (LE)":
        return (
            "La Eficiencia de Ligando es baja. Considera optimizar los contactos "
            "existentes antes de añadir más peso molecular."
        )

    # Si QED es la más débil
    if properties.qed < 0.5:
        if properties.molecular_weight > 500:
            return "El QED es bajo. Intenta reducir el peso molecular para mejorar el perfil general."
        if properties.log_p > 5:
            return "El QED es bajo. Reduce la lipofilia (logP) para mejorar la viabilidad."
        if properties.tpsa > 140:
            return "El QED es bajo. La polaridad excesiva (TPSA) está reduciendo el score."
        return "El QED es bajo. Revisa la complejidad estructural de la molécula."

    return (
        "El perfil general es muy bueno. Cualquier mejora futura debería priorizar "
        "la optimización del ajuste estérico sin degradar el QED."
    )


def calculate_score_breakdown(
    docking: DockingResult,
    properties: PhysicochemicalProperties,
    is_control: bool = False,
    target_hotspots: list[dict] | None = None,
) -> ScoreBreakdown:
    """Calcula el breakdown completo del score para una evaluación."""
    
    # Afinidad ahora evalúa Ligand Efficiency (LE) y Lipophilic Efficiency (LLE)
    affinity_score = normalize_affinity(
        docking.best_affinity, 
        properties.heavy_atom_count,
        properties.log_p
    )
    
    # Ambos scores usan QED internamente (Bickerton 2012)
    adme_score = calculate_adme_score(properties)
    druglikeness_score = calculate_druglikeness_score(properties)
    
    # --- [NUEVO] Score de Especificidad Biológica ---
    specificity_score = 100.0
    specificity_multiplier = 1.0
    
    if target_hotspots:
        # Calcular cuánto de los hotspots se cubrieron
        total_importance = sum(h.get("importance", 1.0) for h in target_hotspots)
        hits_importance = 0.0
        
        hit_names = set(docking.hotspots_hit or [])
        for h in target_hotspots:
            if h["name"].upper() in hit_names:
                hits_importance += h.get("importance", 1.0)
        
        if total_importance > 0:
            specificity_score = (hits_importance / total_importance) * 100
        
        # El multiplicador reduce el score final si la especificidad es baja.
        # Rango: 0.5 (si hit=0) a 1.0 (si hit=total).
        specificity_multiplier = 0.5 + (0.5 * specificity_score / 100.0)

    # El score físico es esencialmente el QED ponderado
    physico_score = (adme_score * settings.score_weight_adme) + (druglikeness_score * settings.score_weight_druglikeness)
    
    # Penalizador suavizado: la afinidad aporta su peso, pero también modula la utilidad de las propiedades
    # Si la afinidad es muy baja (no une), las propiedades perfectas no sirven de mucho.
    # v4: Más estricto. Si affinity_score < 20, el multiplicador cae drásticamente.
    if affinity_score < 20:
        # Rango [0.1, 0.5]. Si es 0, las propiedades solo valen un 10%.
        affinity_multiplier = (affinity_score / 20.0) * 0.4 + 0.1
    else:
        # Rango [0.5, 1.0].
        affinity_multiplier = ((affinity_score - 20) / 80.0) * 0.5 + 0.5
    
    if is_control:
        # Si es ligando de control endógeno, ignorar propiedades fisicoquímicas
        total_score = clamp_score(affinity_score)
    else:
        # El score base se multiplica por la especificidad
        base_score = (affinity_score * settings.score_weight_affinity) + (physico_score * affinity_multiplier)
        total_score = clamp_score(base_score * specificity_multiplier)

    strongest, weakest = _pick_dimensions(
        affinity_score,
        adme_score,
        druglikeness_score,
    )

    # Calcular LE y LLE bruta para pasarla al frontend
    le_raw = round(docking.best_affinity / properties.heavy_atom_count, 3) if properties.heavy_atom_count else None
    lle_raw = round((-docking.best_affinity) - properties.log_p, 3) if properties.log_p is not None else None

    return ScoreBreakdown(
        affinity_score=affinity_score,
        adme_score=adme_score,
        druglikeness_score=druglikeness_score,
        total_score=total_score,
        specificity_score=specificity_score,
        ligand_efficiency=le_raw,
        lipophilic_efficiency=lle_raw,
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
        # Obtenemos el resultado previo para saber si es control
        result = await repository.get_evaluation_result(molecule_id)
        is_control = bool(result.is_control) if result else False

        breakdown = calculate_score_breakdown(docking, properties, is_control=is_control)
        await repository.upsert_evaluation_result(
            molecule_id=molecule_id,
            properties=properties,
            docking=docking,
            scores=breakdown.model_dump(),
            is_control=is_control,
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
        "ligand_efficiency": float(breakdown.ligand_efficiency) if breakdown.ligand_efficiency else None,
        "lipophilic_efficiency": float(breakdown.lipophilic_efficiency) if breakdown.lipophilic_efficiency is not None else None,
        "strongest_dimension": str(breakdown.strongest_dimension),
        "weakest_dimension": str(breakdown.weakest_dimension),
        "improvement_hint": str(breakdown.improvement_hint),
    }

