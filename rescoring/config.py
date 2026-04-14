"""
rescoring/config.py

Configuración del microservicio de rescoring.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings


class RescoringSettings(BaseSettings):
    """Configuración del microservicio de rescoring."""

    # Paths a artefactos del modelo
    model_a_path: str = "artifacts/model_a.joblib"
    model_null_path: str = "artifacts/model_null.joblib"
    delta_distribution_path: str = "artifacts/delta_distribution.json"
    applicability_domain_path: str = "artifacts/applicability_domain.json"
    training_report_path: str = "artifacts/training_report.json"

    # Umbrales de semáforo de Delta (percentiles, se cargan del artefacto)
    delta_green_threshold: float = 0.5  # por encima → verde (específico)
    delta_red_threshold: float = -0.3  # por debajo → rojo (choque)

    # Pose filter
    pose_filter_max_distance: float = 12.0  # Å — distancia máxima centroide-ligando al grid center
    pose_filter_min_atoms_in_box: float = 0.7  # 70% de átomos pesados dentro del grid box
    pose_filter_max_clashes: int = 5  # máximo de clashes estéricos con la proteína

    # Pose variance — umbrales de estabilidad
    pose_variance_low: float = 0.3  # < 0.3 kcal/mol → ALTA estabilidad
    pose_variance_high: float = 1.0  # > 1.0 kcal/mol → BAJA estabilidad

    # Logging
    log_level: str = "INFO"

    model_config = {"env_prefix": "RESCORING_"}


@lru_cache
def get_rescoring_settings() -> RescoringSettings:
    return RescoringSettings()
