import os
import re
import sys
import subprocess

REPORT_PATH = "docs/Spearman_Report_Latest.md"

def get_average_spearman(report_path):
    if not os.path.exists(report_path):
        print(f"Error: No se encontró el reporte en {report_path}")
        return None
        
    spearman_values = []
    
    with open(report_path, "r", encoding="utf-8") as f:
        lines = f.readlines()
        
    in_table = False
    for line in lines:
        line = line.strip()
        if line.startswith("| Dianas Terapéuticas"):
            in_table = True
            continue
        if in_table and line.startswith("|---"):
            continue
        if in_table and line.startswith("|"):
            parts = line.split("|")
            if len(parts) >= 6:
                rho_str = parts[4].replace("*", "").strip()
                try:
                    rho = float(rho_str)
                    spearman_values.append(rho)
                except ValueError:
                    pass
        elif in_table and not line:
            in_table = False
            
    if not spearman_values:
        return 0.0
        
    avg_rho = sum(spearman_values) / len(spearman_values)
    return avg_rho

import time

def main():
    print("🔍 Analizando resultados de la prueba piloto...")
    avg_rho = get_average_spearman(REPORT_PATH)
    
    if avg_rho is None:
        sys.exit(1)
        
    print(f"📊 Spearman Promedio de la prueba piloto: {avg_rho:.3f}")
    
    if avg_rho > 0.5:
        print("✅ ¡Condición superada! (Spearman > 0.5). Disparando escalado a 50 moléculas en los 21 receptores...")
        
        # Llama a la siguiente prueba
        env = os.environ.copy()
        env["PYTHONPATH"] = "backend"
        env["PYTHONIOENCODING"] = "utf-8"
        cmd = ["python", "-u", "backend/scripts/run_global_spearman_benchmark.py", "--limit", "50"]
        
        print(f"🚀 Ejecutando: {' '.join(cmd)}")
        # Usa subprocess para lanzar el escalado y dejarlo correr
        subprocess.Popen(cmd, env=env)
    else:
        print("❌ La condición de Spearman > 0.5 NO se cumplió. Se aborta el escalado a 50 moléculas.")
        print("💡 Sugerencia: Revisa la calibración de la GNN o los logs de Celery para identificar anomalías termodinámicas.")
        
if __name__ == "__main__":
    main()
