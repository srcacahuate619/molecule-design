"""
Endpoints del flujo de evaluación del MVP.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from chem.validator import validate_smiles_or_raise
from core.database import get_db
from core.models import EvaluationResultRead, JobStatus
from db.repository import Repository
from utils.logger import bind_context, get_logger

log = get_logger(__name__)

router = APIRouter(prefix="/evaluation", tags=["Evaluación científica"])


class EvaluationSubmitRequest(BaseModel):
    smiles: str = Field(..., min_length=1, max_length=2000)
    target_pdb_id: str = Field(default="7E2Y", min_length=4, max_length=10)
    molecule_name: str | None = Field(default=None, max_length=200)


class EvaluationSubmitResponse(BaseModel):
    task_id: str
    status: str
    target_pdb_id: str
    smiles_hash: str


@router.post(
    "/submit",
    response_model=EvaluationSubmitResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Enviar evaluación molecular asíncrona",
)
async def submit_evaluation(request: EvaluationSubmitRequest) -> EvaluationSubmitResponse:
    validation = validate_smiles_or_raise(request.smiles)
    bind_context(endpoint="evaluation_submit", smiles_hash=validation.smiles_hash)

    try:
        from services.docking.queue_handler import submit_evaluation_job

        task = submit_evaluation_job(
            smiles=request.smiles,
            target_pdb_id=request.target_pdb_id,
            molecule_name=request.molecule_name,
        )
    except Exception as exc:
        log.error(
            "no se pudo enviar job de evaluación",
            error=str(exc),
            error_type=type(exc).__name__,
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="El servicio de evaluación no está disponible en este momento. "
                   "Verifica que el worker de Celery y Redis estén corriendo.",
        ) from exc

    log.info("job de evaluación enviado", task_id=task.id, target=request.target_pdb_id)
    return EvaluationSubmitResponse(
        task_id=task.id,
        status="submitted",
        target_pdb_id=request.target_pdb_id,
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

    # Patch: inject poseData (raw SDF string) into result if available
    if status_obj and status_obj.result and getattr(status_obj.result, 'poses_file_path', None):
        try:
            from utils.file_handlers import download_text
            pose_data = await download_text(status_obj.result.poses_file_path)
        except Exception as e:
            pose_data = None
        # Convert to dict if needed
        result_dict = status_obj.result.model_dump() if hasattr(status_obj.result, 'model_dump') else dict(status_obj.result)
        result_dict['poseData'] = pose_data
        # Patch status_obj.result to be this dict
        status_obj.result = result_dict
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
    return EvaluationResultRead.model_validate(result)


@router.get(
    "/files/poses/{molecule_id}",
    response_class=PlainTextResponse,
    summary="Descargar SDF de poses de docking",
)
async def get_pose_file(
    molecule_id: uuid.UUID,
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

    # Convierte el PDBQT de salida a SDF usando RDKit antes de enviarlo al frontend
    pdbqt_path = result.poses_file_path.replace('.sdf', '.pdbqt') if result.poses_file_path else None
    if not pdbqt_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Esta evaluación no tiene archivo de poses (puede ser un resultado fallido o pendiente)",
        )
    try:
        pdbqt_content = await download_text(pdbqt_path)
    except FileNotFoundInStorage:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="El archivo de poses PDBQT no se encontró en storage",
        )
    # Validación mínima: debe contener ATOM/HETATM
    if not pdbqt_content or not any(l.startswith(('ATOM', 'HETATM')) for l in pdbqt_content.splitlines()):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="El archivo PDBQT de la pose está vacío o no contiene átomos.",
        )
    # Convertir a SDF usando RDKit, pero nunca generar nuevos conformers para docking output
    from rdkit import Chem
    import io
    mol = Chem.MolFromPDBBlock(pdbqt_content, sanitize=True, removeHs=False)
    if mol is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="No se pudo parsear el PDBQT a un mol RDKit válido.",
        )
    # Validar que el mol tenga conformer 3D (coordenadas)
    if mol.GetNumConformers() == 0:
        warning = "El SDF generado desde el PDBQT de docking NO contiene conformer 3D. Las coordenadas pueden estar perdidas."
        print(warning)
        # No generamos conformer, solo advertimos
    buffer = io.StringIO()
    writer = Chem.SDWriter(buffer)
    writer.write(mol)
    writer.close()
    sdf_content = buffer.getvalue()
    return PlainTextResponse(
        content=sdf_content,
        media_type="chemical/x-mdl-sdfile",
        headers={"Content-Disposition": f'inline; filename="poses_{molecule_id}.sdf"'},
    )


@router.get(
    "/files/protein/{molecule_id}",
    response_class=PlainTextResponse,
    summary="Descargar PDB del target biológico",
)
async def get_protein_file(
    molecule_id: uuid.UUID,
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