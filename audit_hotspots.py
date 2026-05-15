import subprocess
import json
import sys
from pathlib import Path

# Mock del validador para correrlo desde aquí (o usar el archivo recién creado)
def check_file(pdb_id, hotspots):
    local_pdb = f"data/targets/{pdb_id}.pdb"
    if not Path(local_pdb).exists():
        # Intentar descargar de MinIO o buscar en el servidor
        return f"SKIP: {pdb_id}.pdb no encontrado localmente"
    
    found_residues = set()
    with open(local_pdb, "r") as f:
        for line in f:
            if line.startswith(("ATOM", "HETATM")):
                res_name = line[17:20].strip().upper()
                res_seq = line[22:26].strip()
                found_residues.add(f"{res_name}{res_seq}")
    
    errors = []
    for h in hotspots:
        if h["name"].upper() not in found_residues:
            errors.append(h["name"])
    
    if not errors:
        return "OK"
    else:
        return f"MISSING: {', '.join(errors)}"

def audit_database():
    # 1. Obtener targets y hotspots de la DB remota
    query = "SELECT pdb_id, hotspots FROM targets;"
    cmd = [
        "ssh", "srcacahuate619@192.168.1.64",
        f"docker exec postgres_db psql -U admin -d moldesign_db -t -c \"{query}\""
    ]
    output = subprocess.check_output(cmd).decode()
    
    print("\n=== REPORTE DE AUDITORÍA DE HOTSPOTS (CONTRASTE PDB VS DB) ===\n")
    for line in output.splitlines():
        if not line.strip() or "|" not in line: continue
        pdb_id, hotspots_json = line.split("|")
        pdb_id = pdb_id.strip()
        try:
            hotspots = json.loads(hotspots_json)
            status = check_file(pdb_id, hotspots)
            print(f"Target {pdb_id:5}: {status}")
        except:
            print(f"Target {pdb_id:5}: Error en formato JSON")

if __name__ == "__main__":
    audit_database()
