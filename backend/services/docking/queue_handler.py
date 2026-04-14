"""Tasks Celery para evaluación completa del MVP."""

from __future__ import annotations

import asyncio
import threading
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from celery.result import AsyncResult

from api.celery_app import celery_app
from chem.conformer import generate_conformer
from chem.properties import calculate_properties
from core.database import get_db_session
from core.models import AIReportRequest, EvaluationResultRead, JobStatus, MoleculeStatus
from db.repository import Repository
from scoring.engine import calculate_score_breakdown
from services.ai.interpreter import safe_generate_ai_report
from services.docking.vina_service import run_vina_docking
from utils.cache import cache
from utils.logger import bind_context, get_logger

log = get_logger(__name__)


def _parse_iso_or_none(value: str | None) -> datetime | None:
    """Parse an ISO timestamp string from cache, or return None."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except (ValueError, TypeError):
        return None


# ── Event loop persistente para Celery ─────────────────────────────────────────
#
# Los clientes async (asyncpg, aioredis, aiohttp/MinIO) mantienen pools de
# conexiones vinculadas al event loop que las creó. Si creamos un loop por
# task (asyncio.run), al cerrar el loop todas las conexiones quedan huérfanas
# y la siguiente task falla con "Event loop is closed".
#
# Solución: mantener UN event loop vivo mientras viva el proceso del worker.
# Con --pool=solo --concurrency=1, solo corre una task a la vez, así que no
# hay race conditions.

_celery_loop: asyncio.AbstractEventLoop | None = None
_celery_loop_lock = threading.Lock()


def _get_celery_loop() -> asyncio.AbstractEventLoop:
    """Retorna el event loop persistente del worker, creándolo si no existe."""
    global _celery_loop
    with _celery_loop_lock:
        if _celery_loop is None or _celery_loop.is_closed():
            _celery_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(_celery_loop)
            log.info({"event": "event loop persistente creado para Celery worker"})
        return _celery_loop


async def _run_full_evaluation_async(
    task_id: str,
    smiles: str,
    target_pdb_id: str,
    molecule_name: str | None = None,
) -> dict[str, Any]:
    async with get_db_session() as db:
        repository = Repository(db)
        target = await repository.get_target_by_pdb_id(target_pdb_id)
        if target is None:
            target = await repository.ensure_default_target()

        molecule = await repository.create_or_get_molecule(
            smiles=smiles,
            target_pdb_id=target.pdb_id,
            name=molecule_name,
        )

        try:
            properties = calculate_properties(smiles)
            await repository.set_molecule_status(molecule.id, MoleculeStatus.VALIDATED)

            await repository.upsert_evaluation_result(
                molecule_id=molecule.id,
                properties=properties,
                celery_task_id=task_id,
            )

            await cache.set_job_progress(task_id, 20, "conformer")
            conformer = await generate_conformer(smiles)
            log.info({
                "event": "conformer listo para docking",
                "conformer_path": conformer["conformer_path"]
            })

            await repository.set_molecule_status(molecule.id, MoleculeStatus.DOCKING)
            await cache.set_job_progress(task_id, 55, "docking")
            docking = await run_vina_docking(
                smiles_hash=molecule.smiles_hash,
                target_pdb_id=target.pdb_id,
                target_chain=target.chain,
            )

            await cache.set_job_progress(task_id, 80, "scoring")
            breakdown = calculate_score_breakdown(docking, properties)
            ai_report = await safe_generate_ai_report(
                AIReportRequest(
                    molecule_smiles=molecule.smiles,
                    target_name=target.name,
                    affinity_kcal=docking.best_affinity,
                    affinity_score=breakdown.affinity_score,
                    properties=properties,
                    score_breakdown=breakdown,
                    parent_smiles=None,
                    mutation_type=molecule.mutation_type,
                )
            )
            await repository.upsert_evaluation_result(
                molecule_id=molecule.id,
                properties=properties,
                docking=docking,
                scores=breakdown.model_dump(),
                ai_report=ai_report,
                celery_task_id=task_id,
            )
            await repository.set_molecule_status(molecule.id, MoleculeStatus.EVALUATED)

            result = await repository.get_evaluation_result(molecule.id)
            await cache.set_job_progress(task_id, 100, "done")

            return {
                "task_id": task_id,
                "molecule_id": str(molecule.id),
                "smiles_hash": molecule.smiles_hash,
                "target_pdb_id": target.pdb_id,
                "total_score": breakdown.total_score,
                "best_affinity": docking.best_affinity,
                "evaluation_result_id": str(result.id) if result else None,
            }

        except Exception as exc:
            # ── Error recovery: garantiza que la molécula no quede en
            # estado intermedio (VALIDATED/DOCKING) sin explicación. ──────
            detail = getattr(exc, 'detail', None)
            # Forzar que detail sea string para logging y DB
            if detail is None:
                detail_str = '(sin detail)'
            elif not isinstance(detail, str):
                detail_str = str(detail)
            else:
                detail_str = detail
            log.error(
                "pipeline de evaluación falló",
                task_id=task_id,
                molecule_id=str(molecule.id),
                error=str(exc),
                error_type=type(exc).__name__,
                error_detail=detail_str,
            )
            try:
                await repository.set_molecule_status(
                    molecule.id, MoleculeStatus.FAILED
                )
                await repository.upsert_evaluation_result(
                    molecule_id=molecule.id,
                    error_message=f"{type(exc).__name__}: {exc}\nDetail: {detail_str}",
                    celery_task_id=task_id,
                )
            except Exception as db_exc:
                log.error(
                    "no se pudo persistir estado FAILED en DB",
                    molecule_id=str(molecule.id),
                    db_error=str(db_exc),
                )
            raise


@celery_app.task(name="moldesign.celery_ping")
def celery_ping() -> dict[str, str]:
    return {"status": "ok", "service": "celery"}


@celery_app.task(name="moldesign.run_full_evaluation", bind=True)
def run_full_evaluation(
    self,
    smiles: str,
    target_pdb_id: str,
    molecule_name: str | None = None,
) -> dict[str, Any]:
    """
    Celery task que ejecuta el pipeline completo de evaluación.

    Usa un event loop persistente compartido entre todas las tasks del worker.
    Esto mantiene las conexiones async (asyncpg, redis, MinIO) vivas entre tasks,
    evitando el error "Event loop is closed" que ocurre al crear/destruir loops.
    """
    bind_context(task_id=self.request.id, target=target_pdb_id)
    loop = _get_celery_loop()
    return loop.run_until_complete(
        _run_full_evaluation_async(
            task_id=self.request.id,
            smiles=smiles,
            target_pdb_id=target_pdb_id,
            molecule_name=molecule_name,
        )
    )


def submit_evaluation_job(
    smiles: str,
    target_pdb_id: str,
    molecule_name: str | None = None,
):
    return run_full_evaluation.delay(smiles=smiles, target_pdb_id=target_pdb_id, molecule_name=molecule_name)


async def get_job_status(task_id: str) -> JobStatus:
    progress = await cache.get_job_progress(task_id)
    async_result = AsyncResult(task_id, app=celery_app)

    status_value = async_result.status
    error = None
    result_payload: EvaluationResultRead | None = None

    if async_result.successful():
        async_result_payload = async_result.result or {}
        molecule_id = async_result_payload.get("molecule_id")
        if molecule_id:
            async with get_db_session() as db:
                repository = Repository(db)
                evaluation = await repository.get_evaluation_result(UUID(molecule_id))
                if evaluation is not None:
                    result_payload = EvaluationResultRead.model_validate(evaluation)
    elif async_result.failed():
        error = str(async_result.result)

    return JobStatus(
        task_id=task_id,
        status=status_value,
        progress=(progress or {}).get("progress", 0),
        result=result_payload,
        error=error,
        started_at=_parse_iso_or_none((progress or {}).get("started_at")),
        finished_at=_parse_iso_or_none((progress or {}).get("finished_at")),
    )
