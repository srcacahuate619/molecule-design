import asyncio
import sys
import os
import json

sys.path.append(os.getcwd())

from services.docking.vina_service import run_vina_docking
from chem.validator import validate_smiles
from chem.conformer import generate_conformer

async def benchmark():
    # Panel de Calibración GLP-1R (Agonistas conocidos)
    panel = [
        {"name": "Danuglipron", "smiles": "C[C@@]1(OC2=CC=CC(=C2O1)C3CCN(CC3)CC4=NC5=C(N4C[C@@H]6CCO6)C=C(C=C5)C(=O)O)C7=NC=C(C=C7)Cl"},
        {"name": "Lotiglipron", "smiles": "CC1(CCN(CC1)CC2=NC3=C(N2C[C@@H]4CCO4)C=C(C=C3)C(=O)O)C5=NC=C(C=C5)Cl"},
        {"name": "Control Negativo (Aspirina)", "smiles": "CC(=O)OC1=CC=CC=C1C(=O)O"},
        {"name": "Control Negativo (Cafeína)", "smiles": "CN1C=NC2=C1C(=O)N(C(=O)N2C)C"}
    ]
    
    pdb_id = "6B3J"
    results = []
    
    print(f"🧪 Iniciando Benchmarking de Calibración para {pdb_id}...")
    
    from db.repository import Repository
    from core.database import get_db
    
    target_data = None
    async for db in get_db():
        repo = Repository(db)
        target_data = await repo.get_target_by_pdb_id(pdb_id)
        break
    
    if not target_data:
        print(f"❌ Target {pdb_id} no encontrado en DB.")
        return
        
    center = (target_data.grid_center_x, target_data.grid_center_y, target_data.grid_center_z)
    size = (target_data.grid_size_x, target_data.grid_size_y, target_data.grid_size_z)
    hotspots = target_data.hotspots

    for mol in panel:
        print(f"🔄 Evaluando {mol['name']}...")
        val = validate_smiles(mol['smiles'])
        await generate_conformer(mol['smiles'])
        
        try:
            # Usar exhaustiveness alta para calibración (32)
            docking = await run_vina_docking(
                smiles_hash=val.smiles_hash,
                target_pdb_id=pdb_id,
                target_chain=target_data.chain,
                target_center=center,
                target_size=size,
                force_redock=True,
                hotspots=hotspots
            )
            
            results.append({
                "name": mol['name'],
                "affinity": docking.best_affinity,
                "hotspots": docking.hotspots_hit
            })
            print(f"  ✅ Aff: {docking.best_affinity} kcal/mol | Hotspots: {len(docking.hotspots_hit)}")
        except Exception as e:
            print(f"  ❌ Error: {str(e)}")
            
    # Sugerir Threshold
    actives = [r['affinity'] for r in results if "Control Negativo" not in r['name']]
    inactives = [r['affinity'] for r in results if "Control Negativo" in r['name']]
    
    if actives and inactives:
        suggested = (max(actives) + min(inactives)) / 2
        print(f"\n📊 ANÁLISIS DE CALIBRACIÓN:")
        print(f"  Media Activos: {sum(actives)/len(actives):.2f}")
        print(f"  Media Inactivos: {sum(inactives)/len(inactives):.2f}")
        print(f"  🚀 Threshold sugerido para {pdb_id}: {round(suggested, 1)}")

if __name__ == "__main__":
    asyncio.run(benchmark())
