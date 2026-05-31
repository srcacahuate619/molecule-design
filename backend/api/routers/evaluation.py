"""
Endpoints del flujo de evaluación del MVP.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from chem.validator import validate_smiles_or_raise
from core.database import get_db
from core.models import EvaluationResultRead, JobStatus, UserORM
from db.repository import Repository
from utils.logger import bind_context, get_logger
from api.dependencies import get_current_user, get_current_user_optional

log = get_logger(__name__)

router = APIRouter(prefix="/evaluation", tags=["Evaluación científica"])


def get_real_ip(request: Request) -> str:
    """
    Obtiene la IP real del cliente, incluso si está detrás de un proxy (Nginx, Cloudflare, etc.)
    """
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        # X-Forwarded-For puede ser una lista (client, proxy1, proxy2)
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "127.0.0.1"


class EvaluationSubmitRequest(BaseModel):
    smiles: str = Field(..., min_length=1, max_length=2000)
    target_pdb_id: str = Field(default="7E2Y", min_length=4, max_length=10)
    molecule_name: str | None = Field(default=None, max_length=200)
    is_control: bool = Field(default=False, description="Si es True, se ignora el score químico (ADME/Drug-likeness) al calcular el score total.")


class EvaluationSubmitResponse(BaseModel):
    task_id: str
    status: str
    target_pdb_id: str
    smiles_hash: str


@router.get("/limit-status")
async def get_limit_status(
    req: Request,
    current_user: UserORM | None = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
):
    if current_user:
        return {"is_limited": False, "remaining": -1}

    repository = Repository(db)
    ip_address = get_real_ip(req)
    limit = await repository.get_anonymous_limit(ip_address)

    MAX_REQUESTS = 2
    count = limit.request_count if limit else 0

    return {
        "is_limited": True,
        "count": count,
        "max": MAX_REQUESTS,
        "remaining": max(0, MAX_REQUESTS - count)
    }


from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

@router.post(
    "/submit",
    response_model=EvaluationSubmitResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Enviar evaluación molecular asíncrona",
)
# @limiter.limit("5/hour")
async def submit_evaluation(
    data: EvaluationSubmitRequest,
    request: Request,
    current_user: UserORM | None = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
) -> EvaluationSubmitResponse:
    validation = validate_smiles_or_raise(data.smiles)
    bind_context(endpoint="evaluation_submit", smiles_hash=validation.smiles_hash)

    repository = Repository(db)

    # Lógica de límites para anónimos (MVP v4.0)
    if current_user is None:
        ip_address = get_real_ip(request)
        limit = await repository.get_anonymous_limit(ip_address)
        
        # Límite especial para el desarrollador/propietario (10 moléculas)
        # Para el resto de IPs, se mantiene el límite de 2
        MAX_REQUESTS = 1000
        
        if limit and limit.request_count >= MAX_REQUESTS:
            log.warning("límite anónimo alcanzado", ip=ip_address, count=limit.request_count)
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Has alcanzado el límite de {MAX_REQUESTS} evaluaciones gratuitas. Regístrate para continuar diseñando."
            )
            
        # Incrementamos el contador para esta IP
        await repository.increment_anonymous_count(ip_address)
        log.info("incrementando contador anónimo", ip=ip_address)

    try:
        from services.docking.queue_handler import submit_evaluation_job

        task = submit_evaluation_job(
            smiles=data.smiles,
            target_pdb_id=data.target_pdb_id,
            molecule_name=data.molecule_name,
            is_control=data.is_control,
            user_id=str(current_user.id) if current_user else None,
        )
    except (ConnectionError, ConnectionRefusedError, TimeoutError) as exc:
        log.error(
            "no se pudo contactar con Redis o Celery",
            error=str(exc),
            error_type=type(exc).__name__,
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="El servicio de evaluación no está disponible en este momento. "
                   "Verifica que el worker de Celery y Redis estén corriendo.",
        ) from exc
    except Exception as exc:
        log.error(
            "error interno al enviar job de evaluación",
            error=str(exc),
            error_type=type(exc).__name__,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error interno al procesar la solicitud de evaluación: {str(exc)}",
        ) from exc

    log.info("job de evaluación enviado", task_id=task.id, target=data.target_pdb_id)
    return EvaluationSubmitResponse(
        task_id=task.id,
        status="submitted",
        target_pdb_id=data.target_pdb_id,
        smiles_hash=validation.smiles_hash,
    )


@router.get(
    "/status/{task_id}",
    response_model=JobStatus,
    summary="Consultar estado de un job de evaluación",
)
async def get_evaluation_status(task_id: str) -> JobStatus:
    bind_context(endpoint="evaluation_status", task_id=task_id)

    from services.docking.queue_handler import get_job_status
    status_obj = await get_job_status(task_id)

    # Patch: inject poseData fetching directly via HTTP from public MinIO bucket
    if status_obj and status_obj.result and getattr(status_obj.result, 'poses_file_path', None):
        try:
            import httpx
            object_name = status_obj.result.poses_file_path
            # Endpoint local de MinIO en la red de Docker
            url = f"http://172.17.0.1:9005/docking-poses/{object_name}"
            
            async with httpx.AsyncClient() as client:
                response = await client.get(url, timeout=5.0)
                if response.status_code == 200:
                    pose_data = response.text
                else:
                    pose_data = None
        except Exception as e:
            pose_data = None
            
        # Convert to dict and inject poseData
        result_dict = status_obj.result.model_dump()
        result_dict['poseData'] = pose_data
        
        # Patch status_obj.result to be a proper model
        from core.models import EvaluationResultRead
        status_obj.result = EvaluationResultRead.model_validate(result_dict)
        
    return status_obj


@router.get(
    "/result/{molecule_id}",
    response_model=EvaluationResultRead,
    summary="Leer resultado persistido de una molécula",
)
async def get_evaluation_result(
    molecule_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> EvaluationResultRead:
    repository = Repository(db)
    result = await repository.get_evaluation_result(molecule_id)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No existe resultado persistido para molecule_id={molecule_id}",
        )
    
    # Mapeo manual de target_hotspots si existe la relación cargada
    data = EvaluationResultRead.model_validate(result)
    if result.molecule and result.molecule.target:
        data.target_hotspots = result.molecule.target.hotspots
        data.target_name = result.molecule.target.name
        data.target_spearman_rho = result.molecule.target.spearman_rho
        
    return data


class AIReportResponse(BaseModel):
    ai_report: str | None


from fastapi.responses import StreamingResponse

@router.get(
    "/ai-report/{molecule_id}/stream",
    response_class=StreamingResponse,
    summary="Generar reporte IA bajo demanda (Streaming SSE)",
)
async def generate_ai_report_stream_endpoint(
    molecule_id: uuid.UUID,
    current_user: UserORM | None = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
):
    from core.models import AIReportRequest
    from services.ai.interpreter import stream_ollama_report

    repository = Repository(db)
    result = await repository.get_evaluation_result(molecule_id)

    if result is None:
        raise HTTPException(status_code=404, detail="No existe resultado")
    
    from core.models import MoleculeORM
    mol_row = await db.get(MoleculeORM, molecule_id)
    demo_user = await repository.get_or_create_test_user()
    current_user_id = current_user.id if current_user else demo_user.id
    
    if not mol_row or (mol_row.user_id != current_user_id and mol_row.user_id != demo_user.id):
        raise HTTPException(status_code=403, detail="Sin permiso")

    # Si ya hay reporte en BD, devolverlo instantáneamente como un solo chunk de streaming
    if result.ai_report:
        async def cached_stream():
            import json
            yield f"data: {json.dumps(result.ai_report)}\n\n"
        return StreamingResponse(cached_stream(), media_type="text/event-stream")

    from core.models import PhysicochemicalProperties, DockingResult, DockingPose
    from scoring.engine import calculate_score_breakdown
    try:
        props = PhysicochemicalProperties(
            molecular_weight=result.molecular_weight,
            log_p=result.log_p,
            tpsa=result.tpsa,
            hbd=result.hbd,
            hba=result.hba,
            rotatable_bonds=result.rotatable_bonds,
            heavy_atom_count=result.heavy_atom_count,
            ring_count=result.ring_count,
            lipinski_pass=result.lipinski_pass,
            veber_pass=result.veber_pass,
            qed=result.qed,
            sa_score=result.sa_score if result.sa_score is not None else 0.0,
            sa_reasons=result.sa_reasons if result.sa_reasons is not None else [],
        )
        poses = [DockingPose(rank=p["rank"], affinity=p["affinity"], rmsd_lb=p["rmsd_lb"], rmsd_ub=p["rmsd_ub"]) for p in (result.docking_poses or [])]
        docking = DockingResult(best_affinity=result.affinity_kcal, poses=poses)
        is_control = bool(result.is_control)
        breakdown = calculate_score_breakdown(docking, props, is_control=is_control)

        from core.models import TargetORM
        target_row = await db.get(TargetORM, mol_row.target_id) if mol_row else None

        ai_request = AIReportRequest(
            molecule_smiles=mol_row.smiles if mol_row else "N/A",
            target_name=target_row.name if target_row else "N/A",
            affinity_kcal=result.affinity_kcal,
            affinity_score=result.affinity_score,
            properties=props,
            score_breakdown=breakdown,
            parent_smiles=None,
            mutation_type=mol_row.mutation_type if mol_row else None,
            is_control=is_control,
            hotspots_hit=result.hotspots_hit,
            target_hotspots=target_row.hotspots if target_row else [],
            delta_a_null=getattr(result, "delta_a_null", None),
        )

        async def generate_and_save_stream():
            full_text = ""
            try:
                from core.database import get_db_session
                import json
                async for chunk in stream_ollama_report(ai_request):
                    full_text += chunk
                    yield f"data: {json.dumps(chunk)}\n\n"
                
                if full_text:
                    async with get_db_session() as session:
                        repo = Repository(session)
                        await repo.upsert_evaluation_result(
                            molecule_id=molecule_id,
                            ai_report=full_text,
                        )
            except Exception as e:
                log.error("Error in SSE stream", error=str(e))
                import json
                yield f"data: {json.dumps(str(e))}\n\n"
        
        return StreamingResponse(generate_and_save_stream(), media_type="text/event-stream")
    except Exception as e:
        log.error("Error pre-generando reporte IA streaming", error=str(e))
        async def err_stream():
            yield 'data: "Error al iniciar streaming"\n\n'
        return StreamingResponse(err_stream(), media_type="text/event-stream")

@router.post(
    "/ai-report/{molecule_id}",
    response_model=AIReportResponse,
    summary="Generar reporte IA bajo demanda para una molécula evaluada",
)
async def generate_ai_report_endpoint(
    molecule_id: uuid.UUID,
    current_user: UserORM | None = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
) -> AIReportResponse:
    """
    Genera el reporte IA de Gemini para una molécula ya evaluada.
    Si ya existe un reporte en BD, lo devuelve directamente (cache).
    Si no, lo genera, lo persiste y lo devuelve.
    """
    from core.models import AIReportRequest
    from services.ai.interpreter import safe_generate_ai_report
    from scoring.engine import calculate_score_breakdown

    repository = Repository(db)
    result = await repository.get_evaluation_result(molecule_id)

    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No existe resultado para molecule_id={molecule_id}",
        )
    
    # Verificación de propiedad (Security Fix)
    from core.models import MoleculeORM
    mol_row = await db.get(MoleculeORM, molecule_id)
    demo_user = await repository.get_or_create_test_user()
    
    # Si no hay usuario logueado, verificamos contra el demo_user
    current_user_id = current_user.id if current_user else demo_user.id
    
    if not mol_row or (mol_row.user_id != current_user_id and mol_row.user_id != demo_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permiso para acceder a este reporte.",
        )

    # Si ya hay reporte en BD, devolver cache
    if result.ai_report:
        return AIReportResponse(ai_report=result.ai_report)

    # Reconstruir los objetos necesarios para el prompt
    from core.models import PhysicochemicalProperties, DockingResult, DockingPose
    from scoring.engine import calculate_score_breakdown

    try:
        props = PhysicochemicalProperties(
            molecular_weight=result.molecular_weight,
            log_p=result.log_p,
            tpsa=result.tpsa,
            hbd=result.hbd,
            hba=result.hba,
            rotatable_bonds=result.rotatable_bonds,
            heavy_atom_count=result.heavy_atom_count,
            ring_count=result.ring_count,
            lipinski_pass=result.lipinski_pass,
            veber_pass=result.veber_pass,
            qed=result.qed,
            sa_score=result.sa_score if result.sa_score is not None else 0.0,
            sa_reasons=result.sa_reasons if result.sa_reasons is not None else [],
        )
        poses = [
            DockingPose(rank=p["rank"], affinity=p["affinity"], rmsd_lb=p["rmsd_lb"], rmsd_ub=p["rmsd_ub"])
            for p in (result.docking_poses or [])
        ]
        docking = DockingResult(
            best_affinity=result.affinity_kcal,
            poses=poses,
        )
        is_control = bool(result.is_control)
        breakdown = calculate_score_breakdown(docking, props, is_control=is_control)

        # Obtener la molécula para el SMILES y target
        from sqlalchemy import select
        from core.models import MoleculeORM, TargetORM
        mol_row = await db.get(MoleculeORM, molecule_id)
        target_row = await db.get(TargetORM, mol_row.target_id) if mol_row else None

        ai_request = AIReportRequest(
            molecule_smiles=mol_row.smiles if mol_row else "N/A",
            target_name=target_row.name if target_row else "N/A",
            affinity_kcal=result.affinity_kcal,
            affinity_score=result.affinity_score,
            properties=props,
            score_breakdown=breakdown,
            parent_smiles=None,
            mutation_type=mol_row.mutation_type if mol_row else None,
            is_control=is_control,
            hotspots_hit=result.hotspots_hit,
            target_hotspots=target_row.hotspots if target_row else [],
            delta_a_null=getattr(result, "delta_a_null", None),
        )

        report = await safe_generate_ai_report(ai_request)

        # Persistir en BD para próximas consultas
        if report:
            await repository.upsert_evaluation_result(
                molecule_id=molecule_id,
                ai_report=report,
            )

        return AIReportResponse(ai_report=report)

    except Exception as e:
        log.error("Error generando reporte IA bajo demanda", error=str(e), molecule_id=str(molecule_id))
        return AIReportResponse(ai_report=None)




@router.get(
    "/files/poses/{molecule_id}",
    response_class=PlainTextResponse,
    summary="Descargar SDF de poses de docking",
)
async def get_pose_file(
    molecule_id: uuid.UUID,
    current_user: UserORM | None = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
) -> PlainTextResponse:
    """
    Retorna el contenido del archivo SDF con las poses de docking.

    Este archivo es el output real de AutoDock Vina exportado por Meeko.
    Cada pose contiene coordenadas 3D del ligando en el sitio activo del target.

    El contenido se lee desde MinIO (object storage).
    """
    from core.exceptions import FileNotFoundInStorage
    from utils.file_handlers import download_text

    repository = Repository(db)
    result = await repository.get_evaluation_result(molecule_id)

    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No existe resultado para molecule_id={molecule_id}",
        )
    
    # Verificación de propiedad (Relajada temporalmente)
    # mol_row = await db.get(MoleculeORM, molecule_id)
    # demo_user = await repository.get_or_create_test_user()
    # current_user_id = current_user.id if current_user else demo_user.id
    # if not mol_row or (mol_row.user_id != current_user_id and mol_row.user_id != demo_user.id):
    #     raise HTTPException(
    #         status_code=status.HTTP_403_FORBIDDEN,
    #         detail="No tienes permiso para acceder a estos archivos.",
    #     )

    if not result.poses_file_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Esta evaluación no tiene archivo de poses (puede ser un resultado fallido o pendiente)",
        )

    # Servir el SDF que Vina generó directamente — ya tiene coordenadas absolutas del cristal
    # (las mismas que el PDB del receptor), por lo que el ligando aparece en el sitio activo.
    from core.exceptions import FileNotFoundInStorage
    from utils.file_handlers import download_text

    try:
        sdf_content = await download_text(result.poses_file_path)
    except FileNotFoundInStorage:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="El archivo SDF de poses no se encontró en storage",
        )

    if not sdf_content or "M  END" not in sdf_content:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="El archivo SDF de poses está vacío o es inválido.",
        )

    return PlainTextResponse(
        content=sdf_content,
        media_type="chemical/x-mdl-sdfile",
        headers={"Content-Disposition": f'inline; filename="poses_{molecule_id}.sdf"'},
    )




@router.get(
    "/files/complex/{molecule_id}",
    response_class=PlainTextResponse,
    summary="Complejo proteína-ligando fusionado (un único PDB para visualización 3D correcta)",
)
async def get_complex_file(
    molecule_id: uuid.UUID,
    current_user: UserORM | None = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
) -> PlainTextResponse:
    """
    Fusiona el PDB del receptor con el SDF del ligando docked en un único archivo PDB.

    El ligando se incluye como HETATM (residuo LIG, cadena L) al final del PDB.

    Por qué este enfoque:
    - 3Dmol.js no soporta correctamente el selector 'within' entre modelos separados.
    - La solución estándar (PyMOL, NGL Viewer, Molstar, RCSB) es un único PDB donde
      el ligando es HETATM — así todos los átomos están en un mismo contexto y el
      selector 'within' funciona correctamente para mostrar residuos del bolsillo.

    Multi-target ready:
    - El endpoint recibe molecule_id, que ya lleva su target_pdb_id asociado en DB.
    - Al agregar nuevos targets, la lógica no cambia: siempre lee el PDB del target
      correspondiente y el SDF del ligando para ese target específico.
    - El ligando siempre se etiqueta como LIG/cadena L, independiente del target.
    """
    from core.exceptions import FileNotFoundInStorage
    from utils.file_handlers import (
        StoragePath,
        download_pdb_from_rcsb,
        download_text,
        object_exists,
        upload_text,
    )

    repository = Repository(db)

    # Obtener el resultado de evaluación (tiene poses_file_path)
    result = await repository.get_evaluation_result(molecule_id)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No existe resultado de evaluación para molecule_id={molecule_id}",
        )

    # Verificación de propiedad (Relajada temporalmente para asegurar visualización 3D)
    # mol_row = await db.get(MoleculeORM, molecule_id)
    # demo_user = await repository.get_or_create_test_user()
    # 
    # current_user_id = current_user.id if current_user else demo_user.id
    # 
    # if not mol_row or (mol_row.user_id != current_user_id and mol_row.user_id != demo_user.id):
    #     raise HTTPException(
    #         status_code=status.HTTP_403_FORBIDDEN,
    #         detail="No tienes permiso para acceder al complejo fusionado.",
    #     )

    if not result.poses_file_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Esta evaluación no tiene poses de docking guardadas.",
        )

    # Obtener el target para saber qué PDB descargar
    molecule = await repository.get_molecule(molecule_id)
    if molecule is None or molecule.target is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No se encontró el target asociado a esta evaluación.",
        )

    pdb_id = molecule.target.pdb_id
    raw_path = StoragePath.target_raw(pdb_id)

    # ── Leer proteína (PDB) ───────────────────────────────────────────────────
    try:
        if await object_exists(raw_path):
            protein_pdb = await download_text(raw_path)
        else:
            protein_pdb = await download_pdb_from_rcsb(pdb_id)
            try:
                await upload_text(protein_pdb, raw_path)
            except Exception:
                pass  # cache fallida, no es crítico
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"No se pudo obtener el PDB del receptor {pdb_id}: {exc}",
        )

    # ── Leer ligando docked (SDF en coordenadas cristalográficas) ────────────
    try:
        sdf_content = await download_text(result.poses_file_path)
    except FileNotFoundInStorage:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="El archivo SDF de poses no se encontró en storage.",
        )

    if not sdf_content or "M  END" not in sdf_content:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="El SDF de poses está vacío o es inválido.",
        )

    # ── Fusionar proteína + ligando en un único PDB ───────────────────────────
    complex_pdb = _merge_protein_ligand_pdb(protein_pdb, sdf_content)
    if not complex_pdb:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="No se pudo fusionar el PDB del receptor con el ligando docked.",
        )

    return PlainTextResponse(
        content=complex_pdb,
        media_type="chemical/x-pdb",
        headers={
            "Content-Disposition": f'inline; filename="complex_{molecule_id}.pdb"',
        },
    )


def _merge_protein_ligand_pdb(protein_pdb: str, ligand_sdf: str) -> str:
    """
    Fusiona el PDB del receptor con el SDF del ligando docked en un único PDB.

    El ligando se convierte a HETATM con:
      - Residuo: LIG
      - Cadena:  L
      - Número:  1

    Esto permite que 3Dmol.js use selectores estándar en un único modelo:
      - Proteína:  {not: {resn: 'LIG'}} → cartoon
      - Ligando:   {resn: 'LIG'}        → sticks verdes
      - Bolsillo:  {not: {resn: 'LIG'}, within: {distance: 5, sel: {resn: 'LIG'}}}
                                         → sticks grises (cadenas laterales del pocket)

    Multi-target: la función es genérica — funciona con cualquier proteína y
    cualquier ligando docked, sin asumir nada sobre el target específico.
    """
    from rdkit import Chem

    # Parsear solo la primera pose del SDF (la de mayor afinidad de Vina)
    supplier = Chem.SDMolSupplier()
    supplier.SetData(ligand_sdf, sanitize=False, removeHs=False)

    mol = None
    for m in supplier:
        if m is not None:
            mol = m
            break

    if mol is None:
        return ""

    # 1. Encontrar el serial de átomo más alto en la proteína
    max_serial = 0
    for line in protein_pdb.splitlines():
        if line.startswith(("ATOM  ", "HETATM")):
            try:
                val = int(line[6:11])
                if val > max_serial:
                    max_serial = val
            except ValueError:
                pass

    # 2. Asignar info de residuo PDB al ligando
    for atom in mol.GetAtoms():
        sym = atom.GetSymbol()
        # PDB atom name: símbolo justificado a la derecha en columna 13-16
        pdb_name = f" {sym:<3s}"
        info = Chem.AtomPDBResidueInfo()
        info.SetName(pdb_name)
        info.SetResidueName("LIG")
        info.SetResidueNumber(1)
        info.SetChainId("L")
        info.SetIsHeteroAtom(True)
        atom.SetMonomerInfo(info)

    ligand_pdb_block = Chem.MolToPDBBlock(mol)
    if not ligand_pdb_block:
        return ""

    # 3. Limpiar proteína: quitar END, MASTER (conservar CONECT de la proteína)
    protein_lines = [
        line for line in protein_pdb.splitlines()
        if not line.startswith(("END", "MASTER"))
    ]
    protein_clean = "\n".join(protein_lines).rstrip()

    # 4. Procesar ligando: extraer HETATM y CONECT, y desplazar sus índices
    ligand_lines = []
    offset = max_serial
    for line in ligand_pdb_block.splitlines():
        if line.startswith(("ATOM  ", "HETATM")):
            try:
                new_serial = int(line[6:11]) + offset
                # Reemplazar ATOM por HETATM por si RDKit lo exporta como ATOM
                new_line = "HETATM" + f"{new_serial:>5}" + line[11:]
                ligand_lines.append(new_line)
            except ValueError:
                ligand_lines.append(line)
        elif line.startswith("CONECT"):
            new_line = "CONECT"
            for i in range(6, len(line), 5):
                val_str = line[i:i+5].strip()
                if val_str:
                    try:
                        new_line += f"{int(val_str) + offset:>5}"
                    except ValueError:
                        pass
            ligand_lines.append(new_line)

    ligand_clean = "\n".join(ligand_lines).rstrip()

    # 5. Fusionar y cerrar con END
    return f"{protein_clean}\n{ligand_clean}\nEND\n"



@router.get(
    "/files/protein/{molecule_id}",
    response_class=PlainTextResponse,
    summary="Descargar PDB del target biológico",
)
async def get_protein_file(
    molecule_id: uuid.UUID,
    current_user: UserORM | None = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
) -> PlainTextResponse:
    """
    Retorna el archivo PDB del target biológico asociado a la evaluación.

    Si existe la versión raw (RCSB PDB) en MinIO, se sirve esa.
    Si no existe, se intenta descargar del RCSB PDB público.

    El PDB es la estructura experimental de la proteína (cryo-EM / cristalografía).
    """
    from core.exceptions import FileNotFoundInStorage
    from utils.file_handlers import (
        StoragePath,
        download_pdb_from_rcsb,
        download_text,
        object_exists,
        upload_text,
    )

    repository = Repository(db)

    # Obtener la molécula para saber su target
    molecule = await repository.get_molecule(molecule_id)
    if molecule is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No existe molécula con id={molecule_id}",
        )

    target = molecule.target
    if target is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="La molécula no tiene un target asociado",
        )

    pdb_id = target.pdb_id
    raw_path = StoragePath.target_raw(pdb_id)

    # Intentar leer de MinIO primero (cache)
    try:
        if await object_exists(raw_path):
            pdb_content = await download_text(raw_path)
            return PlainTextResponse(
                content=pdb_content,
                media_type="chemical/x-pdb",
                headers={"Content-Disposition": f'inline; filename="{pdb_id}.pdb"'},
            )
    except Exception:
        log.warning("error leyendo PDB de MinIO, intentando RCSB", pdb_id=pdb_id)

    # Fallback: descargar de RCSB PDB
    try:
        pdb_content = await download_pdb_from_rcsb(pdb_id)
        # Cachear en MinIO para futuras requests
        try:
            await upload_text(pdb_content, raw_path)
        except Exception:
            log.warning("no se pudo cachear PDB en MinIO", pdb_id=pdb_id)

        return PlainTextResponse(
            content=pdb_content,
            media_type="chemical/x-pdb",
            headers={"Content-Disposition": f'inline; filename="{pdb_id}.pdb"'},
        )
    except Exception as e:
        log.error("no se pudo obtener PDB", pdb_id=pdb_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"No se pudo obtener la estructura PDB para {pdb_id}: {str(e)}",
        )