import math
from core.models import PhysicochemicalProperties


def clamp_score(value: float) -> float:
    """Asegura que cualquier score quede en el rango [0, 100]."""
    return round(max(0.0, min(100.0, value)), 2)


def normalize_affinity(
    affinity_kcal: float, 
    heavy_atoms: int | None = None, 
    log_p: float | None = None,
    threshold: float = -7.5,
    is_control: bool = False
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
    
    # --- [CIENCIA DILUCIDADA] LE de referencia decae fisiológicamente con el tamaño ---
    # Fragmentos pequeños necesitan mayor densidad de energía; ligandos grandes tienen límites de empaquetamiento estérico.
    if heavy_atoms < 15:
        mid_le = -0.38
    elif heavy_atoms > 45:
        mid_le = -0.20
    else:
        # Interpolación lineal entre 15 y 45 átomos pesados
        mid_le = -0.38 + (heavy_atoms - 15) * (0.18 / 30)
    
    k_le = 15
    base_score = 100 / (1 + math.exp(k_le * (le - mid_le)))

    # --- PENALIZADOR DE POTENCIA ABSOLUTA OPTIMIZADO ---
    # Si la molécula es más débil que el threshold, se aplica un castigo sigmoideo suave.
    # Si cumple o supera el threshold, no hay penalización (potency_factor = 1.0).
    if affinity_kcal > threshold and not is_control:
        # Sigmoide centrada en threshold con pendiente k=2.0
        potency_factor = 1.0 / (1 + math.exp(2.0 * (affinity_kcal - threshold)))
        # Escalamos para evitar discontinuidades bruscas: a la altura del threshold vale 1.0
        potency_factor = min(1.0, potency_factor * 2.0)
        base_score *= potency_factor

    # --- Factor LLE (Lipophilic Efficiency) ---
    if log_p is not None:
        lle = (-affinity_kcal / 1.36) - log_p
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
    Score ADME basado en el perfil de absorción/distribución estimado.

    Compuesto de tres factores:
      - TPSA: penaliza absorción oral pobre (>90Å²) y BBB impenetrable (>120Å²)
      - logP: penaliza lipofilia extrema (<0 o >4.5) que afecta distribución y toxicidad
      - SA Score: penaliza complejidad sintética elevada (>4.0)

    A diferencia del QED (que da un único score holístico de drug-likeness),
    este score captura el perfil ADME de forma más mecánicamente interpretable.

    Rango: 0–100 (100 = perfil ADME ideal)
    """
    score = 100.0

    # 1. Penalización TPSA — absorción oral e intestinal
    tpsa = properties.tpsa
    if tpsa > 120.0:
        # Rango pobre de BBB o absorción oral muy limitada
        score -= min(30.0, (tpsa - 120.0) * 0.75)
    elif tpsa > 90.0:
        # Absorción oral limitada (Veber: TPSA≤140 para biodisponibilidad oral)
        score -= (tpsa - 90.0) * 0.5

    # 2. Penalización logP — lipofilia extrema en ambos sentidos
    log_p = properties.log_p
    if log_p > 4.5:
        # Riesgo de hERG, acumulación en tejido graso, baja solubilidad
        score -= min(25.0, (log_p - 4.5) * 5.0)
    elif log_p < 0.0:
        # Hidrofilia extrema → posible baja permeabilidad celular
        score -= min(15.0, abs(log_p) * 3.0)

    # 3. Penalización SA Score — accesibilidad sintética
    sa = properties.sa_score
    if sa > 5.0:
        # Difícil de sintetizar → costo de desarrollo elevado
        score -= min(20.0, (sa - 5.0) * 4.0)
    elif sa > 4.0:
        # Complejidad moderada-alta
        score -= (sa - 4.0) * 2.0

    return clamp_score(score)


def calculate_druglikeness_score(properties: PhysicochemicalProperties) -> float:
    """
    Score de Drug-likeness basado en QED (Bickerton et al., Nat. Chem. 2012).

    QED combina 8 propiedades moleculares ponderadas (MW, logP, HBD, HBA,
    PSA, RotBonds, Aromáticos, Alertas estructurales) en una métrica unificada
    de 0 a 1 que reproduce el juicio de expertos en química medicinal.

    Rango mapeado: 0–100 (100 = QED=1.0, molécula drug-like ideal)
    """
    return clamp_score(properties.qed * 100.0)


def normalize_logp(log_p: float) -> float:
    """
    Normaliza el logP usando una función simétrica respecto al óptimo de 2.5.
    Mantiene compatibilidad con auditorías y tests de regresión.
    """
    dist = abs(log_p - 2.5)
    score = 0.0 if dist >= 3.5 else (1.0 - dist / 3.5) * 100.0
    return clamp_score(score)


def normalize_tpsa(tpsa: float) -> float:
    """
    Normaliza el TPSA con una ventana óptima de 20-90 Å².
    Mantiene compatibilidad con auditorías y tests de regresión.
    """
    if tpsa >= 140.0:
        score = 0.0
    elif 20.0 <= tpsa <= 90.0:
        score = 100.0
    elif tpsa < 20.0:
        score = (tpsa / 20.0) * 100.0
    else:
        score = ((140.0 - tpsa) / 50.0) * 100.0
    return clamp_score(score)


def normalize_rotatable_bonds(rotatable_bonds: int) -> float:
    """
    Normaliza la flexibilidad molecular (rotatable bonds).
    Mantiene compatibilidad con auditorías y tests de regresión.
    """
    if rotatable_bonds <= 3:
        score = 100.0
    elif rotatable_bonds >= 15:
        score = 0.0
    elif rotatable_bonds <= 10:
        score = 100.0 - ((rotatable_bonds - 3) / 7.0) * 40.0
    else:
        score = 60.0 - ((rotatable_bonds - 10) / 5.0) * 60.0
    return clamp_score(score)

