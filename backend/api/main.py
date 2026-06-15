"""
api/main.py

Entrypoint principal de FastAPI para el MVP de MolDesign.

Objetivos de esta fase:
- arrancar correctamente,
- exponer el servicio químico existente,
- proveer health checks reales,
- inicializar recursos base,
- manejar errores de forma consistente.
"""

from __future__ import annotations

import os
import shutil
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from api.middleware import register_middleware
from api.routers.auth import router as auth_router
from api.routers.blockchain import router as blockchain_router
from api.routers.evaluation import router as evaluation_router
from api.routers.history import router as history_router
from api.routers.stats import router as stats_router
from api.routers.suggestions import router as suggestions_router
from api.routers.targets import router as targets_router
from chem.router import router as chem_router
from core.config import get_settings
from core.database import (
    check_database_health,
    close_engine,
    create_all_tables,
)
from core.exceptions import MolDesignError, VinaExecutableNotFound
from utils.cache import check_redis_health, close_redis_pool
from utils.file_handlers import check_storage_health, close_minio_client, ensure_bucket_exists
from utils.logger import get_logger, setup_logging

settings = get_settings()
log = get_logger(__name__)


def _check_vina_health() -> dict[str, Any]:
    path = settings.vina_executable_path
    resolved_path = None

    if os.path.exists(path):
        resolved_path = path
    else:
        resolved_path = shutil.which(path)
        if resolved_path is None:
            scripts_dir = Path(sys.executable).resolve().parent
            candidate = scripts_dir / f"{path}.exe"
            if candidate.exists():
                resolved_path = str(candidate)

    exists = resolved_path is not None
    return {
        "status": "healthy" if exists else "unhealthy",
        "path": resolved_path or path,
        "exists": exists,
    }


def _check_rdkit_health() -> dict[str, Any]:
    try:
        from rdkit import Chem
        from rdkit import __version__ as rdkit_version

        test_mol = Chem.MolFromSmiles("CC(=O)Oc1ccccc1C(=O)O")
        ok = test_mol is not None
        return {
            "status": "healthy" if ok else "unhealthy",
            "rdkit_version": rdkit_version,
            "test_passed": ok,
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e),
        }


async def _safe_health_check(name: str, checker) -> dict[str, Any]:
    try:
        result = checker()
        if hasattr(result, "__await__"):
            result = await result
        return result
    except Exception as e:
        log.warning("health check falló", component=name, error=str(e))
        return {
            "status": "unhealthy",
            "error": str(e),
        }


async def _bootstrap_runtime_resources() -> None:
    Path(settings.vina_temp_dir).mkdir(parents=True, exist_ok=True)
    await ensure_bucket_exists(settings.minio_bucket_poses)
    log.info("Bootstrap: MinIO bucket verificado")
    
    if settings.environment in {"development", "testing"}:
        await create_all_tables()
    
    if settings.is_production:
        if not os.path.exists(settings.vina_executable_path):
            raise VinaExecutableNotFound(settings.vina_executable_path)


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    log.info("iniciando aplicación MolDesign", environment=settings.environment)
    await _bootstrap_runtime_resources()
    yield
    await close_redis_pool()
    await close_minio_client()
    await close_engine()
    log.info("aplicación MolDesign detenida limpiamente")


from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from fastapi.middleware.cors import CORSMiddleware
from api.dynamic_limiter import limiter

app = FastAPI(
    title="MolDesign API",
    version="1.0.0-mvp",
    summary="Plataforma de diseño molecular asistido con pipeline científico reproducible.",
    description=(
        "MolDesign expone un pipeline científico basado en RDKit, AutoDock Vina y "
        "scoring explícito. La IA interpreta resultados ya calculados y no genera "
        "métricas químicas por sí misma."
    ),
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

from api.moldex import router as moldex_router

register_middleware(app)
app.include_router(auth_router)
app.include_router(blockchain_router)
app.include_router(chem_router)
app.include_router(evaluation_router)
app.include_router(history_router)
app.include_router(moldex_router)
app.include_router(targets_router)
app.include_router(suggestions_router)
app.include_router(stats_router)


@app.exception_handler(MolDesignError)
async def handle_moldesign_error(request: Request, exc: MolDesignError) -> JSONResponse:
    log.warning(
        "error controlado de aplicación",
        error_type=type(exc).__name__,
        message=exc.message,
        detail=exc.detail,
        path=request.url.path,
    )
    return JSONResponse(
        status_code=exc.http_code,
        content=exc.to_dict(),
    )


@app.exception_handler(Exception)
async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
    log.exception(
        "error inesperado no controlado",
        error_type=type(exc).__name__,
        path=request.url.path,
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "InternalServerError",
            "message": "Ocurrió un error interno no controlado",
            "detail": str(exc) if settings.is_development else None,
        },
    )


@app.get("/", tags=["Meta"])
async def root() -> dict[str, Any]:
    return {
        "name": "MolDesign API",
        "version": "1.0.0-mvp",
        "environment": settings.environment,
        "mission": "pipeline científico reproducible para diseño molecular asistido",
    }


@app.get("/health", tags=["Meta"], summary="Estado integral del sistema")
async def health() -> JSONResponse:
    db_health = await _safe_health_check("database", check_database_health)
    redis_health = await _safe_health_check("redis", check_redis_health)
    storage_health = await _safe_health_check("storage", check_storage_health)
    rdkit_health = await _safe_health_check("rdkit", _check_rdkit_health)
    vina_health = await _safe_health_check("vina", _check_vina_health)

    # DiffDock (servicio complementario, no bloqueante)
    async def _check_diffdock():
        from services.diffdock.service import get_diffdock_service
        return await get_diffdock_service().check_health()

    diffdock_health = await _safe_health_check("diffdock", _check_diffdock)

    components = {
        "database": db_health,
        "redis": redis_health,
        "storage": storage_health,
        "rdkit": rdkit_health,
        "vina": vina_health,
        "diffdock": diffdock_health,
    }

    # DiffDock es opcional — no marca el sistema como degradado
    core_components = {"database", "redis", "storage", "rdkit", "vina"}
    unhealthy_components = [
        name
        for name, payload in components.items()
        if name in core_components and payload.get("status") != "healthy"
    ]

    status_code = (
        status.HTTP_200_OK
        if not unhealthy_components
        else status.HTTP_503_SERVICE_UNAVAILABLE
    )

    return JSONResponse(
        status_code=status_code,
        content={
            "status": "healthy" if not unhealthy_components else "degraded",
            "environment": settings.environment,
            "unhealthy_components": unhealthy_components,
            "components": components,
        },
    )