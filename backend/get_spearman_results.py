import os
import sys
import asyncio
from sqlalchemy import text

# Add /app to sys.path
sys.path.append("/app")

from core.database import get_db

async def main():
    query = text("""
        SELECT smiles, predicted_affinity, predicted_score 
        FROM benchmark_results 
        WHERE run_id = 'spearman_run_20260518_003743' AND target_id = '3OSK'
        LIMIT 5;
    """)
    
    async for db in get_db():
        result = await db.execute(query)
        rows = result.all()
        break
        
    for r in rows:
        print("SMILES:", r[0][:50])
        print("Predicted Affinity:", r[1])
        print("Predicted Score:", r[2])
        print("-" * 40)

if __name__ == "__main__":
    asyncio.run(main())
