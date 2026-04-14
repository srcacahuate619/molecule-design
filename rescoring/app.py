"""
rescoring/app.py

Microservicio de ML Rescoring — FastAPI application.

Este servicio corre en un contenedor separado (Python 3.12) y se comunica
con el backend principal (Python 3.14) vía HTTP en puerto 8001.

Responsabilidades:
  - POST /rescore  → recibe pose(s) + SMILES, devuelve score ML + Delta + warnings
  - GET  /health   → health check (modelo cargado, dependencias OK)
  - GET  /info     → metadata del modelo (versión, métricas, fecha de entrenamiento)
"""

from __future__ import annotations

import time
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from config import get_rescoring_settings
from logger import get_logger
from model_manager import ModelManager

log = get_logger(__name__)
settings = get_rescoring_settings()

# ─────────────────────────────────────────────
# Pydantic models (contratos de API)
# ─────────────────────────────────────────────


class PoseData(BaseModel):
    """Una pose individual de Vina."""

    pdbqt_block: str = Field(..., description="Bloque PDBQT de la pose")
    vina_score: float = Field(..., description="Score de Vina (kcal/mol)")
    rmsd_lb: float = Field(0.0, description="RMSD lower bound vs pose 1")
    rmsd_ub: float = Field(0.0, description="RMSD upper bound vs pose 1")


class RescoreRequest(BaseModel):
    """Request para rescoring de una molécula."""

    smiles: str = Field(..., description="SMILES canónico de la molécula")
    target_pdb_path: str = Field(..., description="Path al archivo PDB del target")
    poses: list[PoseData] = Field(..., description="Lista de poses de Vina (típicamente 9)")
    # Propiedades 1D/2D pre-calculadas por el backend
    molecular_weight: float = Field(..., description="Peso molecular (Da)")
    logp: float = Field(..., description="LogP calculado")
    tpsa: float = Field(..., description="TPSA (Å²)")
    hbd: int = Field(..., description="Hydrogen Bond Donors")
    hba: int = Field(..., description="Hydrogen Bond Acceptors")
    rotatable_bonds: int = Field(..., description="Rotatable bonds")
    qed: float = Field(..., description="QED score")


class ApplicabilityDomainResult(BaseModel):
    """Resultado del check de Applicability Domain."""

    in_domain: bool = Field(..., description="¿Molécula dentro del dominio de entrenamiento?")
    mahalanobis_distance: float = Field(..., description="Distancia de Mahalanobis")
    threshold: float = Field(..., description="Umbral (percentil 99 del training set)")
    out_of_range_descriptors: list[str] = Field(
        default_factory=list,
        description="Descriptores fuera de rango (e.g., 'MW: 1250 Da, rango training: 150-750')",
    )


class PoseVarianceResult(BaseModel):
    """Incertidumbre derivada de las 9 poses de Vina."""

    score_variance: float = Field(..., description="Varianza de scores entre las 9 poses")
    score_range: float = Field(..., description="Rango (max - min) de scores")
    poses_analyzed: int = Field(..., description="Número de poses analizadas")
    poses_passing_filter: int = Field(..., description="Poses que pasan el filtro geométrico")
    stability: str = Field(..., description="ALTA / MEDIA / BAJA")


class DeltaResult(BaseModel):
    """Delta de Especificidad 3D."""

    delta: float = Field(..., description="score_A - score_NULL")
    semaphore: str = Field(..., description="GREEN / YELLOW / RED")
    interpretation: str = Field(..., description="Interpretación en lenguaje natural")


class RescoreResponse(BaseModel):
    """Respuesta completa del rescoring."""

    # Scores
    score_a: float = Field(..., description="Score del Modelo A (ranking, features completas)")
    score_null: float = Field(..., description="Score del Modelo NULL (solo descriptores 1D/2D)")

    # Delta
    delta: DeltaResult

    # Applicability Domain
    applicability_domain: ApplicabilityDomainResult

    # Pose variance
    pose_variance: PoseVarianceResult

    # Features usadas (para auditoría)
    features_used: dict[str, float] = Field(
        default_factory=dict,
        description="Features extraídas y sus valores (transparencia)",
    )

    # Metadata
    model_version: str = Field(..., description="Versión del modelo usado")
    inference_time_ms: float = Field(..., description="Tiempo de inferencia en ms")

    # Warnings
    warnings: list[str] = Field(default_factory=list, description="Warnings científicos")


class HealthResponse(BaseModel):
    """Health check response."""

    status: str
    model_loaded: bool
    model_version: str | None
    prolif_available: bool
    xgboost_available: bool


class ModelInfoResponse(BaseModel):
    """Metadata del modelo."""

    model_version: str | None
    training_date: str | None
    training_samples: int | None
    ndcg_at_10: float | None
    spearman: float | None
    applicability_domain_threshold: float | None
    families_trained: list[str]


# ─────────────────────────────────────────────
# Lifespan — carga del modelo al arrancar
# ─────────────────────────────────────────────

model_manager = ModelManager()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Cargar modelo al arrancar, liberar al cerrar."""
    log.info("rescoring_startup", msg="Iniciando microservicio de rescoring")
    model_manager.load_models()
    yield
    log.info("rescoring_shutdown", msg="Cerrando microservicio de rescoring")


# ─────────────────────────────────────────────
# App FastAPI
# ─────────────────────────────────────────────

app = FastAPI(
    title="MolDesign ML Rescoring Service",
    description=(
        "Microservicio de rescoring ML para MolDesign. "
        "Ejecuta predicción con Modelo A (completo) y Modelo NULL (control), "
        "calcula Delta de Especificidad 3D, verifica Applicability Domain, "
        "y reporta incertidumbre de poses."
    ),
    version="0.1.0",
    lifespan=lifespan,
)


# ─────────────────────────────────────────────
# Endpoints
# ─────────────────────────────────────────────


@app.get("/health", response_model=HealthResponse)
async def health():
    """Health check — verifica que el modelo esté cargado y las dependencias disponibles."""
    prolif_ok = _check_prolif()
    xgboost_ok = _check_xgboost()

    status = "healthy" if model_manager.is_loaded and prolif_ok and xgboost_ok else "degraded"

    return HealthResponse(
        status=status,
        model_loaded=model_manager.is_loaded,
        model_version=model_manager.model_version,
        prolif_available=prolif_ok,
        xgboost_available=xgboost_ok,
    )


@app.get("/info", response_model=ModelInfoResponse)
async def model_info():
    """Metadata del modelo cargado."""
    return model_manager.get_info()


@app.post("/rescore", response_model=RescoreResponse)
async def rescore(request: RescoreRequest):
    """
    Rescoring ML completo de una molécula.

    Pipeline:
    1. Filtro geométrico de poses
    2. Extracción de features (1D/2D + 3D + Vina)
    3. Check de Applicability Domain (Mahalanobis)
    4. Si fuera de dominio → devolver warning, sin predicción ML
    5. Predicción Modelo A y Modelo NULL
    6. Delta de Especificidad 3D
    7. Varianza de poses como medida de incertidumbre
    """
    start_time = time.perf_counter()

    if not model_manager.is_loaded:
        raise HTTPException(
            status_code=503,
            detail=(
                "Modelo de rescoring no cargado. "
                "El microservicio arrancó sin artefactos de modelo. "
                "Ejecute el entrenamiento primero (Fase 2)."
            ),
        )

    try:
        result = model_manager.predict(request)
    except Exception as e:
        log.error("rescore_error", error=str(e), smiles=request.smiles)
        raise HTTPException(
            status_code=500,
            detail=f"Error en rescoring: {str(e)}",
        )

    elapsed_ms = (time.perf_counter() - start_time) * 1000
    result.inference_time_ms = elapsed_ms

    log.info(
        "rescore_ok",
        smiles=request.smiles[:50],
        score_a=result.score_a,
        delta=result.delta.delta,
        in_domain=result.applicability_domain.in_domain,
        time_ms=round(elapsed_ms, 1),
    )

    return result


# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────


def _check_prolif() -> bool:
    """Verificar que ProLIF + MDAnalysis están importables."""
    try:
        import prolif          # noqa: F401
        import MDAnalysis      # noqa: F401
        return True
    except ImportError:
        return False


def _check_xgboost() -> bool:
    """Verificar que XGBoost está importable."""
    try:
        import xgboost  # noqa: F401
        return True
    except ImportError:
        return False
