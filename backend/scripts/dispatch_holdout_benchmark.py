import os
import sys
import json
import asyncio
from datetime import datetime

sys.path.append(os.getcwd())

from api.celery_app import celery_app

TARGETS = [
    "7E2Y", "6B3J", "6X1A", "2P4E", "6U26", "3OSK",
    "3ERT", "5L2I", "2W96", "4JPS", "3O96", "3PP0", "4ZZZ", "1HVY",
    "4I5I", "6D8X", "5IKR", "4RER", "5VEW", "1ERE", "4EKL"
]

async def dispatch_jobs():
    print(f"📥 Despachando panel HOLDOUT a Celery...")
    submitted_jobs = []
    
    from services.docking.queue_handler import run_full_evaluation
    
    for pdb_id in TARGETS:
        panel_path = f"data/benchmark/{pdb_id}_holdout_panel.json"
        if not os.path.exists(panel_path):
            print(f"⚠️ Saltando {pdb_id}: No se encontró el dataset en {panel_path}")
            continue
            
        with open(panel_path, "r", encoding="utf-8") as f:
            compounds = json.load(f)
            
        print(f"   Enviando {len(compounds)} tareas para {pdb_id} (HOLDOUT)...")
        
        for idx, cmp in enumerate(compounds):
            smiles = cmp["smiles"]
            chembl_id = cmp.get("chembl_id", f"unk_{idx}")
            
            task = run_full_evaluation.delay(
                smiles=smiles,
                target_pdb_id=pdb_id,
                molecule_name=f"holdout_{pdb_id}_{chembl_id}",
                is_control=False
            )
            
            submitted_jobs.append(task.id)
            await asyncio.sleep(0.01) # mini cooldown para Redis
            
    print(f"✅ Total de tareas enviadas con éxito a Celery: {len(submitted_jobs)}")
    print(f"Puedes monitorear el progreso usando Flower o 'docker logs -f moldesign_worker'")

if __name__ == "__main__":
    asyncio.run(dispatch_jobs())
