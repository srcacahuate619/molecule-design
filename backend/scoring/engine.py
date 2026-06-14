"""
scoring/engine.py

Motor de score compuesto del MVP.

Combina:
- Ligand Efficiency (LE) o Afinidad absoluta
- QED (Quantitative Estimate of Drug-likeness) para propiedades fisicoquímicas

El resultado es una métrica de priorización basada en estándares de la industria.
"""

from __future__ import annotations

import math
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
    affinity_threshold: float = -7.5,
    specificity_floor: float = 0.5,
    gnn_score: float | None = None,
) -> ScoreBreakdown:
    """Calcula el breakdown completo del score para una evaluación.

    Args:
        gnn_score: Score de RTMScore GNN (Nivel 2). Si es None, no se aplica
                   el factor de corrección geométrica continua.
        specificity_floor: Mínimo del multiplier de especificidad (configurable
                           por target). Default 0.5; targets con hotspots muy
                           conocidos pueden bajar a 0.1 para mayor penalización.
    """
    
    # Afinidad ahora evalúa Ligand Efficiency (LE) y Lipophilic Efficiency (LLE)
    affinity_score = normalize_affinity(
        docking.best_affinity, 
        properties.heavy_atom_count,
        properties.log_p,
        threshold=affinity_threshold,
        is_control=is_control
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
        
        # El multiplicador usa el specificity_floor configurable por target.
        # Floor=0.5 (default): si no hay hits, el score baja 50%.
        # Floor=0.1: targets con hotspots críticos bien conocidos penalizan mucho más.
        specificity_floor = max(0.1, min(0.9, specificity_floor))  # clamp defensivo
        specificity_multiplier = specificity_floor + ((1.0 - specificity_floor) * specificity_score / 100.0)

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
        base_score_with_specificity = base_score * specificity_multiplier

        # --- [NUEVO] Factor GNN (RTMScore Nivel 2) Normalizado por Tamaño ---
        # En lugar de un umbral estático de 20.0, normalizamos el GNN Score por 
        # el número de átomos pesados para obtener una "Eficiencia de Ligando GNN" (GNN-LE).
        # Esto hace que la sigmoide sea independiente del tamaño del bolsillo (Escalabilidad Enterprise).
        if gnn_score is not None and properties.heavy_atom_count > 0:
            gnn_le = gnn_score / properties.heavy_atom_count
            
            # El GNN-LE típico para un buen binder suele estar entre 1.0 y 5.0.
            # Centramos la sigmoide en un GNN-LE de 2.0.
            raw_factor = 1.0 / (1.0 + math.exp(-1.5 * (gnn_le - 2.0)))
            
            # Mapear [0, 1] → [0.7, 1.15]
            gnn_factor = 0.7 + (raw_factor * 0.45)
        else:
            gnn_factor = 1.0

        total_score = clamp_score(base_score_with_specificity * gnn_factor)

    strongest, weakest = _pick_dimensions(
        affinity_score,
        adme_score,
        druglikeness_score,
    )

    # Calcular LE y LLE bruta para pasarla al frontend
    le_raw = round(docking.best_affinity / properties.heavy_atom_count, 3) if properties.heavy_atom_count else None
    lle_raw = round((-docking.best_affinity / 1.36) - properties.log_p, 3) if properties.log_p is not None else None

    return ScoreBreakdown(
        affinity_score=affinity_score,
        adme_score=adme_score,
        druglikeness_score=druglikeness_score,
        total_score=total_score,
        gnn_score=round(gnn_score, 4) if gnn_score is not None else None,
        specificity_score=specificity_score,
        ligand_efficiency=le_raw,
        lipophilic_efficiency=lle_raw,
        affinity_threshold=affinity_threshold,
        affinity_multiplier=affinity_multiplier,
        specificity_multiplier=specificity_multiplier,
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
        # Obtenemos el resultado previo y la molécula para saber el target
        result = await repository.get_evaluation_result(molecule_id)
        is_control = bool(result.is_control) if result else False
        
        mol = await repository.get_molecule(molecule_id)
        target = mol.target if mol else None
        
        breakdown = calculate_score_breakdown(
            docking, 
            properties, 
            is_control=is_control,
            target_hotspots=target.hotspots if target else None,
            affinity_threshold=target.affinity_threshold if target and target.affinity_threshold is not None else -7.5
        )
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

