import asyncio
import sys
import os

# Añadir el path del backend para importar módulos internos
sys.path.append(os.getcwd())

from services.docking.preparer import prepare_target
from core.database import get_db
from db.repository import Repository

async def main():
    print("🚀 Iniciando preparación científica de TODOS los 5 targets activos...")
    
    # Configuración de targets basada exactamente en los registros de la DB
    targets_to_prep = [
        {
            "pdb_id": "7E2Y",
            "chain": "R",
            "center": (103.03, 114.79, 108.36),
            "size": (25.0, 25.0, 25.0),
            "name": "5-HT1A Serotonin Receptor"
        },
        {
            "pdb_id": "6B3J",
            "chain": "R",      # Cadena R = GLP-1R (confirmado RCSB API)
            "center": (93.23, 148.16, 103.33),  # Centroide Exendin-P5 (diff=0.01 Å)
            "size": (30.0, 30.0, 30.0),         # 30 Å para cubrir interfaz ECD péptido
            "name": "GLP-1R (ECD / Peptide Pocket)"
        },
        {
            "pdb_id": "6X1A",
            "chain": "R",      # Cadena R = GLP-1R (confirmado RCSB API)
            "center": (131.35, 116.78, 155.04), # Centroide UK4/Danuglipron (diff=0.0000 Å)
            "size": (30.0, 30.0, 30.0),         # 30 Å recomendado por dimensiones del ligando
            "name": "GLP-1R (TMD / Oral Agonist Pocket)"
        },
        {
            "pdb_id": "2P4E",
            "chain": "A",
            "center": (28.82, 31.75, 40.92),
            "size": (22.0, 22.0, 22.0),
            "name": "PCSK9 (Orthosteric)"
        },
        {
            "pdb_id": "6U26",
            "chain": "A",
            "center": (40.87, 30.19, 29.78),
            "size": (20.0, 20.0, 20.0),
            "name": "PCSK9 (Allosteric)"
        },
        {
            "pdb_id": "3OSK",
            "chain": "A",
            "center": (-2.132, -19.592, 22.149),
            "size": (25.0, 25.0, 25.0),
            "name": "CTLA-4 Immune Checkpoint"
        },
        {
            "pdb_id": "3ERT",
            "chain": "A",
            "center": (31.57, -1.59, 25.60),
            "size": (25.0, 25.0, 25.0),
            "name": "ER-alpha LBD (Tamoxifen)"
        },
        {
            "pdb_id": "5L2I",
            "chain": "A",
            "center": (13.98, 28.18, 9.65),
            "size": (25.0, 25.0, 25.0),
            "name": "CDK6 (Palbociclib)"
        },
        {
            "pdb_id": "2W96",
            "chain": "B",
            "center": (7.41, 2.10, 81.55),
            "size": (25.0, 25.0, 25.0),
            "name": "CDK4 (Apo/Cyclin D1)"
        },
        {
            "pdb_id": "4JPS",
            "chain": "A",
            "center": (-1.32, -9.51, 16.95),
            "size": (25.0, 25.0, 25.0),
            "name": "PIK3CA WT (Alpelisib)"
        },
        {
            "pdb_id": "3O96",
            "chain": "A",
            "center": (8.37, -6.83, 12.62),
            "size": (25.0, 25.0, 25.0),
            "name": "AKT1 (Allosteric Inhibitor VIII)"
        },
        {
            "pdb_id": "3PP0",
            "chain": "A",
            "center": (25.86, 30.61, 7.55),
            "size": (25.0, 25.0, 25.0),
            "name": "HER2 Kinase Domain (SYR-475)"
        },
        {
            "pdb_id": "4ZZZ",
            "chain": "A",
            "center": (55.81, 0.16, 22.52),
            "size": (25.0, 25.0, 25.0),
            "name": "PARP1 LBD (NMS-P118)"
        },
        {
            "pdb_id": "1HVY",
            "chain": "A",
            "center": (25.99, 19.63, 17.19),
            "size": (25.0, 25.0, 25.0),
            "name": "Thymidylate Synthase (Raltitrexed)"
        }
    ]

    async for db in get_db():
        repo = Repository(db)
        
        for t_info in targets_to_prep:
            pdb_id = t_info["pdb_id"]
            print(f"\n--- Preparando {t_info['name']} ({pdb_id}) ---")
            
            try:
                # 1. Ejecutar preparación estructural (Meeko/OpenBabel)
                path = await prepare_target(
                    pdb_id=pdb_id,
                    chain_id=t_info["chain"],
                    center=t_info["center"],
                    size=t_info["size"],
                    force_reprepare=True
                )
                print(f"✅ Archivo PDBQT generado y subido: {path}")
                
                # 2. Actualizar estado en la DB usando el Repositorio
                target_obj = await repo.get_target_by_pdb_id(pdb_id)
                
                if target_obj:
                    target_obj.is_prepared = True
                    target_obj.prepared_file_path = path
                    target_obj.grid_center_x = t_info["center"][0]
                    target_obj.grid_center_y = t_info["center"][1]
                    target_obj.grid_center_z = t_info["center"][2]
                    target_obj.grid_size_x = t_info["size"][0]
                    target_obj.grid_size_y = t_info["size"][1]
                    target_obj.grid_size_z = t_info["size"][2]
                    
                    await db.commit()
                    print(f"✅ DB actualizada para {pdb_id}")
                else:
                    print(f"⚠️ Warning: {pdb_id} no encontrado en la DB")
                    
            except Exception as e:
                print(f"❌ Error preparando {pdb_id}: {str(e)}")
        
        break

if __name__ == "__main__":
    asyncio.run(main())
