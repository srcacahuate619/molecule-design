import asyncio
from core.database import get_db_session
from sqlalchemy import text

async def main():
    async with get_db_session() as session:
        res = await session.execute(text("SELECT count(*) FROM evaluation_results"))
        print("evaluation_results count:", res.scalar())
        res2 = await session.execute(text("SELECT count(*) FROM benchmark_results"))
        print("benchmark_results count:", res2.scalar())
        res3 = await session.execute(text("SELECT target_id, count(*) FROM benchmark_results GROUP BY target_id"))
        for row in res3.fetchall():
            print(f"  Target {row[0]}: {row[1]}")

if __name__ == "__main__":
    asyncio.run(main())
