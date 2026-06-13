import asyncio
import sys
import os

sys.path.append(os.getcwd())
from core.database import get_db
from sqlalchemy import text

async def main():
    async for db in get_db():
        q = text("""
            SELECT smiles, experimental_p_value, predicted_affinity, predicted_score, specificity_score 
            FROM benchmark_results 
            WHERE run_id = 'spearman_run_20260609_003641' AND target_id = '7E2Y'
            ORDER BY experimental_p_value DESC
        """)
        res = await db.execute(q)
        rows = res.all()
        print(f"\n=== 7E2Y DETAILED RESULTS ({len(rows)} molecules) ===")
        print(f"{'No.':3} | {'Experimental pKi':16} | {'Pred Affinity (kcal)':20} | {'Pred pKi (aff/-1.36)':20} | {'Pred Score':10} | {'Spec Score':10}")
        print("-" * 90)
        for idx, r in enumerate(rows):
            pred_pki = r[2] / -1.36 if r[2] is not None else 0.0
            print(f"{idx:3} | {r[1]:16.4f} | {r[2]:20.4f} | {pred_pki:20.4f} | {r[3]:10.2f} | {r[4]:10.2f}")
        print("========================================================================\n")

if __name__ == "__main__":
    asyncio.run(main())
