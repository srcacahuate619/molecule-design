"""
scoring/normalizer.py

Normalización explícita de métricas crudas a escala 0–100.

Principio: una métrica normalizada debe ser:
- auditable,
- reproducible,
- monotónica respecto a la dirección deseada,
- y fácil de interpretar.

No usamos funciones opacas ni modelos entrenados. Las transformaciones son
determinísticas y documentadas para priorización computacional del MVP.
"""

from __future__ import annotations

from core.models import PhysicochemicalProperties


def clamp_score(value: float) -> float:
    """Asegura que cualquier score quede en el rango [0, 100]."""
    return round(max(0.0, min(100.0, value)), 2)


def normalize_affinity(affinity_kcal: float, heavy_atoms: int | None = None) -> float:
    """
    Normaliza afinidad usando Ligand Efficiency (LE) si se dispone de átomos pesados,
    o afinidad absoluta como fallback.

    Ligand Efficiency (LE) = affinity_kcal / heavy_atoms
    - LE <= -0.40 kcal/mol/átomo → 100 (excelente)
    - LE >= -0.10 kcal/mol/átomo → 0 (pobre)
    """
    if heavy_atoms and heavy_atoms > 0:
        le = affinity_kcal / heavy_atoms
        # Calibración estricta para Vina:
        # Vina tiende a inflar la afinidad de fragmentos pequeños (a menudo superan el -0.40 teórico).
        # Ajustamos el umbral para que llegar a 100 requiera una eficiencia verdaderamente excepcional (-0.55).
        # Implementamos el estándar de la industria para "Hit identification": LE >= -0.30. 
        # Moléculas peores a -0.30 son consideradas "ruido" y obtienen 0%.
        best_le = -0.55
        worst_le = -0.30
        if le <= best_le:
            return 100.0
        if le >= worst_le:
            return 0.0
        normalized = ((worst_le - le) / (worst_le - best_le)) * 100.0
        return clamp_score(normalized)
    
    # Fallback to absolute affinity
    best_abs = -10.0
    worst_abs = -4.0
    if affinity_kcal <= best_abs:
        return 100.0
    if affinity_kcal >= worst_abs:
        return 0.0
    normalized = ((worst_abs - affinity_kcal) / (worst_abs - best_abs)) * 100.0
    return clamp_score(normalized)


def calculate_adme_score(properties: PhysicochemicalProperties) -> float:
    """
    Score ADME ahora basado directamente en QED (Quantitative Estimate of Drug-likeness).
    QED evalúa de forma balanceada logP, TPSA, RotBonds, etc.
    Rango 0.0 a 1.0 → mapeado a 0–100.
    """
    return clamp_score(properties.qed * 100.0)


def calculate_druglikeness_score(properties: PhysicochemicalProperties) -> float:
    """
    Score Drug-likeness basado directamente en QED (Quantitative Estimate of Drug-likeness).
    Utilizamos la misma métrica rigurosa para ADME y Drug-likeness, 
    eliminando heurísticas manuales inventadas.
    """
    return clamp_score(properties.qed * 100.0)

