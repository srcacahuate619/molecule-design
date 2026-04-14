"""
rescoring/scripts/redock_pdbbind.py

Re-dock PDBbind crystal ligands with AutoDock Vina to populate Group B features.

═══════════════════════════════════════════════════════════════════════════
PROBLEMA: En training, Group B features (vina_best_score, pose_score_variance,
pose_score_range, poses_passing_ratio) son siempre 0 porque usamos las poses
cristalográficas de PDBbind, no poses de docking.  En producción, estas
features vienen del docking real.  Esto crea un train/inference mismatch
que hace que el modelo ignore Group B completamente.

SOLUCIÓN: Re-dockear los ligandos cristalográficos contra sus propias
proteínas con Vina, usando el mismo protocolo que en producción.

NOTA: Este proceso es computacionalmente costoso.
  ~5 min/complejo × 3,019 complejos = ~250 horas en 1 core
  Con 6 cores: ~42 horas
  Recomendación: ejecutar en background o en servidor dedicado.

RESULTADO: Los features de Vina se guardan en el cache de features,
permitiendo que el modelo aprenda de la correlación entre score Vina,
varianza de poses, y afinidad experimental.
═══════════════════════════════════════════════════════════════════════════

Uso:
  python scripts/redock_pdbbind.py --data-dir PATH --vina-path PATH [--max-workers N]
"""

from __future__ import annotations

import argparse
import json
import subprocess
import tempfile
import time
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, as_completed

import numpy as np


def prepare_ligand_pdbqt(sdf_path: str, output_path: str) -> bool:
    """
    Convert SDF ligand to PDBQT for Vina input.

    Uses Open Babel (obabel) for conversion.
    Falls back to RDKit if obabel not available.
    """
    try:
        result = subprocess.run(
            ["obabel", sdf_path, "-O", output_path, "-h"],
            capture_output=True, text=True, timeout=30,
        )
        return result.returncode == 0 and Path(output_path).exists()
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def prepare_receptor_pdbqt(pdb_path: str, output_path: str) -> bool:
    """
    Prepare receptor PDBQT from PDB.

    Uses prepare_receptor from ADFR suite or obabel.
    """
    try:
        result = subprocess.run(
            ["obabel", pdb_path, "-O", output_path, "-xr"],
            capture_output=True, text=True, timeout=60,
        )
        return result.returncode == 0 and Path(output_path).exists()
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def find_binding_center(sdf_path: str) -> tuple[float, float, float] | None:
    """
    Calculate binding site center from crystal ligand coordinates.
    This is the centroid of the ligand heavy atoms.
    """
    from rdkit import Chem

    supplier = Chem.SDMolSupplier(sdf_path, removeHs=True)
    try:
        mol = next(supplier)
    except StopIteration:
        return None

    if mol is None:
        return None

    conf = mol.GetConformer()
    coords = np.array([
        conf.GetAtomPosition(i)
        for i in range(mol.GetNumAtoms())
    ])

    if len(coords) == 0:
        return None

    center = coords.mean(axis=0)
    return (float(center[0]), float(center[1]), float(center[2]))


def run_vina_redocking(
    pdb_id: str,
    protein_pdb: str,
    ligand_sdf: str,
    vina_path: str,
    work_dir: str,
) -> dict[str, float] | None:
    """
    Run Vina re-docking for a single PDBbind complex.

    Returns dict with Group B features, or None on failure.
    """
    work = Path(work_dir)
    work.mkdir(parents=True, exist_ok=True)

    lig_pdbqt = str(work / f"{pdb_id}_lig.pdbqt")
    rec_pdbqt = str(work / f"{pdb_id}_rec.pdbqt")

    # Prepare receptor
    if not prepare_receptor_pdbqt(protein_pdb, rec_pdbqt):
        return None

    # Prepare ligand
    if not prepare_ligand_pdbqt(ligand_sdf, lig_pdbqt):
        return None

    # Find binding center from crystal ligand
    center = find_binding_center(ligand_sdf)
    if center is None:
        return None

    cx, cy, cz = center

    # Run Vina
    out_pdbqt = str(work / f"{pdb_id}_out.pdbqt")
    cmd = [
        vina_path,
        "--receptor", rec_pdbqt,
        "--ligand", lig_pdbqt,
        "--center_x", str(cx),
        "--center_y", str(cy),
        "--center_z", str(cz),
        "--size_x", "25",
        "--size_y", "25",
        "--size_z", "25",
        "--exhaustiveness", "8",
        "--num_modes", "9",
        "--out", out_pdbqt,
    ]

    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=300,
        )
        if result.returncode != 0:
            return None
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return None

    # Parse scores from output
    scores = []
    for line in result.stdout.split("\n"):
        parts = line.strip().split()
        if len(parts) >= 4 and parts[0].isdigit():
            try:
                scores.append(float(parts[1]))
            except ValueError:
                continue

    if not scores:
        return None

    return {
        "vina_best_score": scores[0],
        "pose_score_variance": float(np.var(scores)) if len(scores) > 1 else 0.0,
        "pose_score_range": scores[-1] - scores[0] if len(scores) > 1 else 0.0,
        "poses_passing_ratio": sum(1 for s in scores if s < -5.0) / len(scores),
    }


def main():
    parser = argparse.ArgumentParser(
        description="Re-dock PDBbind crystals with Vina for Group B features"
    )
    parser.add_argument("--data-dir", required=True, help="PDBbind data directory")
    parser.add_argument("--vina-path", default="vina", help="Path to Vina executable")
    parser.add_argument("--max-workers", type=int, default=4)
    parser.add_argument("--output", default=None, help="Output JSON with results")
    args = parser.parse_args()

    data_dir = Path(args.data_dir)
    cache_dir = data_dir / "vina_redock_cache"
    cache_dir.mkdir(exist_ok=True)

    work_dir = data_dir / "vina_redock_work"
    work_dir.mkdir(exist_ok=True)

    # Find complexes
    complexes = []
    for d in sorted(data_dir.iterdir()):
        if not d.is_dir():
            continue
        pdb = d / f"{d.name}_protein.pdb"
        sdf = d / f"{d.name}_ligand.sdf"
        if pdb.exists() and sdf.exists():
            cache_file = cache_dir / f"{d.name}.json"
            if not cache_file.exists():
                complexes.append((d.name, str(pdb), str(sdf)))

    print(f"Found {len(complexes)} complexes to re-dock")
    print(f"Estimated time: {len(complexes) * 5 / args.max_workers / 60:.1f} hours")
    print(f"Results will be cached in: {cache_dir}")

    n_success = 0
    n_failed = 0
    t0 = time.time()

    with ProcessPoolExecutor(max_workers=args.max_workers) as executor:
        futures = {
            executor.submit(
                run_vina_redocking,
                pdb_id, prot, sdf, args.vina_path,
                str(work_dir / pdb_id),
            ): pdb_id
            for pdb_id, prot, sdf in complexes
        }

        for future in as_completed(futures):
            pdb_id = futures[future]
            try:
                result = future.result(timeout=600)
                if result is not None:
                    cache_file = cache_dir / f"{pdb_id}.json"
                    cache_file.write_text(json.dumps(result))
                    n_success += 1
                else:
                    n_failed += 1
            except Exception:
                n_failed += 1

            total = n_success + n_failed
            if total % 50 == 0 or total <= 5:
                elapsed = time.time() - t0
                rate = total / elapsed if elapsed > 0 else 0
                eta = (len(complexes) - total) / rate / 3600 if rate > 0 else 0
                print(
                    f"[{total}/{len(complexes)}] "
                    f"success={n_success} failed={n_failed} "
                    f"ETA={eta:.1f}h"
                )

    print(f"\nDone: {n_success} success, {n_failed} failed")
    print(f"Total time: {(time.time() - t0) / 3600:.1f} hours")


if __name__ == "__main__":
    main()
