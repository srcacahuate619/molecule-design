import math
from core.models import PhysicochemicalProperties


def clamp_score(value: float) -> float:
    """Asegura que cualquier score quede en el rango [0, 100]."""
    return round(max(0.0, min(100.0, value)), 2)


def normalize_affinity(
    affinity_kcal: float, 
    heavy_atoms: int | None = None, 
    log_p: float | None = None,
    threshold: float = -7.5
) -> float:
    """
    Normaliza afinidad usando una función sigmoidea (Curva de Hill) basada en 
    Ligand Efficiency (LE) y validada por Lipophilic Efficiency (LLE).
    
    V6.0 "Scientific Rigor - Potency Floor":
    - LE = affinity / heavy_atoms
    - Sigmoide centrada en LE = -0.30
    - Penalizador por Potencia Absoluta: Si afinidad > threshold, el score cae.
    """
    if not heavy_atoms or heavy_atoms <= 0:
        # Fallback a afinidad absoluta con sigmoide
        mid_abs = threshold
        k_abs = 2.0
        score = 100 / (1 + math.exp(k_abs * (affinity_kcal - mid_abs)))
        return clamp_score(score)

    le = affinity_kcal / heavy_atoms
    
    # --- Función Sigmoidea para LE ---
    mid_le = -0.30
    k_le = 15
    base_score = 100 / (1 + math.exp(k_le * (le - mid_le)))

    # --- PENALIZADOR DE POTENCIA ABSOLUTA [NUEVO] ---
    # Si la molécula es muy eficiente pero muy débil (fragmento), se le castiga.
    # Sigmoide centrada en 'threshold' (ej. -7.5) con pendiente k=2.0.
    # Esto asegura que para ser un "Lead", debe tener potencia real.
    potency_factor = 1.0 / (1 + math.exp(2.0 * (affinity_kcal - threshold)))
    base_score *= potency_factor

    # --- Factor LLE (Lipophilic Efficiency) ---
    if log_p is not None:
        lle = (-affinity_kcal) - log_p
        if lle < 3.0:
            lle_factor = max(0.4, (lle / 3.0)) 
            base_score *= lle_factor
        elif lle > 7.0:
            base_score = min(100.0, base_score * 1.05)

    # --- Penalizador por Tamaño ---
    if heavy_atoms < 12:
        size_penalty = (12 - heavy_atoms) * 8.0 
        base_score = max(0.0, base_score - size_penalty)

    return clamp_score(base_score)


def calculate_adme_score(properties: PhysicochemicalProperties) -> float:
    """
    Score ADME basado en QED.
    Rango 0.0 a 1.0 → mapeado a 0–100.
    """
    return clamp_score(properties.qed * 100.0)


def calculate_druglikeness_score(properties: PhysicochemicalProperties) -> float:
    """
    Score Drug-likeness basado en QED.
    """
    return clamp_score(properties.qed * 100.0)

