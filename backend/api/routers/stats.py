from fastapi import APIRouter, Depends
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from core.database import get_db
from core.models import MoleculeORM, EvaluationResultORM

router = APIRouter(prefix="/stats", tags=["Estadísticas"])

@router.get("/global")
async def get_global_stats(db: AsyncSession = Depends(get_db)):
    """
    Obtiene estadísticas globales de la plataforma en tiempo real.
    """
    # 1. Total de moléculas evaluadas
    total_mols_stmt = select(func.count(MoleculeORM.id))
    total_mols_res = await db.execute(total_mols_stmt)
    total_mols = total_mols_res.scalar() or 0

    # 2. Total de certificaciones (moléculas con TX ID)
    cert_stmt = select(func.count(EvaluationResultORM.id)).where(EvaluationResultORM.blockchain_tx_id.isnot(None))
    cert_res = await db.execute(cert_stmt)
    total_certs = cert_res.scalar() or 0

    # 3. Mejor afinidad encontrada (valor más bajo)
    best_aff_stmt = select(func.min(EvaluationResultORM.affinity_kcal))
    best_aff_res = await db.execute(best_aff_stmt)
    best_affinity = best_aff_res.scalar()

    return {
        "total_molecules": total_mols,
        "total_certifications": total_certs,
        "best_affinity": round(best_affinity, 2) if best_affinity is not None else None,
        "community_status": "Global"
    }
