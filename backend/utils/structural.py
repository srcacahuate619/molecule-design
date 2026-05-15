import re
from pathlib import Path

def validate_hotspots_in_pdb(pdb_path: str | Path, hotspots: list[dict]) -> dict:
    """
    Verifica si los residuos definidos como hotspots existen en el archivo PDB/PDBQT.
    Retorna un diccionario con el estado de cada hotspot.
    """
    pdb_path = Path(pdb_path)
    if not pdb_path.exists():
        return {"error": f"Archivo {pdb_path.name} no encontrado", "valid": False}

    found_residues = set()
    # Regex para extraer nombre y numero: "ATOM    ... MET A  99 ..."
    # Capturamos Nombre (col 18-20) y Numero (col 23-26)
    with open(pdb_path, "r") as f:
        for line in f:
            if line.startswith(("ATOM", "HETATM")):
                res_name = line[17:20].strip().upper()
                res_seq = line[22:26].strip()
                found_residues.add(f"{res_name}{res_seq}")

    report = []
    all_valid = True
    
    for h in hotspots:
        h_name = h["name"].upper()
        if h_name in found_residues:
            report.append({"name": h_name, "status": "FOUND"})
        else:
            all_valid = False
            # Intentar encontrar candidatos sugeridos (mismo aminoácido en otra posición)
            amino = re.sub(r'\d+', '', h_name)
            candidates = [r for r in found_residues if r.startswith(amino)]
            # Tomar los 3 más cercanos numéricamente si es posible
            report.append({
                "name": h_name, 
                "status": "MISSING", 
                "suggestions": candidates[:5]
            })

    return {
        "valid": all_valid,
        "hotspots_checked": len(hotspots),
        "found_count": sum(1 for r in report if r["status"] == "FOUND"),
        "report": report
    }

def discover_pocket_from_pdb(pdb_content: str, target_chain: str = "A") -> dict:
    """
    Analiza un PDB para encontrar el ligando más grande y sugerir
    un grid box y hotspots automáticos.
    """
    ligands = {} # res_id -> list of atom coords
    standard_residues = [] # list of (res_id, res_name, atom_coord)
    
    # Buffers comunes a ignorar
    skip_res = {"HOH", "WAT", "DOD", "SO4", "PO4", "PEG", "EDO", "ACT", "GOL", "DMS"}

    for line in pdb_content.splitlines():
        if not line.startswith(("ATOM", "HETATM")):
            continue
            
        record = line[:6].strip()
        res_name = line[17:20].strip().upper()
        chain = line[21].strip() or "A"
        res_seq = line[22:26].strip()
        res_id = f"{chain}:{res_name}{res_seq}"
        
        try:
            x = float(line[30:38])
            y = float(line[38:46])
            z = float(line[46:54])
        except:
            continue

        if record == "HETATM" and res_name not in skip_res:
            if res_id not in ligands:
                ligands[res_id] = []
            ligands[res_id].append((x, y, z))
        
        if record == "ATOM" and chain == target_chain:
            standard_residues.append((res_id, res_name, (x, y, z)))

    if not ligands:
        return {"success": False, "error": "No se encontraron ligandos de referencia adecuados."}

    # Seleccionar el ligando más grande (más átomos)
    best_res_id = max(ligands, key=lambda k: len(ligands[k]))
    coords = ligands[best_res_id]
    
    # Calcular centroide
    cx = sum(c[0] for c in coords) / len(coords)
    cy = sum(c[1] for c in coords) / len(coords)
    cz = sum(c[2] for c in coords) / len(coords)
    
    # Hotspot mining: Residuos ATOM dentro de 5.0A del ligando
    hotspots = set()
    for res_id, res_name, r_coord in standard_residues:
        for l_coord in coords:
            dist_sq = (r_coord[0]-l_coord[0])**2 + (r_coord[1]-l_coord[1])**2 + (r_coord[2]-l_coord[2])**2
            if dist_sq < 5.0 * 5.0: # 5A threshold
                hotspots.add(res_id)
                break
    
    return {
        "success": True,
        "ligand_id": best_res_id,
        "atom_count": len(coords),
        "grid_center": (round(cx, 2), round(cy, 2), round(cz, 2)),
        "suggested_hotspots": [{"name": h, "importance": 1.0} for h in sorted(list(hotspots))]
    }
