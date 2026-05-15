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
