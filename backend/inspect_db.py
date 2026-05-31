import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
import os
from dotenv import load_dotenv

load_dotenv('/app/.env')
DB_URL = os.getenv('DATABASE_URL').replace('postgresql://', 'postgresql+asyncpg://', 1)
engine = create_async_engine(DB_URL)

async def run():
    async with engine.connect() as c:
        # List tables
        res = await c.execute(text("SELECT table_name FROM information_schema.tables WHERE table_schema='public' ORDER BY table_name"))
        print("=== TABLES ===")
        tables = [r[0] for r in res.fetchall()]
        for t in tables:
            print(t)

        # Find the evaluation table and get last entries
        eval_table = next((t for t in tables if 'eval' in t.lower()), None)
        metric_table = next((t for t in tables if 'metric' in t.lower()), None)
        target_table = next((t for t in tables if 'target' in t.lower()), None)
        
        print(f"\n=== GUESSED: eval={eval_table}, metrics={metric_table}, targets={target_table} ===")
        
        if eval_table:
            res2 = await c.execute(text(f"SELECT column_name FROM information_schema.columns WHERE table_name='{eval_table}' AND table_schema='public'"))
            print(f"\n=== COLUMNS of {eval_table} ===")
            for r in res2.fetchall():
                print(r[0])

        if metric_table:
            res3 = await c.execute(text(f"SELECT column_name FROM information_schema.columns WHERE table_name='{metric_table}' AND table_schema='public'"))
            print(f"\n=== COLUMNS of {metric_table} ===")
            for r in res3.fetchall():
                print(r[0])

asyncio.run(run())
