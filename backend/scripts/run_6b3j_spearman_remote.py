import asyncio
import json
import os
import sys
from pathlib import Path

# Añadir el path raíz
sys.path.append("/app")

from core.config import get_settings
from scripts.calibrate_external_panel import run_calibration

async def run_test():
    settings = get_settings()
    
    # Target PDB y cadena
    settings.default_target_pdb_id = "6B3J"
    settings.default_target_chain = "A"
    
    # [IMPORTANTE] Coordenadas corregidas según la DB del servidor
    settings.vina_center_x = 93.23
    settings.vina_center_y = 148.16
    settings.vina_center_z = 103.33
    settings.vina_size_x = 28.0
    settings.vina_size_y = 28.0
    settings.vina_size_z = 28.0
    
    # Exhaustiveness balanceada (16) para velocidad y rigor
    settings.vina_calibration_exhaustiveness = 16
    
    panel_path = Path("/app/artifacts/bindingdb_glp1r_6b3j_panel.json")
    output_path = Path("/app/artifacts/6b3j_spearman_report_final.json")
    
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    print(f"Iniciando prueba de Spearman FINAL para 6B3J...")
    print(f"Centro: ({settings.vina_center_x}, {settings.vina_center_y}, {settings.vina_center_z})")
    print(f"Exhaustiveness: {settings.vina_calibration_exhaustiveness}")
    
    report = await run_calibration(
        panel_path=panel_path,
        output_path=output_path,
        pchembl_active_threshold=6.5
    )
    
    metrics = report["metrics"]
    print("\nPRUEBA COMPLETADA")
    print(f"Spearman: {metrics['spearman_activity_vs_minus_affinity']:.4f}")
    print(f"Pearson: {metrics['pearson_activity_vs_minus_affinity']:.4f}")
    print(f"Aceptadas: {report['dataset']['n_accepted']}/{report['dataset']['n_input']}")
    print(f"Reporte guardado en: {output_path}")

if __name__ == "__main__":
    asyncio.run(run_test())
