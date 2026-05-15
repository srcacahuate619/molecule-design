import asyncio
import sys
import os

# Añadir el path del backend para importar módulos internos
sys.path.append(os.getcwd())

from services.docking.preparer import prepare_target
from core.database import get_db
from db.repository import Repository
from sqlalchemy.ext.asyncio import AsyncSession
from core.models import TargetORM
from sqlalchemy import select

async def main():
    print("🚀 Iniciando preparación científica de nuevos targets...")
    
    # Configuración de targets a preparar
    targets_to_prep = [
        {
            "pdb_id": "2P4E",
            "chain": "A",
            "center": (-14.6, 24.5, -45.7),
            "size": (22.0, 22.0, 22.0),
            "name": "PCSK9 (Orthosteric)"
        },
        {
            "pdb_id": "6U26",
            "chain": "A",
            "center": (10.1, 15.2, -5.3),
            "size": (20.0, 20.0, 20.0),
            "name": "PCSK9 (Alosteric)"
        },
        {
            "pdb_id": "6B3J",
            "chain": "A",
            "center": (118.5, 122.1, 131.4),
            "size": (28.0, 28.0, 28.0),
            "name": "GLP-1 Receptor"
        }
    ]

    async for db in get_db():
        repo = Repository(db)
        
        for t_info in targets_to_prep:
            pdb_id = t_info["pdb_id"]
            print(f"\n--- Preparando {t_info['name']} ({pdb_id}) ---")
            
            try:
                # 1. Ejecutar preparación estructural (Meeko)
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
                    # Actualizar parámetros derivados
                    target_obj.grid_center_x = t_info["center"][0]
                    target_obj.grid_center_y = t_info["center"][1]
                    target_obj.grid_center_z = t_info["center"][2]
                    target_obj.grid_size_x = t_info["size"][0]
                    target_obj.grid_size_y = t_info["size"][1]
                    target_obj.grid_size_z = t_info["size"][2]
                    
                    await db.commit()
                    print(f"✅ DB actualizada para {pdb_id}")
                else:
                    print(f"⚠️ Warning: {pdb_id} no encontrado en la DB (¿corriste el seed?)")
                    
            except Exception as e:
                print(f"❌ Error preparando {pdb_id}: {str(e)}")
        
        break

if __name__ == "__main__":
    asyncio.run(main())
