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
from core.database import get_db_session, close_engine
from core.models import AIReportRequest, EvaluationResultRead, JobStatus, MoleculeStatus
from db.repository import Repository
from scoring.engine import calculate_score_breakdown
from services.ai.interpreter import safe_generate_ai_report
from services.docking.vina_service import run_vina_docking
from services.docking.rescoring_client import get_ml_rescore
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
            try:
                _celery_loop = asyncio.get_event_loop()
            except RuntimeError:
                _celery_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(_celery_loop)
            log.info({"event": "event loop persistente inicializado para Celery worker"})
        return _celery_loop


async def _run_full_evaluation_async(
    task_id: str,
    smiles: str,
    target_pdb_id: str,
    molecule_name: str | None = None,
    is_control: bool = False,
    user_id: str | None = None,
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
            user_id=UUID(user_id) if user_id else None,
        )

        # [CACHE FIX] Invalidar cache previo para forzar recalculo con nueva logica v4
        from utils.cache import CacheKey
        await cache.delete(CacheKey.properties(molecule.smiles_hash))
        await cache.delete(CacheKey.docking(molecule.smiles_hash, target.pdb_id))

        try:
            properties = calculate_properties(smiles)
            await repository.set_molecule_status(molecule.id, MoleculeStatus.VALIDATED)

            # --- [NUEVO] Filtro SA Score (Accesibilidad Sintética) ---
            # Si la molécula es imposible de fabricar, abortamos para evitar
            # falsos positivos científicos.
            if properties.sa_score > 6.0:
                log.warning({
                    "event": "synthetic_infeasibility_abort",
                    "smiles": smiles,
                    "sa_score": properties.sa_score
                })
                await repository.upsert_evaluation_result(
                    molecule_id=molecule.id,
                    properties=properties,
                    error_message=f"Inviabilidad Sintetica: SA Score {properties.sa_score} > 6.0. Esta molecula es probablemente imposible de sintetizar en laboratorio.",
                    is_control=is_control,
                    celery_task_id=task_id,
                )
                await repository.set_molecule_status(molecule.id, MoleculeStatus.FAILED)
                await cache.set_job_progress(task_id, 100, "failed")
                return {
                    "task_id": task_id,
                    "molecule_id": str(molecule.id),
                    "error": "Synthetic Infeasibility",
                    "sa_score": properties.sa_score
                }
            
            # --- [NUEVO] Programar limpieza automática si el score es bajo ---
            if breakdown.total_score < 60.0:
                log.info({"event": "scheduling_cleanup_low_score", "molecule_id": str(molecule.id), "score": breakdown.total_score})
                cleanup_unsaved_molecule.apply_async(args=[str(molecule.id)], countdown=3600) # 1 hora

            await repository.upsert_evaluation_result(
                molecule_id=molecule.id,
                properties=properties,
                is_control=is_control,
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
                target_center=(target.grid_center_x, target.grid_center_y, target.grid_center_z),
                target_size=(target.grid_size_x, target.grid_size_y, target.grid_size_z),
                hotspots=target.hotspots,
            )

            await cache.set_job_progress(task_id, 80, "scoring")
            
            # --- [NUEVO PASO] ML Rescoring Correction ---
            # Intentamos corregir el score de Vina con el "Cerebro Espacial" (XGBoost)
            try:
                # El microservicio necesita los bloques PDBQT de las poses
                # docking.poses ya contiene los datos necesarios
                ml_result = await get_ml_rescore(
                    smiles=smiles,
                    target_pdb_path=f"/data/targets/{target.pdb_id}.pdb",
                    poses=[p.model_dump() for p in docking.poses],
                    properties=properties,
                    grid_center=[target.grid_center_x, target.grid_center_y, target.grid_center_z],
                    grid_size=[target.grid_size_x, target.grid_size_y, target.grid_size_z]
                )
                
                if not ml_result.get("fallback"):
                    # El modelo devuelve pKi (score_a). 
                    # Convertimos pKi a kcal/mol para inyectarlo en el normalizador.
                    # DeltaG = -1.36 * pKi (aprox a 300K)
                    pki_a = ml_result.get("score_a", 0.0)
                    if pki_a > 0:
                        corrected_kcal = -1.36 * pki_a
                        log.info({
                            "event": "ml_rescoring_applied",
                            "vina_kcal": docking.best_affinity,
                            "ml_pki": pki_a,
                            "ml_kcal_equivalent": corrected_kcal
                        })
                        # Inyectamos la afinidad corregida
                        docking.best_affinity = corrected_kcal
                        # También guardamos warnings científicos del modelo si los hay
                        if ml_result.get("warnings"):
                            docking.scientific_warnings.extend(ml_result["warnings"])
            except Exception as ml_err:
                log.warning({"event": "ml_rescoring_skipped", "error": str(ml_err)})

            breakdown = calculate_score_breakdown(
                docking, 
                properties, 
                is_control=is_control,
                target_hotspots=target.hotspots,
                affinity_threshold=target.affinity_threshold if target.affinity_threshold is not None else -7.5
            )
            await repository.upsert_evaluation_result(
                molecule_id=molecule.id,
                properties=properties,
                docking=docking,
                scores=breakdown.model_dump(),
                is_control=is_control,
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
                # Programar limpieza para fallos inesperados
                cleanup_unsaved_molecule.apply_async(args=[str(molecule.id)], countdown=3600)
            except Exception as db_exc:
                log.error(
                    "no se pudo persistir estado FAILED en DB",
                    molecule_id=str(molecule.id),
                    db_error=str(db_exc),
                )
            raise


@celery_app.task(name="moldesign.cleanup_unsaved_molecule")
def cleanup_unsaved_molecule(molecule_id: str):
    """
    Tarea de limpieza diferida. 
    Borra la molécula si no ha sido guardada y tiene un score bajo o falló.
    """
    async def _cleanup():
        async with get_db_session() as db:
            repository = Repository(db)
            mol = await repository.get_molecule(UUID(molecule_id))
            if not mol:
                return False
            
            # Si el usuario ya la guardó explícitamente, NUNCA borrar.
            if mol.is_saved:
                log.info({"event": "cleanup_aborted_saved", "molecule_id": molecule_id})
                return False
                
            # Criterios de borrado:
            # 1. Falló la evaluación
            # 2. El score final es inferior al umbral de "prometedora" (60.0)
            should_delete = False
            if mol.status == MoleculeStatus.FAILED:
                should_delete = True
                log.info({"event": "cleanup_reason_failed", "molecule_id": molecule_id})
            elif mol.evaluation_result and mol.evaluation_result.total_score is not None:
                if mol.evaluation_result.total_score < 60.0:
                    should_delete = True
                    log.info({"event": "cleanup_reason_low_score", "molecule_id": molecule_id, "score": mol.evaluation_result.total_score})
            
            if should_delete:
                success = await repository.delete_molecule(mol.id)
                await db.commit()
                return success
            
            log.info({"event": "cleanup_skipped_promising", "molecule_id": molecule_id})
            return False

    loop = _get_celery_loop()
    return loop.run_until_complete(_cleanup())


@celery_app.task(name="moldesign.celery_ping")
def celery_ping() -> dict[str, str]:
    return {"status": "ok", "service": "celery"}


@celery_app.task(name="moldesign.run_full_evaluation", bind=True)
def run_full_evaluation(
    self,
    smiles: str,
    target_pdb_id: str,
    molecule_name: str | None = None,
    is_control: bool = False,
    user_id: str | None = None,
) -> dict[str, Any]:
    """
    Celery task que ejecuta el pipeline completo de evaluación.

    Cada tarea corre en su propio loop de asyncio aislado.
    """
    bind_context(task_id=self.request.id, target=target_pdb_id)
    loop = _get_celery_loop()
    return loop.run_until_complete(_run_full_evaluation_async(
        task_id=self.request.id,
        smiles=smiles,
        target_pdb_id=target_pdb_id,
        molecule_name=molecule_name,
        is_control=is_control,
        user_id=user_id,
    ))


def submit_evaluation_job(
    smiles: str,
    target_pdb_id: str,
    molecule_name: str | None = None,
    is_control: bool = False,
    user_id: str | None = None,
):
    return run_full_evaluation.delay(smiles=smiles, target_pdb_id=target_pdb_id, molecule_name=molecule_name, is_control=is_control, user_id=user_id)


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
                    if evaluation.molecule and evaluation.molecule.target:
                        result_payload.target_hotspots = evaluation.molecule.target.hotspots
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
