import asyncio
from core.database import SessionLocal
from core.models import EvaluationResultORM
from sqlalchemy import update

async def clear_errors():
    async with SessionLocal() as db:
        stmt = update(EvaluationResultORM).where(EvaluationResultORM.ai_report.like('No se pudo%')).values(ai_report=None)
        await db.execute(stmt)
        await db.commit()
        print('Errores de IA cacheados borrados con exito.')

if __name__ == '__main__':
    asyncio.run(clear_errors())
