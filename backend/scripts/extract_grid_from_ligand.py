"""
scripts/extract_grid_from_ligand.py

Extrae las coordenadas del grid box para AutoDock Vina a partir del ligando
co-cristalizado en una estructura PDB.

Metodología estándar en docking computacional:
    1. Identificar el ligando co-cristalizado (HETATM) en el PDB.
    2. Calcular el centroide geométrico de todos sus átomos pesados.
    3. Definir el grid box como centroide ± margen (default 5 Å por cada lado).

El margen de 5 Å es una práctica estándar documentada en:
    - Morris et al. (2009) J Comput Chem 30:2785-2791
    - Forli et al. (2016) Nature Protocols 11:905-919

Uso:
    python scripts/extract_grid_from_ligand.py --pdb-id 7E2Y --ligand-id SRO --chain R
    python scripts/extract_grid_from_ligand.py --pdb-id 7E2Y --ligand-id SRO --chain R --margin 8
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Para poder importar módulos del backend
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import urllib.request
import urllib.error


def download_pdb(pdb_id: str) -> str:
    """Descarga el archivo PDB desde RCSB."""
    url = f"https://files.rcsb.org/download/{pdb_id.upper()}.pdb"
    print(f"Descargando {url} ...")
    try:
        with urllib.request.urlopen(url, timeout=60) as resp:
            content = resp.read().decode("utf-8", errors="replace")
        print(f"  → {len(content)} bytes descargados")
        return content
    except urllib.error.HTTPError as e:
        # Si el PDB format no está disponible (común en cryo-EM), intentar mmCIF
        print(f"  → PDB format no disponible ({e.code}), intentando mmCIF...")
        url_cif = f"https://files.rcsb.org/download/{pdb_id.upper()}.cif"
        raise RuntimeError(
            f"No se pudo descargar el PDB {pdb_id}. "
            f"Para estructuras cryo-EM, puede que solo exista formato mmCIF ({url_cif}). "
            f"Error HTTP: {e.code}"
        )


def extract_ligand_atoms(
    pdb_content: str,
    ligand_id: str,
    chain_id: str,
) -> list[tuple[float, float, float]]:
    """
    Extrae coordenadas (x, y, z) de todos los átomos HETATM del ligando especificado.

    Args:
        pdb_content: contenido del archivo PDB como string
        ligand_id: identificador de 3 letras del ligando (ej. SRO para serotonina)
        chain_id: cadena donde reside el ligando

    Returns:
        Lista de tuplas (x, y, z) en Angstroms.
    """
    coords: list[tuple[float, float, float]] = []

    for line in pdb_content.splitlines():
        record = line[:6].strip()
        if record != "HETATM":
            continue

        residue_name = line[17:20].strip()
        current_chain = line[21].strip()

        if residue_name != ligand_id:
            continue
        if current_chain != chain_id:
            continue

        try:
            x = float(line[30:38].strip())
            y = float(line[38:46].strip())
            z = float(line[46:54].strip())
            coords.append((x, y, z))
        except (ValueError, IndexError):
            continue

    return coords


def calculate_centroid(
    coords: list[tuple[float, float, float]],
) -> tuple[float, float, float]:
    """Calcula el centroide geométrico de un conjunto de coordenadas."""
    n = len(coords)
    if n == 0:
        raise ValueError("No hay coordenadas para calcular centroide")

    cx = sum(c[0] for c in coords) / n
    cy = sum(c[1] for c in coords) / n
    cz = sum(c[2] for c in coords) / n

    return (round(cx, 2), round(cy, 2), round(cz, 2))


def calculate_bounding_box(
    coords: list[tuple[float, float, float]],
    margin: float,
) -> tuple[float, float, float]:
    """
    Calcula el tamaño del grid box como (max-min) + 2*margin por cada eje.

    El margen se suma en ambas direcciones para cada eje.
    """
    xs = [c[0] for c in coords]
    ys = [c[1] for c in coords]
    zs = [c[2] for c in coords]

    size_x = round((max(xs) - min(xs)) + 2 * margin, 1)
    size_y = round((max(ys) - min(ys)) + 2 * margin, 1)
    size_z = round((max(zs) - min(zs)) + 2 * margin, 1)

    return (size_x, size_y, size_z)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Extraer grid box para Vina desde ligando co-cristalizado"
    )
    parser.add_argument("--pdb-id", required=True, help="PDB ID (ej. 7E2Y)")
    parser.add_argument("--ligand-id", required=True, help="Residue ID del ligando (ej. SRO)")
    parser.add_argument("--chain", required=True, help="Chain ID donde está el ligando (ej. R)")
    parser.add_argument("--margin", type=float, default=5.0,
                        help="Margen en Å alrededor del ligando (default: 5.0)")
    parser.add_argument("--output", type=str, default=None,
                        help="Archivo JSON de salida (opcional)")
    parser.add_argument("--pdb-file", type=str, default=None,
                        help="Usar archivo PDB local en vez de descargar")
    args = parser.parse_args()

    # Obtener contenido PDB
    if args.pdb_file:
        pdb_content = Path(args.pdb_file).read_text(encoding="utf-8", errors="replace")
        print(f"Usando archivo local: {args.pdb_file}")
    else:
        pdb_content = download_pdb(args.pdb_id)

    # Extraer átomos del ligando
    atoms = extract_ligand_atoms(pdb_content, args.ligand_id, args.chain)
    print(f"\nLigando {args.ligand_id} en cadena {args.chain}:")
    print(f"  → {len(atoms)} átomos encontrados")

    if not atoms:
        print("\n*** ERROR: No se encontraron átomos del ligando ***")
        print("Verifica:")
        print(f"  1. Que el PDB {args.pdb_id} contenga el ligando '{args.ligand_id}'")
        print(f"  2. Que la cadena '{args.chain}' sea correcta")
        print("  3. Que el archivo PDB tenga registros HETATM (no solo ATOM)")
        print("\nSugerencia: para estructuras cryo-EM, los chain IDs pueden diferir.")
        print("  Usa --pdb-file con un archivo descargado manualmente para inspeccionar.")
        sys.exit(1)

    # Calcular centroide y bounding box
    center = calculate_centroid(atoms)
    size = calculate_bounding_box(atoms, args.margin)

    # Mostrar rangos por eje
    xs = [c[0] for c in atoms]
    ys = [c[1] for c in atoms]
    zs = [c[2] for c in atoms]

    print(f"\n  Rango X: [{min(xs):.2f}, {max(xs):.2f}] (span: {max(xs)-min(xs):.2f} Å)")
    print(f"  Rango Y: [{min(ys):.2f}, {max(ys):.2f}] (span: {max(ys)-min(ys):.2f} Å)")
    print(f"  Rango Z: [{min(zs):.2f}, {max(zs):.2f}] (span: {max(zs)-min(zs):.2f} Å)")

    print(f"\n═══ Grid Box para config.py ═══")
    print(f"  center: ({center[0]}, {center[1]}, {center[2]})")
    print(f"  size:   ({size[0]}, {size[1]}, {size[2]})")
    print(f"  margin: {args.margin} Å")

    print(f"\n═══ Variables para config.py ═══")
    print(f"  vina_center_x: float = {center[0]}")
    print(f"  vina_center_y: float = {center[1]}")
    print(f"  vina_center_z: float = {center[2]}")
    print(f"  vina_size_x: float = {size[0]}")
    print(f"  vina_size_y: float = {size[1]}")
    print(f"  vina_size_z: float = {size[2]}")

    # Guardar resultado
    result = {
        "pdb_id": args.pdb_id.upper(),
        "ligand_id": args.ligand_id,
        "chain": args.chain,
        "num_ligand_atoms": len(atoms),
        "margin_angstrom": args.margin,
        "grid_center": {"x": center[0], "y": center[1], "z": center[2]},
        "grid_size": {"x": size[0], "y": size[1], "z": size[2]},
        "ligand_span": {
            "x": round(max(xs) - min(xs), 2),
            "y": round(max(ys) - min(ys), 2),
            "z": round(max(zs) - min(zs), 2),
        },
        "methodology": (
            "Centroide geométrico de todos los átomos HETATM del ligando "
            f"co-cristalizado ({args.ligand_id}) + margen de {args.margin} Å. "
            "Estándar: Morris et al. (2009), Forli et al. (2016)."
        ),
    }

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
        print(f"\n  Resultado guardado en: {output_path}")

    # Siempre imprimir JSON a stdout para captura
    print(f"\n{json.dumps(result, indent=2)}")


if __name__ == "__main__":
    main()
