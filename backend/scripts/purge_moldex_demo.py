import asyncio
import sys
import os

# Añadir el backend al path
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from core.database import get_db_session
from sqlalchemy import select, update
from core.models import MoleculeORM, EvaluationResultORM, TargetORM, MoleculeStatus

async def main():
    async with get_db_session() as session:
        # 1. Resetear TODAS las moleculas a is_saved = False
        await session.execute(update(MoleculeORM).values(is_saved=False))
        await session.flush()
        
        # 2. Obtener la mejor molecula (por total_score) para cada target
        targets = (await session.execute(select(TargetORM))).scalars().all()
        
        kept_count = 0
        for target in targets:
            # Buscar la mejor molécula de este target que esté EVALUATED
            stmt = (
                select(MoleculeORM)
                .join(EvaluationResultORM, EvaluationResultORM.molecule_id == MoleculeORM.id)
                .where(MoleculeORM.target_id == target.id)
                .where(MoleculeORM.status == MoleculeStatus.EVALUATED)
                .order_by(EvaluationResultORM.total_score.desc())
                .limit(1)
            )
            best_mol = (await session.execute(stmt)).scalar_one_or_none()
            
            if best_mol:
                best_mol.is_saved = True
                kept_count += 1
                print(f"[{target.pdb_id}] Guardada molécula: {best_mol.name or best_mol.smiles_hash[:8]}")
            else:
                print(f"[{target.pdb_id}] No hay moléculas evaluadas para este target.")
                
        await session.commit()
        print(f"\nPurga completada. Se mantuvieron {kept_count} moléculas (1 por target).")

if __name__ == "__main__":
    asyncio.run(main())
