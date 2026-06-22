import os
import sys
import math
import asyncio
from scipy.stats import spearmanr

sys.path.append(os.getcwd())
from core.database import get_db
from sqlalchemy import text

TARGETS = {
    "4JPS": "PIK3CA WT",
    "4ZZZ": "PARP1",
    "3PP0": "HER2 Kinase",
    "3ERT": "ER-alpha",
    "6X1A": "GLP-1R",
    "5L2I": "CDK6",
    "2W96": "CDK4",
    "3O96": "AKT1",
    "1HVY": "Thymidylate Synthase"
}

async def calc_stats():
    run_id = "spearman_run_20260607_191444_new"
    print(f"📊 Calculando Coeficiente de Spearman para {run_id}...\n")
    
    async for db in get_db():
        for pdb_id, name in TARGETS.items():
            # Exclude APO targets from Spearman validation (Bug #6)
            if pdb_id in ["2W96", "6B3J"]:
                continue
            q = text("""
                SELECT experimental_value, predicted_affinity, predicted_score
                FROM benchmark_results 
                WHERE run_id = :run_id AND target_id = :target_id
            """)
            res = await db.execute(q, {"run_id": run_id, "target_id": pdb_id})
            rows = res.fetchall()
            
            if len(rows) < 2:
                print(f"⚠️ {pdb_id} ({name}): Datos insuficientes ({len(rows)})")
                continue
                
            y_real = [float(r[0]) for r in rows] # pKi / experimental_value_nm
            # Para Spearman, si experimental_value es pKi o IC50, el orden importa. 
            # Los _panel.json asumen pKi (mayor es más potente) o p_value? 
            # run_global_spearman_benchmark.py usa experimental_p_value (pKi).
            # Vina affinity es negativo (menor es más potente). 
            # Así que correlacionamos -affinity con pKi.
            y_pred = [-float(r[1]) for r in rows]
            
            rho, p_val = spearmanr(y_pred, y_real)
            
            status = "🔴 Inválido"
            if not math.isnan(rho):
                if rho > 0.45:
                    status = "🏆 Certificado (Producción)" if pdb_id in ["6X1A"] else "🟢 Validado"
                elif rho > 0.30:
                    status = "🟡 Débil"
            
            print(f"[{status}] {pdb_id} ({name}): N={len(rows)} | Spearman ρ = {rho:.3f} (p-value={p_val:.2e})")
            
        break

if __name__ == "__main__":
    asyncio.run(calc_stats())
