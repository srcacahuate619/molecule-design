import math
from core.models import PhysicochemicalProperties


def clamp_score(value: float) -> float:
    """Asegura que cualquier score quede en el rango [0, 100]."""
    return round(max(0.0, min(100.0, value)), 2)


def normalize_affinity(affinity_kcal: float, heavy_atoms: int | None = None, log_p: float | None = None) -> float:
    """
    Normaliza afinidad usando una función sigmoidea (Curva de Hill) basada en 
    Ligand Efficiency (LE) y validada por Lipophilic Efficiency (LLE).
    
    V5.0 "Scientific Rigor":
    - LE = affinity / heavy_atoms
    - Sigmoide centrada en LE = -0.45 kcal/mol/at.
    - LLE = (-affinity) - logP (Ideal > 5)
    """
    if not heavy_atoms or heavy_atoms <= 0:
        # Fallback a afinidad absoluta con sigmoide
        # Centro en -7.0 kcal/mol, k=1.5
        mid_abs = -7.0
        k_abs = 1.5
        score = 100 / (1 + math.exp(k_abs * (affinity_kcal - mid_abs)))
        return clamp_score(score)

    le = affinity_kcal / heavy_atoms
    
    # --- Función Sigmoidea para LE ---
    # Centro (50%) en -0.30. Pendiente (k) = 15.
    mid_le = -0.30
    k_le = 15
    # Formula: 100 / (1 + exp(k * (le - mid)))
    base_score = 100 / (1 + math.exp(k_le * (le - mid_le)))

    # --- Factor LLE (Lipophilic Efficiency) ---
    # LLE penaliza moléculas que ganan afinidad solo por ser "grasientas" (logP alto).
    # Un LLE < 3 es mediocre, > 5 es excelente.
    if log_p is not None:
        lle = (-affinity_kcal) - log_p
        if lle < 3.0:
            # Penalización suave pero progresiva
            lle_factor = max(0.4, (lle / 3.0)) 
            base_score *= lle_factor
        elif lle > 7.0:
            # Bonus pequeño por eficiencia excepcional
            base_score = min(100.0, base_score * 1.05)

    # --- Penalizador por Tamaño (Rigidez Química) ---
    # Moléculas muy pequeñas (< 12 átomos) no pueden tener scores perfectos
    # por falta de especificidad.
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

