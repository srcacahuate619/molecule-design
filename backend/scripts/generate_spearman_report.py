import asyncio
import os
import json
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from scipy.stats import spearmanr
from sqlalchemy import text
import matplotlib.pyplot as plt

from core.database import get_db

async def generate_report():
    print("Extraigo resultados de la base de datos...")
    
    # Extraer evaluaciones de las últimas 12 horas, excluyendo targets APO (Bug #6)
    query = """
        SELECT 
            t.pdb_id, 
            m.smiles, 
            m.name,
            e.affinity_kcal, 
            e.specificity_score,
            e.affinity_score,
            e.gnn_score,
            e.total_score
        FROM evaluation_results e
        JOIN molecules m ON e.molecule_id = m.id
        JOIN targets t ON m.target_id = t.id
        WHERE m.created_at > NOW() - INTERVAL '24 hours'
          AND e.affinity_kcal IS NOT NULL
          AND t.pdb_id NOT IN ('2W96', '6B3J')
    """
    
    results = []
    try:
        async for db in get_db():
            res = await db.execute(text(query))
            rows = res.fetchall()
            for r in rows:
                results.append({
                    "target_id": r.pdb_id,
                    "smiles": r.smiles,
                    "name": r.name,
                    "affinity_kcal": r.affinity_kcal,
                    "specificity_score": r.specificity_score,
                    "affinity_score": r.affinity_score,
                    "gnn_score": r.gnn_score
                })
            break
    except Exception as e:
        print(f"Error conectando a DB: {e}")
        return

    if not results:
        print("No hay evaluaciones recientes terminadas en la DB.")
        return

    df_db = pd.DataFrame(results)
    
    # Necesitamos cruzar esto con los valores experimentales pChEMBL de los JSON
    print("Cruzando con datos experimentales (pChEMBL)...")
    target_groups = df_db.groupby("target_id")
    
    report_lines = []
    report_lines.append("# Reporte de Correlación Spearman (Extraído de BD)")
    report_lines.append(f"**Fecha de extracción:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report_lines.append("")
    report_lines.append("| Target | Nombre | N moléculas | Spearman XGBoost (ρ) | Spearman GNN (ρ) | Spearman Combinado (ρ) | Estado |")
    report_lines.append("|---|---|---|---|---|---|---|")
    
    global_exp = []
    global_pred_xgb = []
    global_pred_gnn = []
    global_pred_combined = []
    
    from rdkit import Chem
    
    for target_id, group in target_groups:
        # Exclude APO targets from Spearman validation (Bug #6)
        if target_id in ["2W96", "6B3J"]:
            continue
        json_path = f"data/benchmark/{target_id}_panel.json"
        if not os.path.exists(json_path):
            continue
            
        with open(json_path, 'r') as f:
            exp_data = json.load(f)
            
        target_exp = []
        target_pred = []
        target_pred_gnn = []
        target_pred_combined = []
        
        # Match using molecule name: bench_TARGET_idx
        for _, row in group.iterrows():
            m_name = row['name']
            if m_name.startswith('bench_'):
                try:
                    idx = int(m_name.split('_')[-1])
                    if idx < len(exp_data):
                        item = exp_data[idx]
                        exp_val = item.get('p_value', item.get('pchembl_value', 0.0))
                        
                        pred_pchembl = -row['affinity_kcal'] / 1.36
                        gnn_val = row['gnn_score']
                        
                        target_exp.append(exp_val)
                        target_pred.append(pred_pchembl)
                        
                        global_exp.append(exp_val)
                        global_pred_xgb.append(pred_pchembl)
                        
                        if gnn_val is not None:
                            target_pred_gnn.append(gnn_val)
                            global_pred_gnn.append(gnn_val)
                            
                            # Combined score (50% Vina/XGBoost pKi equivalent + 50% GNN score)
                            comb_val = 0.5 * pred_pchembl + 0.5 * gnn_val
                            target_pred_combined.append(comb_val)
                            global_pred_combined.append(comb_val)
                        else:
                            # Default to mean or 0 to keep lengths same if missing
                            target_pred_gnn.append(0.0)
                            global_pred_gnn.append(0.0)
                            
                            target_pred_combined.append(pred_pchembl)
                            global_pred_combined.append(pred_pchembl)
                            
                except Exception:
                    pass
                
        if len(target_exp) > 2:
            rho_xgb, pval_xgb = spearmanr(target_exp, target_pred)
            rho_gnn, pval_gnn = spearmanr(target_exp, target_pred_gnn)
            rho_comb, pval_comb = spearmanr(target_exp, target_pred_combined)
            
            estado = "✅" if rho_xgb > 0.5 or rho_gnn > 0.5 or rho_comb > 0.5 else "⚠️"
            
            rho_xgb_str = f"{rho_xgb:.3f}" if not np.isnan(rho_xgb) else "nan"
            rho_gnn_str = f"{rho_gnn:.3f}" if not np.isnan(rho_gnn) else "nan"
            rho_comb_str = f"{rho_comb:.3f}" if not np.isnan(rho_comb) else "nan"
            
            report_lines.append(f"| {target_id} | Target {target_id} | {len(target_exp)} | {rho_xgb_str} | {rho_gnn_str} | {rho_comb_str} | {estado} |")
        else:
            report_lines.append(f"| {target_id} | Target {target_id} | {len(target_exp)} | N/A | N/A | N/A | ❌ Incompleto |")
            
    if len(global_exp) > 2:
        global_rho_xgb, _ = spearmanr(global_exp, global_pred_xgb)
        
        # Filtrar valores válidos de GNN para el global
        valid_gnn_mask = np.array(global_pred_gnn) > 0.0
        if np.sum(valid_gnn_mask) > 2:
            sub_exp = np.array(global_exp)[valid_gnn_mask]
            sub_xgb = np.array(global_pred_xgb)[valid_gnn_mask]
            sub_gnn = np.array(global_pred_gnn)[valid_gnn_mask]
            
            # Normalización Z-score
            xgb_std_val = np.std(sub_xgb)
            gnn_std_val = np.std(sub_gnn)
            xgb_norm = (sub_xgb - np.mean(sub_xgb)) / (xgb_std_val if xgb_std_val > 0 else 1.0)
            gnn_norm = (sub_gnn - np.mean(sub_gnn)) / (gnn_std_val if gnn_std_val > 0 else 1.0)
            
            # Spearman GNN puro
            global_rho_gnn, _ = spearmanr(sub_exp, sub_gnn)
            
            # Combinación 50/50 Z-score
            comb_50_50 = 0.5 * xgb_norm + 0.5 * gnn_norm
            global_rho_comb_50, _ = spearmanr(sub_exp, comb_50_50)
            
            # Combinación 30/70 Z-score (Optimizado)
            comb_30_70 = 0.3 * xgb_norm + 0.7 * gnn_norm
            global_rho_comb_30, _ = spearmanr(sub_exp, comb_30_70)
        else:
            global_rho_gnn = float('nan')
            global_rho_comb_50 = float('nan')
            global_rho_comb_30 = float('nan')
            
        report_lines.append("")
        report_lines.append(f"### 🌐 Correlación Global")
        report_lines.append(f"- **Total moléculas evaluadas:** {len(global_exp)}")
        report_lines.append(f"- **Spearman Global XGBoost (ρ):** {global_rho_xgb:.3f}")
        report_lines.append(f"- **Spearman Global GNN (ρ):** {global_rho_gnn:.3f}")
        report_lines.append(f"- **Spearman Global Combinado (50/50 Z-score) (ρ):** {global_rho_comb_50:.3f}")
        report_lines.append(f"- **Spearman Global Combinado (30/70 Z-score Optimizado) (ρ):** {global_rho_comb_30:.3f}")
        
    with open("Spearman_Report_Extracted.md", "w", encoding="utf-8") as f:
        f.write("\n".join(report_lines))
        
    print(f"[SUCCESS] Reporte generado: Spearman_Report_Extracted.md con {len(global_exp)} moléculas cruzadas.")

if __name__ == "__main__":
    asyncio.run(generate_report())
