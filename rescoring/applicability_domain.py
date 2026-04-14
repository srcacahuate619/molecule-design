"""
rescoring/applicability_domain.py

Verificación de Applicability Domain con distancia de Mahalanobis.

Origen: Banca / Basilea III (Population Stability Index).
Adaptado a cheminformatics: detectar automáticamente moléculas fuera del
dominio de entrenamiento del modelo ANTES de predecir.

Lógica:
  1. Calcular distancia de Mahalanobis de la molécula al centroide del training set
  2. Comparar con umbral (percentil 99 de distancias en training set)
  3. Si distancia > umbral → molécula fuera de dominio → NO predecir con ML

Artefacto requerido: artifacts/applicability_domain.json
  {
    "mean": [...],           # media de cada descriptor en training set
    "cov_inv": [[...],...],  # inversa de la matriz de covarianza
    "threshold": 8.7,        # percentil 99 de distancias de Mahalanobis en training
    "feature_names": [...],  # nombres de los descriptores usados
    "feature_ranges": {      # rangos observados por descriptor (para reportar al usuario)
      "mw": {"min": 150, "max": 750},
      "logp": {"min": -2.0, "max": 6.0},
      ...
    }
  }

Este artefacto se genera en Fase 2 de entrenamiento.
En Fase 1 (sin artefacto), el check es permisivo (todo pasa).

Referencia:
  - Sahlin U. "The Applicability Domain in QSAR Modeling." QSAR & Comb Sci, 2008.
  - Yurdakul B. "Statistical Properties of Population Stability Index." WMU, 2018.
"""

from __future__ import annotations

from typing import Any

import numpy as np
from scipy.spatial.distance import mahalanobis

from logger import get_logger

log = get_logger(__name__)


# Descriptores usados para el check de Applicability Domain
# Son los descriptores 1D/2D que definen el "espacio químico" del training set
AD_DESCRIPTORS = ["mw", "logp", "tpsa", "hbd", "hba", "rotatable_bonds", "qed"]


class ApplicabilityDomainChecker:
    """
    Verificador de Applicability Domain basado en distancia de Mahalanobis.

    Si no hay artefacto cargado (Fase 1), es permisivo: todo pasa.
    Si hay artefacto (post-Fase 2), verifica contra el training set.
    """

    def __init__(self, ad_data: dict[str, Any] | None = None):
        """
        Args:
            ad_data: dict con keys 'mean', 'cov_inv', 'threshold', 'feature_names', 'feature_ranges'
                     o None si no hay artefacto (modo permisivo)
        """
        self._loaded = ad_data is not None
        self._mean = ad_data["mean"] if ad_data else None
        self._cov_inv = ad_data["cov_inv"] if ad_data else None
        self._threshold = ad_data["threshold"] if ad_data else 0.0
        self._feature_names = ad_data.get("feature_names", AD_DESCRIPTORS) if ad_data else AD_DESCRIPTORS
        self._feature_ranges = ad_data.get("feature_ranges", {}) if ad_data else {}

    def check(self, descriptors: dict[str, float]) -> Any:
        """
        Verificar si una molécula está dentro del dominio de aplicabilidad.

        Args:
            descriptors: dict con descriptores 1D/2D de la molécula

        Returns:
            ApplicabilityDomainResult (importado de app.py)
        """
        from app import ApplicabilityDomainResult

        if not self._loaded:
            # Sin artefacto → modo permisivo (Fase 1)
            log.debug(
                "ad_check_permissive",
                msg="Sin artefacto de Applicability Domain. Modo permisivo (Fase 1).",
            )
            return ApplicabilityDomainResult(
                in_domain=True,
                mahalanobis_distance=0.0,
                threshold=0.0,
                out_of_range_descriptors=[],
            )

        # Construir vector de descriptores en el orden correcto
        mol_vector = np.array([
            descriptors.get(feat, 0.0) for feat in self._feature_names
        ])

        # Calcular distancia de Mahalanobis
        try:
            distance = mahalanobis(mol_vector, self._mean, self._cov_inv)
        except Exception as e:
            log.error("mahalanobis_error", error=str(e))
            # Si falla el cálculo, ser conservador → fuera de dominio
            return ApplicabilityDomainResult(
                in_domain=False,
                mahalanobis_distance=float("inf"),
                threshold=self._threshold,
                out_of_range_descriptors=["Error en cálculo de distancia"],
            )

        in_domain = distance <= self._threshold

        # Identificar qué descriptores están fuera de rango
        out_of_range = []
        for i, feat_name in enumerate(self._feature_names):
            if feat_name in self._feature_ranges:
                feat_range = self._feature_ranges[feat_name]
                val = mol_vector[i]
                if val < feat_range.get("min", float("-inf")) or val > feat_range.get("max", float("inf")):
                    out_of_range.append(
                        f"{feat_name}: {val:.2f} "
                        f"(rango training: {feat_range.get('min', '?')}-{feat_range.get('max', '?')})"
                    )

        if not in_domain:
            log.warning(
                "ad_out_of_domain",
                distance=round(distance, 2),
                threshold=self._threshold,
                out_of_range=out_of_range,
            )

        return ApplicabilityDomainResult(
            in_domain=in_domain,
            mahalanobis_distance=round(distance, 4),
            threshold=self._threshold,
            out_of_range_descriptors=out_of_range,
        )

    @staticmethod
    def build_from_training_data(
        training_descriptors: np.ndarray,
        feature_names: list[str],
        percentile: float = 99.0,
    ) -> dict[str, Any]:
        """
        Construir artefacto de Applicability Domain a partir del training set.

        Se usa OFFLINE durante el entrenamiento (Fase 2).
        El resultado se guarda como artifacts/applicability_domain.json.

        Args:
            training_descriptors: array (n_samples, n_features) de descriptores del training set
            feature_names: nombres de los descriptores
            percentile: percentil para el umbral (default: 99)

        Returns:
            dict serializable a JSON con mean, cov_inv, threshold, feature_names, feature_ranges
        """
        n_samples, n_features = training_descriptors.shape

        mean = training_descriptors.mean(axis=0)
        cov = np.cov(training_descriptors.T)

        # Manejar covarianza singular (features colineales)
        try:
            cov_inv = np.linalg.inv(cov)
        except np.linalg.LinAlgError:
            log.warning(
                "ad_singular_covariance",
                msg="Covarianza singular. Usando pseudo-inversa (Moore-Penrose).",
            )
            cov_inv = np.linalg.pinv(cov)

        # Calcular distancias de Mahalanobis para todo el training set
        distances = []
        for x in training_descriptors:
            d = mahalanobis(x, mean, cov_inv)
            distances.append(d)

        threshold = float(np.percentile(distances, percentile))

        # Rangos por descriptor
        feature_ranges = {}
        for i, name in enumerate(feature_names):
            col = training_descriptors[:, i]
            feature_ranges[name] = {
                "min": round(float(col.min()), 4),
                "max": round(float(col.max()), 4),
                "mean": round(float(col.mean()), 4),
                "std": round(float(col.std()), 4),
            }

        artifact = {
            "mean": mean.tolist(),
            "cov_inv": cov_inv.tolist(),
            "threshold": round(threshold, 4),
            "percentile": percentile,
            "n_training_samples": n_samples,
            "n_features": n_features,
            "feature_names": feature_names,
            "feature_ranges": feature_ranges,
        }

        log.info(
            "ad_built",
            n_samples=n_samples,
            threshold=round(threshold, 4),
            percentile=percentile,
        )

        return artifact
