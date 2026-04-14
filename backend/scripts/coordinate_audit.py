"""
coordinate_audit.py

Audit script to compare the first 3 atoms' coordinates between a docked ligand _out.pdbqt and the final _out.sdf.
If any coordinate differs by >0.001 Å, prints a warning and the values for inspection.

Usage:
    python coordinate_audit.py path/to/ligand_out.pdbqt path/to/ligand_out.sdf

Requirements:
    - RDKit (for SDF parsing)
"""
import sys
import re
from pathlib import Path
from rdkit import Chem

def parse_pdbqt_coords(pdbqt_path, n_atoms=3):
    coords = []
    with open(pdbqt_path, 'r') as f:
        for line in f:
            if line.startswith(('ATOM', 'HETATM')):
                fields = line.split()
                # PDBQT: columns 7,8,9 are X,Y,Z (1-based)
                try:
                    x = float(line[30:38])
                    y = float(line[38:46])
                    z = float(line[46:54])
                    coords.append((x, y, z))
                except Exception:
                    continue
                if len(coords) >= n_atoms:
                    break
    return coords

def parse_sdf_coords(sdf_path, n_atoms=3):
    suppl = Chem.SDMolSupplier(str(sdf_path), removeHs=False)
    mol = next((m for m in suppl if m is not None), None)
    if mol is None or mol.GetNumAtoms() < n_atoms:
        return []
    conf = mol.GetConformer()
    coords = []
    for i in range(n_atoms):
        pos = conf.GetAtomPosition(i)
        coords.append((pos.x, pos.y, pos.z))
    return coords

def compare_coords(coords1, coords2, tol=0.001):
    if len(coords1) != len(coords2):
        print(f"[ERROR] Atom count mismatch: {len(coords1)} vs {len(coords2)}")
        return False
    all_match = True
    for i, (a, b) in enumerate(zip(coords1, coords2)):
        diffs = [abs(a[j] - b[j]) for j in range(3)]
        if any(d > tol for d in diffs):
            print(f"[WARNING] Atom {i+1} coordinate mismatch:")
            print(f"  PDBQT: {a}")
            print(f"  SDF:   {b}")
            print(f"  Diffs: {diffs}")
            all_match = False
        else:
            print(f"[OK] Atom {i+1} matches within tolerance: {a} vs {b}")
    return all_match

def main():
    if len(sys.argv) != 3:
        print("Usage: python coordinate_audit.py path/to/ligand_out.pdbqt path/to/ligand_out.sdf")
        sys.exit(1)
    pdbqt_path, sdf_path = sys.argv[1:3]
    if not Path(pdbqt_path).exists() or not Path(sdf_path).exists():
        print("[ERROR] One or both files do not exist.")
        sys.exit(1)
    pdbqt_coords = parse_pdbqt_coords(pdbqt_path)
    sdf_coords = parse_sdf_coords(sdf_path)
    print(f"First 3 atoms from {pdbqt_path}: {pdbqt_coords}")
    print(f"First 3 atoms from {sdf_path}: {sdf_coords}")
    if not pdbqt_coords or not sdf_coords:
        print("[ERROR] Could not extract coordinates from one or both files.")
        sys.exit(1)
    match = compare_coords(pdbqt_coords, sdf_coords)
    if match:
        print("[SUCCESS] All coordinates match within tolerance. Conversion is spatially correct.")
    else:
        print("[FAIL] At least one atom coordinate differs >0.001 Å. Conversion is NOT spatially faithful.")

if __name__ == "__main__":
    main()
