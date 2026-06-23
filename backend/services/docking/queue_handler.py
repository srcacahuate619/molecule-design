"""Tasks Celery para evaluación completa del MVP."""

from __future__ import annotations

import asyncio
import threading
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from celery.result import AsyncResult
from celery.exceptions import SoftTimeLimitExceeded

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
from utils.scientific import audit_scientific_quality

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
    grid_center: tuple[float, float, float] | None = None,
    grid_size: tuple[float, float, float] | None = None,
    custom_hotspots: list[str] | None = None,
    peptide_docking_engine: str | None = "diffpepdock",
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



        try:
            properties = calculate_properties(smiles)
            await repository.set_molecule_status(molecule.id, MoleculeStatus.VALIDATED)

            # --- [NUEVO] Filtro SA Score (Accesibilidad Sintética) ---
            # Si la molécula es imposible de fabricar, abortamos para evitar
            # falsos positivos científicos.
            if properties.sa_score > 7.0:
                log.warning({
                    "event": "synthetic_infeasibility_abort",
                    "smiles": smiles,
                    "sa_score": properties.sa_score
                })
                await repository.upsert_evaluation_result(
                    molecule_id=molecule.id,
                    properties=properties,
                    error_message=f"Inviabilidad Sintetica: SA Score {properties.sa_score} > 7.0. Esta molecula es probablemente imposible de sintetizar en laboratorio.",
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
            
            await repository.upsert_evaluation_result(
                molecule_id=molecule.id,
                properties=properties,
                is_control=is_control,
                celery_task_id=task_id,
            )

            # Pre-calcular hotspots en scope
            box_center = tuple(grid_center) if grid_center is not None else (target.grid_center_x, target.grid_center_y, target.grid_center_z)
            box_size = tuple(grid_size) if grid_size is not None else (target.grid_size_x, target.grid_size_y, target.grid_size_z)

            active_hotspots = target.hotspots
            if custom_hotspots is not None:
                target_hotspots_map = {h.get("name"): h.get("importance", 1.0) for h in (target.hotspots or [])}
                active_hotspots = [
                    {"name": h_name, "importance": target_hotspots_map.get(h_name, 1.0)}
                    for h_name in custom_hotspots
                ]

            # Detección autónoma de tipo de molécula (péptido o organometálica)
            is_peptide = False
            is_organometallic = False
            metals_in_mol = set()
            
            try:
                from rdkit import Chem
                mol = Chem.MolFromSmiles(smiles)
                if mol:
                    # Detección Enterprise de Péptidos vía Patrones Estructurales SMARTS
                    # Busca el patrón del esqueleto peptídico: [N]-[C.alpha]-[C](=O)
                    peptide_backbone = Chem.MolFromSmarts("[NX3][CX4][CX3](=[OX1])")
                    matches = mol.GetSubstructMatches(peptide_backbone)
                    # Exigimos al menos 4 enlaces peptídicos secuenciales para considerarlo un péptido o peptidomimético pesado
                    is_peptide = (len(matches) >= 4 and properties.molecular_weight > 600)
                    
                    # Detectar metales
                    metals_in_mol = {atom.GetSymbol() for atom in mol.GetAtoms()} & {
                        "Fe", "Cu", "Zn", "Mn", "Co", "Ni", "Cr", "V", "Ti", "Mo", "W", "Pt"
                    }
                    is_organometallic = len(metals_in_mol) > 0
            except Exception as e:
                log.warning("Fallo al inspeccionar tipo de molécula", error=str(e))

            scientific_warnings = []
            docking = None

            # Nivel 3: Docking Peptídico Autónomo
            if is_peptide:
                log.info({"event": "routing_to_level_3_peptide", "molecule_id": str(molecule.id), "engine": peptide_docking_engine})
                await cache.set_job_progress(task_id, 40, "peptide_folding")
                
                from utils.file_handlers import StoragePath, download_pdb_from_rcsb, download_text, object_exists, upload_text
                raw_path = StoragePath.target_raw(target.pdb_id)
                
                temp_pdb_path = ""
                try:
                    if await object_exists(raw_path):
                        pdb_content = await download_text(raw_path)
                    else:
                        pdb_content = await download_pdb_from_rcsb(target.pdb_id)
                        await upload_text(pdb_content, raw_path)
                    
                    import tempfile
                    with tempfile.NamedTemporaryFile(suffix=".pdb", delete=False, mode="w", encoding="utf-8") as temp_pdb:
                        temp_pdb.write(pdb_content)
                        temp_pdb_path = temp_pdb.name
                except Exception as e:
                    log.warning("No se pudo preparar PDB temporal del target para Nivel 3", error=str(e))

                ml_res = None
                try:
                    if peptide_docking_engine == "colabfold" and temp_pdb_path:
                        from services.colabfold.service import get_colabfold_service
                        ml_res = await get_colabfold_service().predict(temp_pdb_path, smiles)
                    elif temp_pdb_path:
                        from services.diffpepdock.service import get_diffpepdock_service
                        ml_res = await get_diffpepdock_service().predict(
                            temp_pdb_path, smiles, grid_center=grid_center, grid_size=grid_size
                        )
                finally:
                    # [FIX #2] Limpiar el archivo temporal del disco para evitar leak de espacio
                    if temp_pdb_path:
                        import os
                        try:
                            os.unlink(temp_pdb_path)
                        except OSError:
                            pass

                if ml_res and ml_res.success and ml_res.poses:
                    log.info("Predicción de Nivel 3 completada con éxito")
                    from rdkit import Chem
                    from chem.conformer import _mol_to_sdf_string
                    from utils.refinement import refine_receptor_peptide_complex
                    from core.config import get_settings
                    
                    settings = get_settings()
                    sdf_parts = []
                    for p in ml_res.poses:
                        # Refinamiento estructural con restricciones.
                        # [FIX #4] ColabFoldPose usa 'complex_pdb', DiffPepDockPose usa 'ligand_pdb'.
                        # getattr con fallback garantiza compatibilidad con ambos tipos de resultado.
                        peptide_pdb = getattr(p, "ligand_pdb", None) or getattr(p, "complex_pdb", "")
                        if settings.peptide_refinement_enabled and pdb_content:
                            try:
                                peptide_pdb = refine_receptor_peptide_complex(pdb_content, peptide_pdb)
                            except Exception as re_err:
                                log.warning("Fallo inesperado al llamar refine_receptor_peptide_complex", error=str(re_err))

                        mol_pep = Chem.MolFromPDBBlock(peptide_pdb, sanitize=False)
                        if mol_pep:
                            try:
                                Chem.SanitizeMol(mol_pep)
                            except Exception:
                                pass
                            mol_pep.SetProp("SMILES", smiles)
                            mol_pep.SetProp("_Name", f"Pose_{p.rank}")
                            sdf_parts.append(_mol_to_sdf_string(mol_pep, smiles))
                    
                    sdf_content = "".join(sdf_parts)
                    poses_path = StoragePath.docking_poses(molecule.smiles_hash, target.pdb_id)
                    await upload_text(sdf_content, poses_path)
                    
                    if peptide_docking_engine == "colabfold":
                        best_affinity = -10.0 * (ml_res.best_iptm if ml_res.best_iptm is not None else 0.7)
                        scientific_warnings.append(
                            f"Modo Docking Peptídico Activo (ColabFold): Complejo plegado de novo. "
                            f"Confianza de interfaz (ipTM): {ml_res.best_iptm:.2f}, pLDDT medio: {ml_res.best_plddt:.1f}."
                        )
                    else:
                        conf = ml_res.best_confidence if ml_res.best_confidence is not None else 4.0
                        best_affinity = max(-12.0, min(-4.0, -1.5 * conf))
                        scientific_warnings.append(
                            f"Modo Docking Peptídico Activo (DiffPepDock): Poses de acoplamiento generadas por difusión. "
                            f"Confianza del modelo: {conf:.2f}."
                        )
                    
                    from core.models import DockingPose, DockingResult
                    poses = []
                    for i, p in enumerate(ml_res.poses):
                        aff = best_affinity + (i * 0.5)
                        poses.append(DockingPose(rank=p.rank, affinity=aff, rmsd_lb=p.rmsd if p.rmsd else 0.0, rmsd_ub=p.rmsd if p.rmsd else 0.0))
                    
                    docking = DockingResult(
                        best_affinity=best_affinity,
                        poses=poses,
                        poses_file_path=poses_path,
                        parsing_source="sdf",
                        vina_version=f"{peptide_docking_engine.upper()}-v1.0",
                        vina_random_seed=42,
                        scientific_warnings=scientific_warnings,
                    )
                else:
                    msg = ml_res.error if ml_res else "Sin respuesta del servicio"
                    log.warning("Fallo en Nivel 3, cayendo a Vina estándar", error=msg)
                    scientific_warnings.append(f"Fallo en Docking Peptídico ({msg}). Se usó AutoDock Vina como fallback.")

            # Nivel 4: Detección de compuestos organometálicos
            # [FIX] El warning anterior implicaba que xtb+AD4 estaban corriendo.
            # Honestidad: los detectamos, pero actualmente corremos Vina como aproximación.
            # AD4 + cargas GFN2-xTB está planificado para una versión futura.
            if is_organometallic and not is_peptide:
                log.info({"event": "metal_detected_vina_fallback", "molecule_id": str(molecule.id), "metals": list(metals_in_mol)})
                scientific_warnings.append(
                    f"⚠️ Metales de transición detectados: {list(metals_in_mol)}. "
                    "Se usa AutoDock Vina como aproximación. "
                    "El docking cuántico con GFN2-xTB + AutoDock 4 está en desarrollo "
                    "y se activará automáticamente en una versión futura. "
                    "Los resultados de afinidad pueden ser menos precisos para compuestos de coordinación."
                )

            # Si no se ejecutó Nivel 3, corremos Vina de forma estándar
            if docking is None:
                await cache.set_job_progress(task_id, 20, "conformer")
                conformer = await generate_conformer(smiles)
                log.info({
                    "event": "conformer listo para docking",
                    "conformer_path": conformer["conformer_path"]
                })

                await repository.set_molecule_status(molecule.id, MoleculeStatus.DOCKING)
                await cache.set_job_progress(task_id, 55, "docking")

                docking = await run_vina_docking(
                    smiles_hash=conformer["smiles_hash"],
                    target_pdb_id=target.pdb_id,
                    target_chain=target.chain,
                    target_center=box_center,
                    target_size=box_size,
                    hotspots=active_hotspots,
                )
                
                # Unir advertencias si existen
                if scientific_warnings:
                    docking.scientific_warnings.extend(scientific_warnings)

            await cache.set_job_progress(task_id, 80, "scoring")
            
            # --- [NUEVO PASO] ML Rescoring Correction + GNN (Nivel 2) ---
            # Paso 1: XGBoost rescoring corrige la afinidad de Vina.
            # Paso 2: RTMScore GNN evalúa la geometría continua de la pose.
            gnn_score_value: float | None = None
            shap_values_dict: dict | None = None
            gnn_attention_list: list | None = None
            gnn_attention_svg_data: str | None = None
            gnn_pharmacophores_dict: dict | None = None
            try:
                ml_result = await get_ml_rescore(
                    smiles=smiles,
                    target_pdb_path=f"/data/targets/{target.pdb_id}.pdb",
                    poses=[p.model_dump() for p in docking.poses],
                    properties=properties,
                    grid_center=list(box_center),
                    grid_size=list(box_size),
                    run_gnn=True,  # [FIX] Activa RTMScore GNN (Nivel 2)
                )

                if not ml_result.get("fallback"):
                    # --- XGBoost: corregir afinidad ---
                    pki_a = ml_result.get("score_a", 0.0)
                    if pki_a > 0:
                        corrected_kcal = -1.36 * pki_a
                        log.info({
                            "event": "ml_rescoring_applied",
                            "vina_kcal": docking.best_affinity,
                            "ml_pki": pki_a,
                            "ml_kcal_equivalent": corrected_kcal
                        })
                        docking.best_affinity = corrected_kcal

                    # --- GNN: capturar score geométrico ---
                    raw_gnn = ml_result.get("gnn_score")
                    if raw_gnn is not None:
                        gnn_score_value = float(raw_gnn)
                        log.info({
                            "event": "gnn_score_captured",
                            "gnn_score": gnn_score_value,
                        })

                    # --- XAI: capturar explicabilidad ---
                    shap_values_dict = ml_result.get("shap_values")
                    gnn_attention_list = ml_result.get("gnn_attention")
                    gnn_attention_svg_data = ml_result.get("gnn_attention_svg")
                    gnn_pharmacophores_dict = ml_result.get("gnn_pharmacophores")

                    # Warnings científicos del microservicio
                    if ml_result.get("warnings"):
                        docking.scientific_warnings.extend(ml_result["warnings"])

            except Exception as ml_err:
                log.warning({"event": "ml_rescoring_skipped", "error": str(ml_err)})

            # Leer specificity_floor del target (default 0.5 si no existe en DB)
            target_specificity_floor = getattr(target, "specificity_floor", None) or 0.5

            breakdown = calculate_score_breakdown(
                docking,
                properties,
                is_control=is_control,
                target_hotspots=active_hotspots,
                affinity_threshold=target.affinity_threshold if target.affinity_threshold is not None else -7.5,
                specificity_floor=target_specificity_floor,
                gnn_score=gnn_score_value,
            )

            # --- [NUEVO] Programar limpieza automática si el score es bajo (Umbral ajustado a 50 para conservación) ---
            if breakdown.total_score < 50.0:
                log.info({"event": "scheduling_cleanup_low_score", "molecule_id": str(molecule.id), "score": breakdown.total_score})
                cleanup_unsaved_molecule.apply_async(args=[str(molecule.id)], countdown=3600) # 1 hora
            # --- [NUEVO] Auditoría Científica Profunda ---
            deep_warnings = audit_scientific_quality(
                affinity_kcal=docking.best_affinity,
                heavy_atom_count=properties.heavy_atom_count,
                log_p=properties.log_p,
                docking_poses=[p.model_dump() for p in docking.poses],
                hotspots=active_hotspots,
                hotspots_hit=docking.hotspots_hit
            )
            # Combinamos advertencias técnicas con las científicas de valor añadido
            docking.scientific_warnings.extend(deep_warnings)

            await repository.upsert_evaluation_result(
                molecule_id=molecule.id,
                properties=properties,
                docking=docking,
                scores={
                    **breakdown.model_dump(),
                    "gnn_score": gnn_score_value,  # persistir en DB
                    "shap_values": shap_values_dict,
                    "gnn_attention": gnn_attention_list,
                    "gnn_attention_svg": gnn_attention_svg_data,
                    "gnn_pharmacophores": gnn_pharmacophores_dict,
                },
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

        except (Exception, SoftTimeLimitExceeded) as exc:
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
            # 2. El score final es inferior al umbral de "prometedora" (50.0)
            should_delete = False
            if mol.status == MoleculeStatus.FAILED:
                should_delete = True
                log.info({"event": "cleanup_reason_failed", "molecule_id": molecule_id})
            elif mol.evaluation_result and mol.evaluation_result.total_score is not None:
                if mol.evaluation_result.total_score < 50.0:
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


@celery_app.task(
    name="moldesign.run_full_evaluation", 
    bind=True,
    time_limit=600,        # Hard kill at 10 minutes
    soft_time_limit=570    # Raise SoftTimeLimitExceeded at 9.5 mins to fail gracefully
)
def run_full_evaluation(
    self,
    smiles: str,
    target_pdb_id: str,
    molecule_name: str | None = None,
    is_control: bool = False,
    user_id: str | None = None,
    grid_center: tuple[float, float, float] | None = None,
    grid_size: tuple[float, float, float] | None = None,
    custom_hotspots: list[str] | None = None,
    peptide_docking_engine: str | None = "diffpepdock",
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
        grid_center=grid_center,
        grid_size=grid_size,
        custom_hotspots=custom_hotspots,
        peptide_docking_engine=peptide_docking_engine,
    ))


def submit_evaluation_job(
    smiles: str,
    target_pdb_id: str,
    molecule_name: str | None = None,
    is_control: bool = False,
    user_id: str | None = None,
    grid_center: tuple[float, float, float] | None = None,
    grid_size: tuple[float, float, float] | None = None,
    custom_hotspots: list[str] | None = None,
    peptide_docking_engine: str | None = "diffpepdock",
):
    return run_full_evaluation.delay(
        smiles=smiles,
        target_pdb_id=target_pdb_id,
        molecule_name=molecule_name,
        is_control=is_control,
        user_id=user_id,
        grid_center=grid_center,
        grid_size=grid_size,
        custom_hotspots=custom_hotspots,
        peptide_docking_engine=peptide_docking_engine,
    )


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
                        result_payload.target_name = evaluation.molecule.target.name
                        result_payload.target_spearman_rho = evaluation.molecule.target.spearman_rho
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
