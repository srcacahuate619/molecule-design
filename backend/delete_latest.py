import asyncio
from core.database import get_db_session
from core.models import MoleculeORM, EvaluationResultORM
from sqlalchemy import select, delete

async def delete_latest():
    async with get_db_session() as db:
        stmt = select(MoleculeORM).order_by(MoleculeORM.created_at.desc()).limit(1)
        result = await db.execute(stmt)
        mol = result.scalar_one_or_none()
        
        if mol:
            await db.execute(delete(EvaluationResultORM).where(EvaluationResultORM.molecule_id == mol.id))
            await db.execute(delete(MoleculeORM).where(MoleculeORM.id == mol.id))
            await db.commit()
            print("Deleted latest molecule from DB.")

if __name__ == "__main__":
    asyncio.run(delete_latest())
