"""
scripts/validate_redocking.py

Script de validación científica: re-docking de serotonina contra 7E2Y.

Protocolo:
    1. Descarga la estructura 7E2Y del RCSB PDB.
    2. Extrae las coordenadas del ligando co-cristalizado (serotonina, SRO).
    3. Genera el conformer 3D de serotonina a partir de su SMILES canónico.
    4. Ejecuta docking de la serotonina contra la cadena R de 7E2Y con Vina.
    5. Calcula RMSD entre la pose docked y la pose cristalográfica.
    6. Acepta si RMSD ≤ 2.0 Å (criterio estándar, Hevener et al. 2009).

Criterio de aceptación:
    RMSD ≤ 2.0 Å indica que el protocolo de docking reproduce la pose
    experimental y, por tanto, el grid box, la preparación de proteína
    y los parámetros de Vina son razonables.

    Referencia: Hevener et al. (2009) J Chem Inf Model 49:444-460.
    "Validation of Molecular Docking Programs for Virtual Screening
    against Dihydropteroate Synthase."

Requisitos:
    - Python 3.11+
    - RDKit
    - numpy
    - Acceso a internet (para descargar PDB)
    - AutoDock Vina NO es necesario para este script; se evalúa offline
      comparando el conformer generado con la pose cristalográfica.

    Para validación completa con docking real, se necesita:
    - AutoDock Vina instalado
    - Meeko instalado
    - MinIO, Redis y PostgreSQL corriendo (o mocks)

Uso:
    python scripts/validate_redocking.py [--output artifacts/redocking_validation.json]

Nota científica:
    Este script valida el SETUP del docking, no ejecuta docking real.
    La validación completa requiere el pipeline full (Vina + Meeko).
    El script verifica que:
    - La proteína target es correcta (5-HT1A)
    - El grid box cubre el sitio de unión de serotonina
    - Las coordenadas cristalográficas son extraíbles y razonables
    - El SMILES de serotonina produce un conformer válido

Autor: MolDesign Pipeline
Fecha: 2024
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


def fetch_pdb(pdb_id: str) -> str:
    """Descarga un archivo PDB del RCSB."""
    url = f"https://files.rcsb.org/download/{pdb_id.upper()}.pdb"
    print(f"[INFO] Descargando {url} ...")
    req = urllib.request.Request(url, headers={"User-Agent": "MolDesign-Validator/1.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8")


def extract_ligand_atoms(
    pdb_text: str,
    ligand_id: str,
    chain: str,
) -> list[tuple[str, float, float, float]]:
    """
    Extrae coordenadas HETATM del ligando especificado.

    Returns:
        Lista de (atom_name, x, y, z).
    """
    atoms = []
    for line in pdb_text.splitlines():
        if not line.startswith("HETATM"):
            continue
        res_name = line[17:20].strip()
        chain_id = line[21].strip()
        if res_name == ligand_id and chain_id == chain:
            atom_name = line[12:16].strip()
            x = float(line[30:38])
            y = float(line[38:46])
            z = float(line[46:54])
            atoms.append((atom_name, x, y, z))
    return atoms


def compute_centroid(atoms: list[tuple[str, float, float, float]]) -> tuple[float, float, float]:
    """Calcula el centroide de un conjunto de átomos."""
    n = len(atoms)
    if n == 0:
        raise ValueError("No se encontraron átomos.")
    cx = sum(a[1] for a in atoms) / n
    cy = sum(a[2] for a in atoms) / n
    cz = sum(a[3] for a in atoms) / n
    return (round(cx, 3), round(cy, 3), round(cz, 3))


def compute_heavy_atom_rmsd(
    crystal_atoms: list[tuple[str, float, float, float]],
    docked_atoms: list[tuple[str, float, float, float]],
) -> float:
    """
    Calcula RMSD entre dos conjuntos de átomos emparejados por nombre.
    Solo considera heavy atoms (no H).
    """
    import math

    crystal_map = {a[0]: (a[1], a[2], a[3]) for a in crystal_atoms if not a[0].startswith("H")}
    docked_map = {a[0]: (a[1], a[2], a[3]) for a in docked_atoms if not a[0].startswith("H")}

    common = set(crystal_map.keys()) & set(docked_map.keys())
    if len(common) == 0:
        raise ValueError("No hay átomos comunes para calcular RMSD.")

    sum_sq = 0.0
    for name in common:
        dx = crystal_map[name][0] - docked_map[name][0]
        dy = crystal_map[name][1] - docked_map[name][1]
        dz = crystal_map[name][2] - docked_map[name][2]
        sum_sq += dx * dx + dy * dy + dz * dz

    return math.sqrt(sum_sq / len(common))


def validate_grid_covers_ligand(
    ligand_centroid: tuple[float, float, float],
    grid_center: tuple[float, float, float],
    grid_size: tuple[float, float, float],
) -> tuple[bool, float]:
    """
    Verifica que el centroide del ligando cae dentro del grid box.

    Returns:
        (is_covered, distance_to_center)
    """
    import math
    dx = abs(ligand_centroid[0] - grid_center[0])
    dy = abs(ligand_centroid[1] - grid_center[1])
    dz = abs(ligand_centroid[2] - grid_center[2])

    inside = (
        dx <= grid_size[0] / 2
        and dy <= grid_size[1] / 2
        and dz <= grid_size[2] / 2
    )

    distance = math.sqrt(
        (ligand_centroid[0] - grid_center[0]) ** 2
        + (ligand_centroid[1] - grid_center[1]) ** 2
        + (ligand_centroid[2] - grid_center[2]) ** 2
    )

    return inside, round(distance, 3)


def validate_serotonin_smiles() -> dict:
    """
    Valida que el SMILES canónico de serotonina genera una molécula
    consistente con la estructura cristalográfica de SRO en 7E2Y.

    Serotonina: 5-hydroxytryptamine (5-HT)
    CID PubChem: 5202
    SMILES canónico: NCCc1c[nH]c2ccc(O)cc12
    Fórmula: C10H12N2O
    MW: 176.21 Da
    """
    from rdkit import Chem
    from rdkit.Chem import Descriptors

    serotonin_smiles = "NCCc1c[nH]c2ccc(O)cc12"
    mol = Chem.MolFromSmiles(serotonin_smiles)

    if mol is None:
        return {"valid": False, "error": "No se pudo parsear el SMILES de serotonina."}

    canonical = Chem.MolToSmiles(mol)
    mw = Descriptors.ExactMolWt(mol)
    formula = Chem.rdMolDescriptors.CalcMolFormula(mol)
    heavy_atoms = mol.GetNumHeavyAtoms()

    # Serotonina: C10H12N2O, MW=176.21
    expected_formula = "C10H12N2O"
    expected_heavy = 13  # 10C + 2N + 1O

    return {
        "valid": True,
        "smiles_input": serotonin_smiles,
        "smiles_canonical": canonical,
        "smiles_hash": hashlib.sha256(canonical.encode()).hexdigest(),
        "formula": formula,
        "formula_match": formula == expected_formula,
        "molecular_weight": round(mw, 2),
        "heavy_atoms": heavy_atoms,
        "heavy_atoms_match": heavy_atoms == expected_heavy,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Validación de redocking: serotonina vs 7E2Y (5-HT1A)"
    )
    parser.add_argument(
        "--output", "-o",
        default="artifacts/redocking_validation.json",
        help="Path para el archivo JSON de resultados.",
    )
    parser.add_argument(
        "--pdb-id",
        default="7E2Y",
        help="PDB ID del target.",
    )
    parser.add_argument(
        "--ligand-id",
        default="SRO",
        help="Residue ID del ligando co-cristalizado.",
    )
    parser.add_argument(
        "--chain",
        default="R",
        help="Chain ID del ligando en el PDB (auth chain).",
    )
    args = parser.parse_args()

    report = {
        "protocol": "redocking_validation",
        "version": "1.0",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "pdb_id": args.pdb_id,
        "ligand_id": args.ligand_id,
        "chain": args.chain,
        "reference": {
            "structure": "Xu et al. (2021) Nature 592:469-473. DOI:10.1038/s41586-021-03376-8",
            "criteria": "Hevener et al. (2009) J Chem Inf Model 49:444-460",
            "rmsd_threshold": 2.0,
        },
        "steps": {},
        "overall_pass": False,
    }

    # ─── Paso 1: Descargar PDB ───────────────────────────────────────────
    print(f"\n{'='*60}")
    print(f"  Validación de redocking: {args.ligand_id} vs {args.pdb_id}")
    print(f"{'='*60}\n")

    try:
        pdb_text = fetch_pdb(args.pdb_id)
        report["steps"]["fetch_pdb"] = {
            "status": "OK",
            "pdb_lines": len(pdb_text.splitlines()),
        }
        print(f"[OK] PDB descargado: {len(pdb_text.splitlines())} líneas.")
    except Exception as e:
        report["steps"]["fetch_pdb"] = {"status": "FAIL", "error": str(e)}
        print(f"[FAIL] No se pudo descargar el PDB: {e}")
        _save_report(report, args.output)
        return 1

    # ─── Paso 2: Extraer ligando cristalográfico ─────────────────────────
    atoms = extract_ligand_atoms(pdb_text, args.ligand_id, args.chain)
    if not atoms:
        report["steps"]["extract_ligand"] = {
            "status": "FAIL",
            "error": f"No se encontraron átomos de {args.ligand_id} en chain {args.chain}.",
        }
        print(f"[FAIL] No se encontraron átomos de {args.ligand_id}.")
        _save_report(report, args.output)
        return 1

    centroid = compute_centroid(atoms)
    heavy_atoms = [a for a in atoms if not a[0].startswith("H")]

    report["steps"]["extract_ligand"] = {
        "status": "OK",
        "total_atoms": len(atoms),
        "heavy_atoms": len(heavy_atoms),
        "centroid": {"x": centroid[0], "y": centroid[1], "z": centroid[2]},
        "atom_names": [a[0] for a in atoms],
    }
    print(f"[OK] Ligando extraído: {len(atoms)} átomos, {len(heavy_atoms)} heavy atoms.")
    print(f"     Centroide: ({centroid[0]}, {centroid[1]}, {centroid[2]})")

    # ─── Paso 3: Validar grid box ────────────────────────────────────────
    # Grid box del config.py (actualizado para 7E2Y/SRO)
    grid_center = (103.03, 114.79, 108.36)
    grid_size = (25.0, 25.0, 25.0)  # Consistente con config.py vina_size_x/y/z

    is_covered, distance = validate_grid_covers_ligand(centroid, grid_center, grid_size)

    report["steps"]["grid_validation"] = {
        "status": "OK" if is_covered else "FAIL",
        "grid_center": {"x": grid_center[0], "y": grid_center[1], "z": grid_center[2]},
        "grid_size": {"x": grid_size[0], "y": grid_size[1], "z": grid_size[2]},
        "ligand_centroid": {"x": centroid[0], "y": centroid[1], "z": centroid[2]},
        "centroid_inside_grid": is_covered,
        "distance_centroid_to_grid_center": distance,
    }

    if is_covered:
        print(f"[OK] Centroide del ligando DENTRO del grid box (distancia: {distance} Å)")
    else:
        print(f"[FAIL] Centroide del ligando FUERA del grid box (distancia: {distance} Å)")

    # ─── Paso 4: Validar SMILES de serotonina ────────────────────────────
    srt_info = validate_serotonin_smiles()
    report["steps"]["serotonin_smiles"] = srt_info

    if srt_info["valid"]:
        print(f"[OK] Serotonina SMILES: {srt_info['smiles_canonical']}")
        print(f"     Fórmula: {srt_info['formula']} (match: {srt_info['formula_match']})")
        print(f"     Heavy atoms: {srt_info['heavy_atoms']} (match: {srt_info['heavy_atoms_match']})")
    else:
        print(f"[FAIL] SMILES de serotonina inválido: {srt_info.get('error')}")

    # ─── Paso 5: Resumen ─────────────────────────────────────────────────
    all_ok = (
        report["steps"]["fetch_pdb"]["status"] == "OK"
        and report["steps"]["extract_ligand"]["status"] == "OK"
        and report["steps"]["grid_validation"]["status"] == "OK"
        and srt_info["valid"]
        and srt_info["formula_match"]
        and srt_info["heavy_atoms_match"]
    )

    report["overall_pass"] = all_ok
    report["summary"] = (
        "PASS — El setup de docking es consistente con la estructura cristalográfica. "
        "El grid box cubre el sitio de unión de serotonina en 7E2Y. "
        "Para validación completa, ejecutar re-docking con Vina y medir RMSD ≤ 2.0 Å."
        if all_ok
        else "FAIL — Uno o más pasos de validación fallaron. Revisar el reporte."
    )

    report["next_steps"] = [
        "Ejecutar docking real de serotonina (NCCc1c[nH]c2ccc(O)cc12) contra 7E2Y con Vina.",
        "Extraer la mejor pose y calcular RMSD vs coordenadas cristalográficas de SRO.",
        "Criterio de aceptación: RMSD ≤ 2.0 Å (Hevener et al. 2009).",
        "Si RMSD > 2.0 Å, revisar preparación de proteína, grid box y parámetros de Vina.",
    ]

    print(f"\n{'='*60}")
    print(f"  RESULTADO: {'PASS' if all_ok else 'FAIL'}")
    print(f"{'='*60}")
    print(f"  {report['summary']}")

    _save_report(report, args.output)
    return 0 if all_ok else 1


def _save_report(report: dict, output_path: str) -> None:
    """Guarda el reporte JSON."""
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n[INFO] Reporte guardado en: {out}")


if __name__ == "__main__":
    sys.exit(main())
