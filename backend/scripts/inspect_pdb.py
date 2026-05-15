import asyncio
import sys
import os

sys.path.append(os.getcwd())

from utils.file_handlers import download_pdb_from_rcsb
from core.config import get_settings

async def main(pdb_id):
    print(f"🔍 Inspeccionando PDB {pdb_id} desde RCSB...")
    content = await download_pdb_from_rcsb(pdb_id)
    
    # Ver ligandos HETATM y su cercanía a cadenas
    ligand_coords = {}
    atom_coords = {} # chain -> list of coords
    
    for line in content.splitlines():
        if line.startswith("ATOM"):
            chain = line[21].strip()
            x, y, z = float(line[30:38]), float(line[38:46]), float(line[46:54])
            if chain not in atom_coords: atom_coords[chain] = []
            atom_coords[chain].append((x,y,z))
            
        if line.startswith("HETATM"):
            res_name = line[17:20].strip()
            if "HOH" in res_name: continue
            chain = line[21].strip()
            res_seq = line[22:26].strip()
            res_id = f"{chain}:{res_name}{res_seq}"
            x, y, z = float(line[30:38]), float(line[38:46]), float(line[46:54])
            if res_id not in ligand_coords: ligand_coords[res_id] = []
            ligand_coords[res_id].append((x,y,z))
            
    print("💎 Análisis de Proximidad:")
    for lid, l_coords in ligand_coords.items():
        print(f"  Ligando {lid}:")
        for chain, a_coords in atom_coords.items():
            # Encontrar distancia mínima
            min_d2 = 9999.0
            for lc in l_coords:
                for ac in a_coords:
                    d2 = (lc[0]-ac[0])**2 + (lc[1]-ac[1])**2 + (lc[2]-ac[2])**2
                    if d2 < min_d2: min_d2 = d2
            print(f"    - Distancia a Cadena {chain}: {min_d2**0.5:.2f} Å")

if __name__ == "__main__":
    pdb = sys.argv[1] if len(sys.argv) > 1 else "6U26"
    asyncio.run(main(pdb))
