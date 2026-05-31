import asyncio
from core.database import get_db_session
from core.models import MoleculeORM, EvaluationResultORM, TargetORM
from sqlalchemy import select

async def audit_last_two():
    async with get_db_session() as db:
        stmt = (
            select(MoleculeORM, EvaluationResultORM, TargetORM)
            .join(EvaluationResultORM)
            .join(TargetORM)
            .order_by(MoleculeORM.created_at.desc())
            .limit(2)
        )
        result = await db.execute(stmt)
        rows = result.all()
        
        for idx, (mol, eval_res, target) in enumerate(rows, 1):
            print(f"--- Molecule {idx} ---")
            print(f"Name: {mol.name}")
            print(f"SMILES: {mol.smiles}")
            print(f"Target: {target.pdb_id} ({target.name})")
            print(f"Status: {mol.status.name if hasattr(mol.status, 'name') else mol.status}")
            print(f"Affinity: {eval_res.affinity_kcal} kcal/mol")
            print(f"Total Score: {eval_res.total_score}")
            print(f"Hotspots Hit: {eval_res.hotspots_hit}")
            print(f"Scientific Warnings: {eval_res.scientific_warnings}")
            print("")

if __name__ == "__main__":
    asyncio.run(audit_last_two())
