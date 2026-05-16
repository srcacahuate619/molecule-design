"""
utils/scientific.py

Utilidades para auditoría científica profunda de resultados de docking y propiedades.
Genera advertencias relevantes para el usuario final (químicos medicinales).
"""

from typing import Any
import math

def audit_scientific_quality(
    affinity_kcal: float,
    heavy_atom_count: int,
    log_p: float,
    docking_poses: list[dict],
    hotspots: list[dict],
    hotspots_hit: list[str]
) -> list[str]:
    """
    Analiza los resultados crudos y genera advertencias científicas dinámicas.
    """
    warnings = []

    # 1. Ligand Efficiency (LE)
    if heavy_atom_count > 0:
        le = abs(affinity_kcal) / heavy_atom_count
        if le < 0.25:
            warnings.append(
                f"Baja Eficiencia de Ligando (LE={le:.2f}): La molécula es demasiado grande para la afinidad que ofrece. Considerar optimizar átomos innecesarios."
            )
        elif le > 0.45:
            warnings.append(
                f"Eficiencia de Ligando Excepcional (LE={le:.2f}): Excelente economía de átomos para este nivel de unión."
            )

    # 2. Lipophilic Efficiency (LLE)
    lle = abs(affinity_kcal) - log_p
    if lle < 1.0:
        warnings.append(
            f"Baja Eficiencia Lipofílica (LLE={lle:.2f}): El compuesto depende demasiado de la hidrofobicidad para unirse. Riesgo de baja selectividad y toxicidad."
        )

    # 3. Estabilidad del modo de enlace (RMSD Diversification)
    if len(docking_poses) > 2:
        # Vina suele dar RMSD lb/ub. Usamos lb como proxy de distancia al centro.
        # Un análisis más real requeriría calcular distancias entre poses.
        # Pero podemos usar la diferencia de afinidad como proxy de "seguridad" del modo 1.
        gap = abs(docking_poses[1]['affinity'] - docking_poses[0]['affinity'])
        if gap < 0.1:
            warnings.append(
                "Incertidumbre de Pose: Hay múltiples modos de enlace con energías casi idénticas. El modo 1 podría no ser el único biológicamente relevante."
            )

    # 4. Análisis de Hotspots
    if hotspots:
        total_hotspots = len(hotspots)
        hits_count = len(hotspots_hit)
        hit_ratio = hits_count / total_hotspots if total_hotspots > 0 else 0
        
        if hit_ratio == 0:
            warnings.append(
                "Fracaso de Farmacóforo: La molécula no interactúa con ningún residuo crítico definido para este target."
            )
        elif hit_ratio < 0.4:
            warnings.append(
                f"Interacción Subóptima: Solo impacta el {hit_ratio*100:.0f}% de los hotspots. Potencial para mejorar la afinidad mediante derivatización dirigida."
            )
            
        # Buscar hotspots de alta importancia no impactados
        critical_missed = [h['name'] for h in hotspots if h['importance'] >= 0.9 and h['name'] not in hotspots_hit]
        if critical_missed:
            warnings.append(
                f"Oportunidad Crítica: Se han fallado residuos de importancia máxima ({', '.join(critical_missed)})."
            )

    # 5. Regla de Oro de Afinidad
    if affinity_kcal > -6.0:
        warnings.append(
            "Afinidad Marginal: Los niveles de binding calculados están en el rango micromolar alto. Probablemente insuficiente para actividad farmacológica in vivo."
        )

    return warnings
