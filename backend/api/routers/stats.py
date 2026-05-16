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
    from core.models import UserORM
    
    # 1. Total de moléculas evaluadas (excluyendo demo)
    total_mols_stmt = (
        select(func.count(MoleculeORM.id))
        .join(UserORM, MoleculeORM.user_id == UserORM.id)
        .where(UserORM.username != 'demo')
    )
    total_mols_res = await db.execute(total_mols_stmt)
    total_mols = total_mols_res.scalar() or 0

    # 2. Total de certificaciones (moléculas con TX ID, excluyendo demo)
    cert_stmt = (
        select(func.count(EvaluationResultORM.id))
        .join(MoleculeORM, EvaluationResultORM.molecule_id == MoleculeORM.id)
        .join(UserORM, MoleculeORM.user_id == UserORM.id)
        .where(EvaluationResultORM.blockchain_tx_id.isnot(None))
        .where(UserORM.username != 'demo')
    )
    cert_res = await db.execute(cert_stmt)
    total_certs = cert_res.scalar() or 0

    # 3. Mejor puntuación encontrada y detalles de la molécula récord
    from core.models import UserORM
    
    from core.models import TargetORM
    
    # Intento 1: Buscar por score total (ML Rescoring)
    best_stmt = (
        select(EvaluationResultORM, MoleculeORM, UserORM, TargetORM)
        .join(MoleculeORM, EvaluationResultORM.molecule_id == MoleculeORM.id)
        .join(UserORM, MoleculeORM.user_id == UserORM.id)
        .join(TargetORM, MoleculeORM.target_id == TargetORM.id)
        .where(EvaluationResultORM.total_score.isnot(None))
        .where(UserORM.username != 'demo')
        .order_by(EvaluationResultORM.total_score.desc())
        .limit(1)
    )
    best_res = await db.execute(best_stmt)
    best_row = best_res.first()

    # Intento 2: Fallback a afinidad si no hay scores (moléculas viejas)
    if not best_row:
        best_stmt = (
            select(EvaluationResultORM, MoleculeORM, UserORM, TargetORM)
            .join(MoleculeORM, EvaluationResultORM.molecule_id == MoleculeORM.id)
            .join(UserORM, MoleculeORM.user_id == UserORM.id)
            .join(TargetORM, MoleculeORM.target_id == TargetORM.id)
            .where(EvaluationResultORM.affinity_kcal.isnot(None))
            .where(UserORM.username != 'demo')
            .order_by(EvaluationResultORM.affinity_kcal.asc())
            .limit(1)
        )
        best_res = await db.execute(best_stmt)
        best_row = best_res.first()

    best_score = 0.0
    best_molecule_name = "N/A"
    best_molecule_user = "Sistema"
    best_target_pdb = "N/A"

    if best_row:
        eval_res, mol, user, target = best_row
        # Si tiene score, lo usamos. Si no, usamos la afinidad * -10 como score dummy para visualización
        best_score = eval_res.total_score or (abs(eval_res.affinity_kcal) * 5 if eval_res.affinity_kcal else 0)
        best_molecule_name = mol.name or mol.smiles
        best_molecule_user = user.username or user.email.split('@')[0]
        best_target_pdb = target.pdb_id

    # 4. Obtener información del Hot Target actual para la UI
    hot_target_stmt = select(TargetORM).where(TargetORM.is_hot == True).limit(1)
    hot_res = await db.execute(hot_target_stmt)
    hot_target = hot_res.scalar_one_or_none()
    
    hot_info = None
    if hot_target:
        hot_info = {
            "pdb_id": hot_target.pdb_id,
            "name": hot_target.name,
            "spearman_rho": hot_target.spearman_rho,
            "family": hot_target.structural_family
        }

    return {
        "total_molecules": total_mols,
        "total_certifications": total_certs,
        "best_score": round(float(best_score), 1),
        "best_molecule_name": best_molecule_name,
        "best_user_name": best_molecule_user,
        "best_target_pdb": best_target_pdb,
        "hot_target": hot_info,
        "community_status": "Global"
    }
