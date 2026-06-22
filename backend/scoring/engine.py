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


def _calculate_sa_factor(sa_score: float | None) -> tuple[float, str]:
    """
    Calcula un factor multiplicativo [0.35, 1.00] basado en el SA Score.

    SA Score (Ertl & Schuffenhauer 2009):
      1.0 = trivialmente sintetizable
      10.0 = prácticamente imposible de sintetizar

    Este factor penaliza directamente el total_score para reflejar
    que una molécula no sintetizable no puede ser un fármaco real,
    independientemente de su afinidad o propiedades fisioquímicas.

    Curva calibrada para química medicinal estándar:
      SA ≤ 3.5  → factor=1.00 (sin penalización)
      SA = 4.0  → factor=0.95
      SA = 4.5  → factor=0.85
      SA = 5.0  → factor=0.72
      SA = 6.0  → factor=0.55
      SA = 7.0  → factor=0.42
      SA ≥ 8.0  → factor=0.35 (máximo castigo)

    Returns:
        (factor, severity_label): el multiplicador y una etiqueta descriptiva.
    """
    if sa_score is None:
        return 1.0, "sin_dato"

    if sa_score <= 3.5:
        return 1.0, "excelente"
    elif sa_score <= 4.0:
        # Gracia suave: SA 3.5–4.0
        factor = 1.0 - (sa_score - 3.5) * 0.10
        return round(factor, 3), "buena"
    elif sa_score <= 5.0:
        # Penalización progresiva: SA 4.0–5.0
        # En 4.0: 0.95, en 5.0: 0.72 (descenso de ~0.23)
        factor = 0.95 - (sa_score - 4.0) * 0.23
        return round(factor, 3), "moderada"
    elif sa_score <= 6.0:
        # Penalización significativa: SA 5.0–6.0
        # En 5.0: 0.72, en 6.0: 0.55 (descenso de ~0.17)
        factor = 0.72 - (sa_score - 5.0) * 0.17
        return round(factor, 3), "dificil"
    elif sa_score <= 7.0:
        # Penalización severa: SA 6.0–7.0
        # En 6.0: 0.55, en 7.0: 0.42 (descenso de ~0.13)
        factor = 0.55 - (sa_score - 6.0) * 0.13
        return round(factor, 3), "muy_dificil"
    else:
        # Penalización máxima: SA > 7.0
        # Decae linealmente hasta 0.35 en SA=8+
        factor = max(0.35, 0.42 - (sa_score - 7.0) * 0.07)
        return round(factor, 3), "inviable"


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
        sa_penalty_factor = 1.0
    else:
        # El score base se multiplica por la especificidad
        base_score = (affinity_score * settings.score_weight_affinity) + (physico_score * affinity_multiplier)
        base_score_with_specificity = base_score * specificity_multiplier

        # --- [NUEVO] Factor GNN (RTMScore Nivel 2) Directo ---
        # RTMScore predice pKd/pKi (típicamente entre 4.0 y 10.0).
        # Centramos la sigmoide en 6.0 (afinidad micromolar). Si el score es 6.0, el factor es 1.0 (neutro).
        if gnn_score is not None:
            # Rango sigmoide crudo [0, 1]
            raw_factor = 1.0 / (1.0 + math.exp(-1.0 * (gnn_score - 6.0)))
            
            # Concordance gate: if GNN strongly disagrees with Vina direction, dampen (Bug #5)
            vina_says_good = affinity_score > 50.0
            gnn_says_good = gnn_score > 6.0
            if vina_says_good != gnn_says_good:
                # Dampen the GNN correction toward neutral [0.85, 1.15]
                gnn_factor = 0.85 + (raw_factor * 0.30)
            else:
                # Full range [0.70, 1.30]
                gnn_factor = 0.70 + (raw_factor * 0.60)
        else:
            gnn_factor = 1.0

        # --- Factor SA (Accesibilidad Sintética) ---
        # Penaliza el total_score si la molécula es difícil/imposible de sintetizar.
        # Actua independientemente del ADME score como gate de viabilidad química.
        # Ref: Ertl & Schuffenhauer (2009), J. Cheminform. 1:8.
        sa_factor, sa_severity = _calculate_sa_factor(properties.sa_score)
        if sa_factor < 1.0:
            log.info(
                "sa_penalty_applied",
                sa_score=properties.sa_score,
                sa_factor=sa_factor,
                sa_severity=sa_severity,
            )

        total_score = clamp_score(base_score_with_specificity * gnn_factor * sa_factor)

    strongest, weakest = _pick_dimensions(
        affinity_score,
        adme_score,
        druglikeness_score,
    )

    # Calcular LE y LLE bruta para pasarla al frontend
    le_raw = round(docking.best_affinity / properties.heavy_atom_count, 3) if properties.heavy_atom_count else None
    
    # Check if best_affinity is positive to prevent LLE inversion (Bug #8)
    best_affinity_val = docking.best_affinity
    if best_affinity_val > 0.0:
        log.warning(f"best_affinity is positive ({best_affinity_val}), which violates the Vina negative convention. Clipping to 0.0.")
        best_affinity_val = 0.0
    lle_raw = round((-best_affinity_val / 1.36) - properties.log_p, 3) if properties.log_p is not None else None

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

