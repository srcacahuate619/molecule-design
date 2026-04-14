"""
rescoring/model_manager.py

Gestión de carga y predicción de los modelos ML de rescoring.

Carga al arranque:
  - Modelo A (XGBoost rank:pairwise, features completas)
  - Modelo NULL (XGBoost rank:pairwise, solo features 1D/2D)
  - Distribución de Delta (para umbrales de semáforo)
  - Applicability Domain (media, cov_inv, threshold)

Si los artefactos no existen (Fase 1 — antes de entrenamiento),
el servicio arranca en modo degradado: health = degraded, /rescore = 503.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import numpy as np

from config import get_rescoring_settings
from logger import get_logger

log = get_logger(__name__)
settings = get_rescoring_settings()


class ModelManager:
    """Gestor de modelos de rescoring."""

    def __init__(self):
        self.model_a = None
        self.model_null = None
        self.model_a_artifact: dict | None = None
        self.model_null_artifact: dict | None = None
        self.delta_distribution: dict[str, Any] | None = None
        self.applicability_domain: dict[str, Any] | None = None
        self.training_report: dict[str, Any] | None = None
        self._is_loaded = False
        self._model_version: str | None = None

    @property
    def is_loaded(self) -> bool:
        return self._is_loaded

    @property
    def model_version(self) -> str | None:
        return self._model_version

    def load_models(self) -> None:
        """
        Intentar cargar todos los artefactos del modelo.

        Si no existen (pre-entrenamiento), el servicio arranca en modo degradado.
        Esto es esperado en Fase 1 — el servicio existe pero no tiene modelo todavía.
        """
        model_a_path = Path(settings.model_a_path)
        model_null_path = Path(settings.model_null_path)
        ad_path = Path(settings.applicability_domain_path)
        delta_path = Path(settings.delta_distribution_path)
        report_path = Path(settings.training_report_path)

        # Verificar si existen los artefactos mínimos
        if not model_a_path.exists() or not model_null_path.exists():
            log.warning(
                "models_not_found",
                msg=(
                    "Artefactos de modelo no encontrados. "
                    "El servicio arranca en modo degradado. "
                    "Ejecute el entrenamiento (Fase 2) para generar los modelos."
                ),
                model_a_exists=model_a_path.exists(),
                model_null_exists=model_null_path.exists(),
            )
            return

        try:
            import joblib

            self.model_a_artifact = joblib.load(model_a_path)
            self.model_null_artifact = joblib.load(model_null_path)
            # Model artifacts are dicts with 'booster' and 'feature_names'
            self.model_a = self.model_a_artifact["booster"]
            self.model_null = self.model_null_artifact["booster"]
            log.info(
                "models_loaded",
                model_a=str(model_a_path),
                model_null=str(model_null_path),
                model_a_features=len(self.model_a_artifact.get("feature_names", [])),
                model_null_features=len(self.model_null_artifact.get("feature_names", [])),
            )
        except Exception as e:
            log.error("model_load_error", error=str(e))
            return

        # Cargar Applicability Domain
        if ad_path.exists():
            try:
                with open(ad_path) as f:
                    ad_data = json.load(f)
                self.applicability_domain = {
                    "mean": np.array(ad_data["mean"]),
                    "cov_inv": np.array(ad_data["cov_inv"]),
                    "threshold": ad_data["threshold"],
                    "feature_names": ad_data.get("feature_names", []),
                    "feature_ranges": ad_data.get("feature_ranges", {}),
                }
                log.info("applicability_domain_loaded", threshold=ad_data["threshold"])
            except Exception as e:
                log.error("ad_load_error", error=str(e))

        # Cargar distribución de Delta
        if delta_path.exists():
            try:
                with open(delta_path) as f:
                    self.delta_distribution = json.load(f)
                log.info("delta_distribution_loaded")
            except Exception as e:
                log.error("delta_load_error", error=str(e))

        # Cargar training report
        if report_path.exists():
            try:
                with open(report_path) as f:
                    self.training_report = json.load(f)
                self._model_version = self.training_report.get("version", "unknown")
                log.info("training_report_loaded", version=self._model_version)
            except Exception as e:
                log.error("report_load_error", error=str(e))

        self._is_loaded = True
        log.info(
            "rescoring_ready",
            model_version=self._model_version,
            has_ad=self.applicability_domain is not None,
            has_delta_dist=self.delta_distribution is not None,
        )

    def get_info(self) -> dict[str, Any]:
        """Metadata del modelo para el endpoint /info."""
        if not self._is_loaded or self.training_report is None:
            return {
                "model_version": None,
                "training_date": None,
                "training_samples": None,
                "ndcg_at_10": None,
                "spearman": None,
                "applicability_domain_threshold": None,
                "families_trained": [],
            }

        report = self.training_report
        return {
            "model_version": report.get("version"),
            "training_date": report.get("training_date"),
            "training_samples": report.get("training_samples"),
            "ndcg_at_10": report.get("ndcg_at_10"),
            "spearman": report.get("spearman"),
            "applicability_domain_threshold": (
                self.applicability_domain["threshold"] if self.applicability_domain else None
            ),
            "families_trained": report.get("families_trained", []),
        }

    def predict(self, request) -> Any:
        """
        Pipeline completo de predicción.

        1. Filtro geométrico de poses
        2. Calcular varianza de poses (9 poses existentes)
        3. Extraer features
        4. Check Applicability Domain
        5. Predecir con Modelo A y Modelo NULL
        6. Calcular Delta
        """
        from pose_filter import PoseFilter
        from feature_extractor import InteractionFeatureExtractor
        from applicability_domain import ApplicabilityDomainChecker

        # Import response models from app module
        from app import (
            RescoreResponse,
            ApplicabilityDomainResult,
            PoseVarianceResult,
            DeltaResult,
        )

        warnings: list[str] = []

        # ── 1. Filtro geométrico de poses ────────────────────────────
        pose_filter = PoseFilter(settings)
        filter_results = pose_filter.filter_poses(request.poses)
        valid_poses = filter_results["valid_poses"]
        poses_passing = filter_results["poses_passing"]
        total_poses = len(request.poses)

        if not valid_poses:
            warnings.append(
                "Ninguna pose pasó el filtro geométrico. "
                "Usando pose de menor energía como fallback."
            )
            # Fallback: usar la pose con mejor score de Vina
            best_pose = min(request.poses, key=lambda p: p.vina_score)
            valid_poses = [best_pose]

        # ── 2. Varianza de poses (feature de incertidumbre, 0 CPU extra) ─
        vina_scores = [p.vina_score for p in request.poses]
        score_var = float(np.var(vina_scores)) if len(vina_scores) > 1 else 0.0
        score_range = float(max(vina_scores) - min(vina_scores)) if len(vina_scores) > 1 else 0.0

        if score_var < settings.pose_variance_low**2:
            stability = "ALTA"
        elif score_var > settings.pose_variance_high**2:
            stability = "BAJA"
            warnings.append(
                f"Varianza alta entre poses ({score_range:.1f} kcal/mol). "
                "El modo de unión no es único — la predicción es menos confiable."
            )
        else:
            stability = "MEDIA"

        pose_variance = PoseVarianceResult(
            score_variance=round(score_var, 4),
            score_range=round(score_range, 2),
            poses_analyzed=total_poses,
            poses_passing_filter=poses_passing,
            stability=stability,
        )

        # ── 3. Extraer features ──────────────────────────────────────
        extractor = InteractionFeatureExtractor()

        # Features 1D/2D (del request, pre-calculadas por backend)
        descriptors_1d2d = {
            "mw": request.molecular_weight,
            "logp": request.logp,
            "tpsa": request.tpsa,
            "hbd": float(request.hbd),
            "hba": float(request.hba),
            "rotatable_bonds": float(request.rotatable_bonds),
            "qed": request.qed,
        }

        # Features 3D + Vina (extraídas de la mejor pose válida)
        features_3d = extractor.extract_from_pose(
            valid_poses[0].pdbqt_block,
            request.target_pdb_path,
            smiles=request.smiles,
        )
        # Agregar vina_best_score como feature
        features_3d["vina_best_score"] = valid_poses[0].vina_score

        # Features de varianza de poses
        pose_features = {
            "pose_score_variance": score_var,
            "pose_score_range": score_range,
            "poses_passing_ratio": poses_passing / total_poses if total_poses > 0 else 0.0,
        }

        # Combinar todas las features
        all_features = {**descriptors_1d2d, **features_3d, **pose_features}

        # Compute derived features needed by v4
        all_features["log_mw"] = math.log(max(request.molecular_weight, 1.0))

        # ── 4. Check Applicability Domain ────────────────────────────
        ad_checker = ApplicabilityDomainChecker(self.applicability_domain)
        ad_result = ad_checker.check(descriptors_1d2d)

        if not ad_result.in_domain:
            warnings.append(
                f"⚠️ FUERA DEL DOMINIO DE APLICABILIDAD. "
                f"Distancia de Mahalanobis: {ad_result.mahalanobis_distance:.1f} "
                f"(umbral: {ad_result.threshold:.1f}). "
                f"La predicción ML NO se genera — confianza insuficiente."
            )
            # Devolver respuesta sin predicción ML
            return RescoreResponse(
                score_a=0.0,
                score_null=0.0,
                delta=DeltaResult(
                    delta=0.0,
                    semaphore="GRAY",
                    interpretation="Predicción no disponible — molécula fuera del dominio de aplicabilidad.",
                ),
                applicability_domain=ad_result,
                pose_variance=pose_variance,
                features_used=all_features,
                model_version=self._model_version or "unknown",
                inference_time_ms=0.0,
                warnings=warnings,
            )

        # ── 5. Predicción Modelo A y Modelo NULL ─────────────────────
        import xgboost as xgb

        # Modelo A: todas las features
        features_a = self._prepare_feature_vector(all_features, model="A")
        feature_names_a = self.model_a_artifact.get("feature_names", [])
        dm_a = xgb.DMatrix(features_a.reshape(1, -1), feature_names=feature_names_a)
        score_a = float(self.model_a.predict(dm_a)[0])

        # Modelo NULL: solo features 1D/2D (sin info 3D ni Vina)
        null_features_dict = {
            k: all_features.get(k, 0.0)
            for k in (self.model_null_artifact.get("feature_names", []))
        }
        features_null = self._prepare_feature_vector(null_features_dict, model="NULL")
        feature_names_null = self.model_null_artifact.get("feature_names", [])
        dm_null = xgb.DMatrix(features_null.reshape(1, -1), feature_names=feature_names_null)
        score_null = float(self.model_null.predict(dm_null)[0])

        # ── 6. Delta de Especificidad 3D ─────────────────────────────
        delta_val = score_a - score_null

        if delta_val > settings.delta_green_threshold:
            semaphore = "GREEN"
            interpretation = (
                f"ENCAJE ESPECÍFICO (Δ = {delta_val:+.2f}). "
                "La molécula tiene interacciones específicas con el receptor "
                "más allá de sus propiedades fisicoquímicas."
            )
        elif delta_val < settings.delta_red_threshold:
            semaphore = "RED"
            interpretation = (
                f"INCOMPATIBILIDAD GEOMÉTRICA (Δ = {delta_val:+.2f}). "
                "La geometría 3D es incompatible con el bolsillo del receptor. "
                "Las propiedades fisicoquímicas son favorables pero la forma impide buen encaje."
            )
        else:
            semaphore = "YELLOW"
            interpretation = (
                f"UNIÓN INESPECÍFICA (Δ = {delta_val:+.2f}). "
                "El score depende principalmente de propiedades fisicoquímicas genéricas. "
                "Riesgo de promiscuidad y off-targets."
            )

        delta = DeltaResult(
            delta=round(delta_val, 4),
            semaphore=semaphore,
            interpretation=interpretation,
        )

        return RescoreResponse(
            score_a=round(score_a, 4),
            score_null=round(score_null, 4),
            delta=delta,
            applicability_domain=ad_result,
            pose_variance=pose_variance,
            features_used=all_features,
            model_version=self._model_version or "unknown",
            inference_time_ms=0.0,  # se sobreescribe en app.py
            warnings=warnings,
        )

    def _prepare_feature_vector(
        self, features: dict[str, float], model: str
    ) -> np.ndarray:
        """
        Convertir dict de features a vector numpy en el orden esperado por el modelo.

        Uses the feature_names stored in the model artifact (saved during training).
        Each model stores its own feature list so ordering is guaranteed to match.
        """
        artifact = self.model_a_artifact if model == "A" else self.model_null_artifact
        if artifact and "feature_names" in artifact:
            feature_order = artifact["feature_names"]
        elif self.training_report and f"feature_order_{model.lower()}" in self.training_report:
            feature_order = self.training_report[f"feature_order_{model.lower()}"]
        else:
            feature_order = sorted(features.keys())
            log.warning(
                "feature_order_fallback",
                model=model,
                msg="Using alphabetical feature order — may cause incorrect predictions",
            )

        vector = []
        for feat_name in feature_order:
            val = features.get(feat_name, 0.0)
            vector.append(float(val))

        return np.array(vector, dtype=np.float64)
