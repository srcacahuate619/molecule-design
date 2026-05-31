import asyncio
from core.database import async_session_maker
from core.models import EvaluationResultORM
from sqlalchemy import select

async def run():
    async with async_session_maker() as session:
        res = await session.execute(select(EvaluationResultORM).order_by(EvaluationResultORM.evaluated_at.desc()).limit(1))
        row = res.scalar_one_or_none()
        if row:
            print(f"hotspots_hit: {row.hotspots_hit}")
        else:
            print("No rows")

asyncio.run(run())
