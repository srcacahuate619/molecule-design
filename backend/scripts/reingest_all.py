import asyncio
import sys
import os

# Añadir el path del backend
sys.path.append(os.getcwd())

from services.targets.ingestion_manager import ingest_new_target
from core.database import get_db

async def main():
    targets_to_reingest = [
        {"pdb_id": "6B3J", "chain_id": "R", "ligand_chain": "P", "family": "GPCR", "is_hot": True},
        {"pdb_id": "6X1A", "chain_id": "R", "ligand_chain": None, "family": "GPCR", "is_hot": True}, # UK4 como HETATM en cadena R
        {"pdb_id": "2P4E", "chain_id": "A", "ligand_chain": None, "family": "Serine Protease", "is_hot": True},
        {"pdb_id": "6U26", "chain_id": "B", "ligand_chain": None, "family": "Serine Protease", "is_hot": True},
        {"pdb_id": "4NC3", "chain_id": "A", "ligand_chain": None, "family": "Serine Protease", "is_hot": True},
        {"pdb_id": "3ERT", "chain_id": "A", "ligand_chain": None, "family": "Nuclear Receptor", "is_hot": True},
        {"pdb_id": "5L2I", "chain_id": "A", "ligand_chain": None, "family": "Kinase", "is_hot": True},
        {"pdb_id": "2W96", "chain_id": "B", "ligand_chain": None, "family": "Kinase", "is_hot": True},
        {"pdb_id": "4JPS", "chain_id": "A", "ligand_chain": None, "family": "Kinase", "is_hot": True},
        {"pdb_id": "3O96", "chain_id": "A", "ligand_chain": None, "family": "Kinase", "is_hot": True},
        {"pdb_id": "3PP0", "chain_id": "A", "ligand_chain": None, "family": "Kinase", "is_hot": True},
        {"pdb_id": "4ZZZ", "chain_id": "A", "ligand_chain": None, "family": "Polymerase", "is_hot": True},
        {"pdb_id": "1HVY", "chain_id": "A", "ligand_chain": None, "family": "Transferase", "is_hot": True},
    ]
    
    print("🚀 Iniciando Re-ingesta masiva para actualizar Hotspots...")
    async for db in get_db():
        for t in targets_to_reingest:
            print(f"📦 Procesando {t['pdb_id']}...")
            try:
                result = await ingest_new_target(
                    pdb_id=t["pdb_id"],
                    db=db,
                    chain_id=t["chain_id"],
                    ligand_chain=t["ligand_chain"],
                    is_hot=t["is_hot"],
                    structural_family=t["family"],
                    force_reingest=True
                )
                print(f"✅ {t['pdb_id']} completado: {result.get('hotspots_mined', 0)} hotspots.")
            except Exception as e:
                print(f"❌ Error en {t['pdb_id']}: {str(e)}")
        break

if __name__ == "__main__":
    asyncio.run(main())
