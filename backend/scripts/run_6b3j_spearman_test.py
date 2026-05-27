import asyncio
import json
import os
import sys
from pathlib import Path

# Añadir el path raíz para importar módulos del backend
sys.path.append(os.path.join(os.getcwd(), "backend"))

# Configurar entorno para el servidor local/remoto
# IMPORTANTE: define estas variables en tu .env o como variables de entorno
# antes de ejecutar este script. No hardcodees credenciales aquí.
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://admin:your_db_password@localhost:5432/moldesign_db")
os.environ.setdefault("MINIO_ACCESS_KEY", "admin")
os.environ.setdefault("MINIO_SECRET_KEY", "your_minio_password")
os.environ.setdefault("MINIO_ENDPOINT", "localhost:9005")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("SECRET_KEY", "a" * 64)

from core.config import get_settings
from scripts.calibrate_external_panel import run_calibration

async def run_test():
    settings = get_settings()
    
    # Sobreescribir el target por defecto temporalmente para la calibración
    # En un sistema ideal, run_calibration aceptaría el pdb_id como parámetro.
    # Por ahora lo forzamos en settings para que el script lo tome.
    settings.default_target_pdb_id = "6B3J"
    settings.default_target_chain = "A" # Según mi check previo
    
    # Coordenadas específicas de 6B3J (obtenidas de la DB en el paso previo)
    settings.vina_center_x = 138.868
    settings.vina_center_y = 139.756
    settings.vina_center_z = 148.601
    settings.vina_size_x = 25.0
    settings.vina_size_y = 25.0
    settings.vina_size_z = 25.0
    
    # Usar exhaustividad alta para benchmark
    settings.vina_calibration_exhaustiveness = 32
    
    panel_path = Path("artifacts") / "bindingdb_glp1r_6b3j_panel.json"
    output_path = Path("artifacts") / "6b3j_spearman_report.json"
    
    print(f"Iniciando prueba de Spearman para 6B3J...")
    print(f"Panel: {panel_path}")
    print(f"Target: {settings.default_target_pdb_id} (Chain {settings.default_target_chain})")
    print(f"Grid: Center({settings.vina_center_x}, {settings.vina_center_y}, {settings.vina_center_z})")
    
    report = await run_calibration(
        panel_path=panel_path,
        output_path=output_path,
        pchembl_active_threshold=6.5 # Ajustado para GLP-1R
    )
    
    metrics = report["metrics"]
    print("\nPRUEBA COMPLETADA")
    print(f"Spearman: {metrics['spearman_activity_vs_minus_affinity']:.4f}")
    print(f"Pearson: {metrics['pearson_activity_vs_minus_affinity']:.4f}")
    print(f"MAPE: {metrics['mape_pct_activity_vs_minus_affinity']:.2f}%")
    print(f"Reporte guardado en: {output_path}")

if __name__ == "__main__":
    asyncio.run(run_test())
