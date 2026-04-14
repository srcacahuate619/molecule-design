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


def normalize_affinity(affinity_kcal: float) -> float:
    """
    Normaliza afinidad de docking a 0–100.

    Rango calibrado para AutoDock Vina con targets típicos de GPCRs:
    - Afinidades <= -10 kcal/mol se consideran excelentes → 100.
    - Afinidades >= -4 kcal/mol se consideran pobres → 0.
    - Entre ambos puntos usamos interpolación lineal inversa.

    Justificación del rango:
    - Vina típicamente reporta afinidades entre -3 y -12 kcal/mol para
      moléculas drug-like contra GPCRs.
    - Para fármacos conocidos de 5-HT1A (ej. buspirona, aripiprazol),
      Vina suele predecir entre -7 y -10 kcal/mol.
    - El umbral de -4 kcal/mol descarta interacciones no específicas.
    - Referencia: Trott & Olson (2010) J Comput Chem 31:455-461.

    NOTA: Este rango debe recalibrarse si se cambia el target o la
    preparación del receptor. Usar scripts/calibrate_external_panel.py
    para verificar que el rango captura la variabilidad real.

    Esto no convierte el docking en verdad biológica; solo permite comparar
    resultados computacionales en una escala homogénea.
    """
    best = -10.0
    worst = -4.0

    if affinity_kcal <= best:
        return 100.0
    if affinity_kcal >= worst:
        return 0.0

    normalized = ((worst - affinity_kcal) / (worst - best)) * 100.0
    return clamp_score(normalized)


def normalize_logp(log_p: float) -> float:
    """
    logP ideal centrado en 2.5 con penalización por distancia.

    Justificación:
    - valores muy bajos suelen indicar baja permeabilidad,
    - valores muy altos suelen indicar exceso de lipofilia y problemas ADME.

    Definimos:
    - score 100 en logP = 2.5
    - score decrece linealmente hasta 0 cuando la distancia al óptimo es >= 3.5
      (aprox. logP <= -1.0 o >= 6.0)
    """
    optimum = 2.5
    max_distance = 3.5
    distance = abs(log_p - optimum)

    if distance >= max_distance:
        return 0.0

    score = (1.0 - (distance / max_distance)) * 100.0
    return clamp_score(score)


def normalize_tpsa(tpsa: float) -> float:
    """
    TPSA con preferencia por rango compatible con absorción oral.

    Supuesto práctico del MVP:
    - <= 20 Å²: demasiado baja polaridad para muchos perfiles orales → penalizada
    - 20–90 Å²: rango fuerte → hasta 100
    - 90–140 Å²: aceptable pero decreciente
    - >= 140 Å²: muy desfavorable para absorción oral → 0
    """
    if tpsa >= 140.0:
        return 0.0
    if 20.0 <= tpsa <= 90.0:
        return 100.0
    if tpsa < 20.0:
        score = (tpsa / 20.0) * 100.0
        return clamp_score(score)

    # 90–140 Å² → caída lineal a 0
    score = ((140.0 - tpsa) / 50.0) * 100.0
    return clamp_score(score)


def normalize_rotatable_bonds(rotatable_bonds: int) -> float:
    """
    Penaliza flexibilidad excesiva.

    Veber usa <= 10 enlaces rotables como umbral razonable de biodisponibilidad.
    En el MVP:
    - 0–3: excelente → 100
    - 4–10: caída suave
    - >10: caída fuerte hasta 0 en 15
    """
    if rotatable_bonds <= 3:
        return 100.0
    if rotatable_bonds >= 15:
        return 0.0
    if rotatable_bonds <= 10:
        score = 100.0 - ((rotatable_bonds - 3) / 7.0) * 40.0
        return clamp_score(score)

    score = 60.0 - ((rotatable_bonds - 10) / 5.0) * 60.0
    return clamp_score(score)


def calculate_adme_score(properties: PhysicochemicalProperties) -> float:
    """
    Score ADME compuesto para priorización del MVP.

    Componentes y pesos internos:
    - logP: 40%
    - TPSA: 40%
    - rotatable bonds: 20%

    No pretende capturar ADME completo; solo una aproximación explícita,
    reproducible y útil para ranking inicial.
    """
    logp_score = normalize_logp(properties.log_p)
    tpsa_score = normalize_tpsa(properties.tpsa)
    rot_score = normalize_rotatable_bonds(properties.rotatable_bonds)

    total = (logp_score * 0.4) + (tpsa_score * 0.4) + (rot_score * 0.2)
    return clamp_score(total)


def calculate_druglikeness_score(properties: PhysicochemicalProperties) -> float:
    """
    Score de drug-likeness basado en cumplimiento de Lipinski y Veber
    con penalización gradual cerca de los umbrales.

    Método:
    - base 100
    - penalización gradual cuando una propiedad se acerca al umbral de Lipinski
    - penalización completa (-20 puntos) cuando se viola el umbral
    - penalización gradual/completa para Veber (-10 puntos por violación)

    La penalización gradual es científicamente más honesta porque la diferencia
    entre MW=499 y MW=501 no es biológicamente significativa.

    Zona de penalización gradual: 10% por debajo del umbral.
    Ejemplo: MW > 450 empieza a penalizar suavemente, MW > 500 penaliza completo.
    """
    score = 100.0

    # --- Lipinski con gradiente ---
    # MW: umbral 500, zona gradual desde 450
    if properties.molecular_weight > 500:
        score -= 20.0
    elif properties.molecular_weight > 450:
        score -= ((properties.molecular_weight - 450) / 50.0) * 10.0

    # logP: umbral 5.0, zona gradual desde 4.5
    if properties.log_p > 5.0:
        score -= 20.0
    elif properties.log_p > 4.5:
        score -= ((properties.log_p - 4.5) / 0.5) * 10.0

    # HBD: umbral 5, zona gradual desde 4
    if properties.hbd > 5:
        score -= 20.0
    elif properties.hbd > 4:
        score -= (properties.hbd - 4) * 10.0

    # HBA: umbral 10, zona gradual desde 8
    if properties.hba > 10:
        score -= 20.0
    elif properties.hba > 8:
        score -= ((properties.hba - 8) / 2.0) * 10.0

    # --- Veber con gradiente ---
    # RotBonds: umbral 10, zona gradual desde 8
    if properties.rotatable_bonds > 10:
        score -= 10.0
    elif properties.rotatable_bonds > 8:
        score -= ((properties.rotatable_bonds - 8) / 2.0) * 5.0

    # TPSA: umbral 140, zona gradual desde 120
    if properties.tpsa > 140:
        score -= 10.0
    elif properties.tpsa > 120:
        score -= ((properties.tpsa - 120) / 20.0) * 5.0

    return clamp_score(score)
