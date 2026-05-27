"""
api/routers/history.py

Endpoints para consultar el historial de evaluaciones.

Permite a un usuario (autenticado u opcionalmente anónimo en dev)
ver sus evaluaciones pasadas con toda la trazabilidad científica.
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from api.dependencies import get_current_user, get_current_user_optional
from core.database import get_db
from core.models import (
    EvaluationResultORM,
    MoleculeORM,
    MoleculeStatus,
    TargetORM,
    UserORM,
)
from utils.logger import get_logger

log = get_logger(__name__)

router = APIRouter(prefix="/history", tags=["Historial de evaluaciones"])


# ── Response schemas ──────────────────────────────────────────────────────────

class EvaluationSummary(BaseModel):
    """Resumen de una evaluación para la lista de historial."""
    molecule_id: str
    smiles: str
    name: str | None
    status: str
    target_pdb_id: str
    total_score: float | None
    affinity_kcal: float | None
    affinity_score: float | None
    adme_score: float | None
    druglikeness_score: float | None
    molecular_weight: float | None
    log_p: float | None
    lipinski_pass: bool | None
    qed: float | None
    blockchain_tx_id: str | None
    evaluated_at: str | None
    created_at: str


class HistoryResponse(BaseModel):
    """Respuesta paginada del historial."""
    items: list[EvaluationSummary]
    total: int
    page: int
    page_size: int
    has_next: bool


class StatsResponse(BaseModel):
    """Estadísticas del usuario."""
    total_evaluations: int
    completed_evaluations: int
    failed_evaluations: int
    best_score: float | None
    avg_score: float | None
    unique_targets: int


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get(
    "/evaluations",
    response_model=HistoryResponse,
    summary="Listar evaluaciones del usuario",
)
async def list_evaluations(
    page: int = Query(default=1, ge=1, description="Página"),
    page_size: int = Query(default=20, ge=1, le=100, description="Elementos por página"),
    status_filter: MoleculeStatus | None = Query(
        default=None, alias="status", description="Filtrar por estado"
    ),
    sort_by: str = Query(
        default="created_at",
        description="Campo de orden: created_at, total_score, affinity_kcal",
    ),
    sort_order: str = Query(default="desc", description="asc o desc"),
    current_user: UserORM = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> HistoryResponse:
    """
    Devuelve el historial de evaluaciones del usuario autenticado.
    Soporta paginación, filtro por estado y ordenamiento.
    """
    # Base query
    base_query = (
        select(MoleculeORM)
        .options(
            selectinload(MoleculeORM.target),
            selectinload(MoleculeORM.evaluation_result),
        )
        .where(MoleculeORM.user_id == current_user.id)
        .where(MoleculeORM.is_saved == True)
    )

    if status_filter is not None:
        base_query = base_query.where(MoleculeORM.status == status_filter)

    # Count total
    count_query = select(func.count()).select_from(
        base_query.with_only_columns(MoleculeORM.id).subquery()
    )
    total = (await db.execute(count_query)).scalar() or 0

    # Sorting
    sort_column = MoleculeORM.created_at  # default
    if sort_by == "total_score":
        base_query = base_query.outerjoin(EvaluationResultORM)
        sort_column = EvaluationResultORM.total_score
    elif sort_by == "affinity_kcal":
        base_query = base_query.outerjoin(EvaluationResultORM)
        sort_column = EvaluationResultORM.affinity_kcal

    if sort_order == "asc":
        base_query = base_query.order_by(sort_column.asc().nullslast())
    else:
        base_query = base_query.order_by(sort_column.desc().nullslast())

    # Pagination
    offset = (page - 1) * page_size
    base_query = base_query.offset(offset).limit(page_size)

    result = await db.execute(base_query)
    molecules = list(result.scalars().all())

    items = []
    for mol in molecules:
        ev = mol.evaluation_result
        items.append(EvaluationSummary(
            molecule_id=str(mol.id),
            smiles=mol.smiles,
            name=mol.name,
            status=mol.status.value if hasattr(mol.status, "value") else str(mol.status),
            target_pdb_id=mol.target.pdb_id if mol.target else "unknown",
            total_score=ev.total_score if ev else None,
            affinity_kcal=ev.affinity_kcal if ev else None,
            affinity_score=ev.affinity_score if ev else None,
            adme_score=ev.adme_score if ev else None,
            druglikeness_score=ev.druglikeness_score if ev else None,
            molecular_weight=ev.molecular_weight if ev else None,
            log_p=ev.log_p if ev else None,
            lipinski_pass=ev.lipinski_pass if ev else None,
            qed=ev.qed if ev else None,
            blockchain_tx_id=ev.blockchain_tx_id if ev else None,
            evaluated_at=ev.evaluated_at.isoformat() if ev and ev.evaluated_at else None,
            created_at=mol.created_at.isoformat() if mol.created_at else "",
        ))

    return HistoryResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        has_next=(offset + page_size) < total,
    )


@router.get(
    "/stats",
    response_model=StatsResponse,
    summary="Estadísticas del usuario",
)
async def get_stats(
    current_user: UserORM = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> StatsResponse:
    """Devuelve estadísticas agregadas de las evaluaciones del usuario."""

    # Total molecules
    total_q = select(func.count()).where(
        MoleculeORM.user_id == current_user.id,
        MoleculeORM.is_saved == True
    )
    total = (await db.execute(total_q)).scalar() or 0

    # Completed
    completed_q = select(func.count()).where(
        MoleculeORM.user_id == current_user.id,
        MoleculeORM.status == MoleculeStatus.EVALUATED,
        MoleculeORM.is_saved == True
    )
    completed = (await db.execute(completed_q)).scalar() or 0

    # Failed
    failed_q = select(func.count()).where(
        MoleculeORM.user_id == current_user.id,
        MoleculeORM.status == MoleculeStatus.FAILED,
        MoleculeORM.is_saved == True
    )
    failed = (await db.execute(failed_q)).scalar() or 0

    # Best and avg score
    score_q = (
        select(
            func.max(EvaluationResultORM.total_score),
            func.avg(EvaluationResultORM.total_score),
        )
        .join(MoleculeORM, EvaluationResultORM.molecule_id == MoleculeORM.id)
        .where(MoleculeORM.user_id == current_user.id)
        .where(MoleculeORM.is_saved == True)
        .where(EvaluationResultORM.total_score.isnot(None))
    )
    score_result = (await db.execute(score_q)).one()
    best_score = float(score_result[0]) if score_result[0] is not None else None
    avg_score = round(float(score_result[1]), 2) if score_result[1] is not None else None

    # Unique targets
    targets_q = (
        select(func.count(func.distinct(MoleculeORM.target_id)))
        .where(MoleculeORM.user_id == current_user.id)
        .where(MoleculeORM.is_saved == True)
    )
    unique_targets = (await db.execute(targets_q)).scalar() or 0

    return StatsResponse(
        total_evaluations=total,
        completed_evaluations=completed,
        failed_evaluations=failed,
        best_score=best_score,
        avg_score=avg_score,
        unique_targets=unique_targets,
    )


@router.post(
    "/save/{molecule_id}",
    summary="Guardar molécula explícitamente en la cuenta",
)
async def save_molecule(
    molecule_id: uuid.UUID,
    name: str | None = Query(None, description="Nombre personalizado"),
    current_user: UserORM = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Marca una molécula como 'guardada' para que aparezca en el listado de Guardado."""
    mol = await db.get(MoleculeORM, molecule_id)
    if not mol or mol.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Molécula no encontrada")
    
    mol.is_saved = True
    if name:
        mol.name = name
    await db.commit()
    return {"status": "saved", "molecule_id": str(molecule_id), "name": mol.name}
