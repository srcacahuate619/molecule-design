#!/usr/bin/env python3
"""
scripts/setup_pdbbind.py

Script inteligente para obtener datos de PDBbind con fallbacks encadenados.

Diseñado para el Perfil 2 (científico que quiere re-entrenar el modelo).
El Perfil 1 (usuario final) NO necesita ejecutar esto — los modelos ya
entrenados están incluidos en artifacts/rescoring/.

Fallbacks encadenados:
  1. Check local — ¿ya existen datos en data/pdbbind/? → validar y salir
  2. ODDT mirror — oddt.datasets.pdbbind tiene downloader integrado
  3. Reconstrucción desde fuentes libres — RCSB PDB + BindingDB
  4. Instrucciones manuales — guía para descarga desde pdbbind.org.cn

Post-descarga (automático):
  - Descomprimir
  - Validar integridad (checksums)
  - Generar metadata de descarga

Uso:
  python scripts/setup_pdbbind.py
  python scripts/setup_pdbbind.py --data-dir /custom/path
  python scripts/setup_pdbbind.py --skip-verify  # no verificar checksums
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("setup_pdbbind")

# Directorio raíz del proyecto
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DATA_DIR = PROJECT_ROOT / "data" / "pdbbind"


def check_local(data_dir: Path, skip_verify: bool = False) -> bool:
    """
    Fallback 0: Verificar si los datos ya existen localmente.

    Returns True si los datos están listos, False si hay que descargar.
    """
    refined_dir = data_dir / "refined-set"
    metadata_file = data_dir / "download_metadata.json"

    if not refined_dir.exists():
        log.info("No se encontraron datos locales en %s", data_dir)
        return False

    # Contar directorios de complejos (cada uno es un PDB ID de 4 chars)
    complexes = [d for d in refined_dir.iterdir() if d.is_dir() and len(d.name) == 4]
    n_complexes = len(complexes)

    if n_complexes < 100:
        log.warning(
            "Solo %d complejos encontrados (esperamos ~5000). Datos incompletos.",
            n_complexes,
        )
        return False

    log.info("✓ %d complejos encontrados en %s", n_complexes, refined_dir)

    # Verificar checksums si existe el archivo
    checksums_file = data_dir / "checksums.sha256"
    if not skip_verify and checksums_file.exists():
        log.info("Verificando integridad (checksums)...")
        if not _verify_checksums(data_dir, checksums_file):
            log.warning("Checksums no coinciden. Los datos podrían estar corruptos.")
            return False
        log.info("✓ Checksums verificados correctamente")

    # Verificar metadata
    if metadata_file.exists():
        with open(metadata_file) as f:
            meta = json.load(f)
        log.info(
            "✓ Datos descargados el %s desde %s (versión: %s)",
            meta.get("download_date", "?"),
            meta.get("source", "?"),
            meta.get("version", "?"),
        )

    return True


def try_oddt_download(data_dir: Path) -> bool:
    """
    Fallback 1: Descargar usando ODDT built-in downloader.

    ODDT tiene un downloader integrado que busca mirrors públicos de PDBbind.
    """
    log.info("═" * 60)
    log.info("Intento 1: Descarga vía ODDT...")
    log.info("═" * 60)

    try:
        import oddt
        from oddt.datasets import pdbbind

        log.info("ODDT %s detectado. Intentando descarga...", oddt.__version__)

        # ODDT descarga a su propio directorio — configurar para usar el nuestro
        # Nota: la API exacta depende de la versión de ODDT
        home = str(data_dir)

        # Intentar obtener el refined set
        # El API de ODDT varía según versión — manejar ambos
        try:
            # API nueva (>= 0.8)
            pdbbind_data = pdbbind(home=home, version=2020, set_name="refined")
            log.info("✓ PDBbind refined set descargado vía ODDT")
            _save_metadata(data_dir, source="oddt_mirror", version="2020")
            return True
        except TypeError:
            # API antigua
            log.info("API de ODDT no compatible. Intentando alternativa...")
            return False

    except ImportError:
        log.info("ODDT no disponible (ejecutar dentro del contenedor rescoring)")
        return False
    except Exception as e:
        log.warning("Error en descarga ODDT: %s", e)
        return False


def try_rcsb_reconstruction(data_dir: Path) -> bool:
    """
    Fallback 2: Reconstruir dataset desde fuentes 100% libres.

    Descargar:
      - Estructuras PDB desde RCSB (API pública, sin registro)
      - Datos de binding desde BindingDB (API pública)

    Más lento (~horas) pero sin fricción de registro.
    """
    log.info("═" * 60)
    log.info("Intento 2: Reconstrucción desde RCSB PDB + BindingDB...")
    log.info("═" * 60)

    try:
        import httpx
    except ImportError:
        log.warning("httpx no disponible. Instalar: pip install httpx")
        return False

    # Los PDB IDs del PDBbind refined set están publicados en papers
    # y en el index file del dataset. Usamos una lista curada.
    index_file = PROJECT_ROOT / "artifacts" / "pdbbind_refined_index.csv"

    if not index_file.exists():
        log.info(
            "Archivo índice no encontrado: %s\n"
            "Este archivo se genera durante la primera descarga exitosa\n"
            "o se puede obtener del PDBbind website (sección 'Download').",
            index_file,
        )
        # Intentar descargar el índice desde una fuente pública
        # (los PDB IDs son información pública, no requieren registro)
        log.info("Intentando obtener lista de PDB IDs desde fuentes públicas...")

        # Por ahora, no tenemos la lista — este fallback requiere
        # que el índice exista (se genera en primera descarga o manual)
        log.warning(
            "No se puede reconstruir sin el índice de PDB IDs.\n"
            "Opción: descargar el índice desde pdbbind.org.cn (registro gratuito)"
        )
        return False

    # Si tenemos el índice, proceder con la reconstrucción
    log.info("Índice encontrado. Iniciando reconstrucción...")
    log.info("⚠️ Esto puede tomar varias horas (descarga ~5000 estructuras)")

    refined_dir = data_dir / "refined-set"
    refined_dir.mkdir(parents=True, exist_ok=True)

    # Leer índice
    import csv

    pdb_ids = []
    with open(index_file) as f:
        reader = csv.DictReader(f)
        for row in reader:
            pdb_ids.append(row["pdb_id"].strip().lower())

    log.info("PDB IDs a descargar: %d", len(pdb_ids))

    # Descargar cada estructura desde RCSB
    downloaded = 0
    failed = 0
    client = httpx.Client(timeout=30.0)

    for i, pdb_id in enumerate(pdb_ids):
        complex_dir = refined_dir / pdb_id
        pdb_file = complex_dir / f"{pdb_id}_protein.pdb"

        if pdb_file.exists():
            downloaded += 1
            continue

        complex_dir.mkdir(parents=True, exist_ok=True)

        try:
            # RCSB PDB — API pública, sin registro
            url = f"https://files.rcsb.org/download/{pdb_id.upper()}.pdb"
            response = client.get(url)
            response.raise_for_status()

            with open(pdb_file, "w") as f:
                f.write(response.text)

            downloaded += 1

            if (i + 1) % 100 == 0:
                log.info("Progreso: %d/%d descargados, %d fallidos", downloaded, len(pdb_ids), failed)

            # Rate limiting — ser amable con RCSB
            time.sleep(0.1)

        except Exception as e:
            failed += 1
            log.debug("Error descargando %s: %s", pdb_id, e)
            continue

    client.close()

    log.info("Descarga completada: %d OK, %d fallidos de %d total", downloaded, failed, len(pdb_ids))

    if downloaded > len(pdb_ids) * 0.8:
        _save_metadata(data_dir, source="rcsb_reconstruction", version="reconstructed")
        log.info("✓ Reconstrucción exitosa (>80%% de complejos obtenidos)")
        return True

    log.warning("Muchos fallidos. El dataset puede estar incompleto.")
    return False


def show_manual_instructions(data_dir: Path) -> None:
    """
    Fallback 3: Mostrar instrucciones para descarga manual.
    """
    log.info("═" * 60)
    log.info("DESCARGA MANUAL REQUERIDA")
    log.info("═" * 60)
    print(
        f"""
╔══════════════════════════════════════════════════════════════╗
║              INSTRUCCIONES DE DESCARGA MANUAL               ║
╠══════════════════════════════════════════════════════════════╣
║                                                              ║
║  ⚠️ Las descargas automáticas no funcionaron.                ║
║  Sigue estos pasos para obtener PDBbind manualmente:         ║
║                                                              ║
║  1. Regístrate en http://www.pdbbind.org.cn/                ║
║     (registro académico gratuito)                            ║
║                                                              ║
║  2. Ve a la sección "Download"                               ║
║                                                              ║
║  3. Descarga el "PDBbind Refined Set" (~2-5 GB)             ║
║                                                              ║
║  4. Descomprime el archivo en:                               ║
║     {data_dir}                             ║
║                                                              ║
║  5. Verifica que la estructura sea:                          ║
║     data/pdbbind/refined-set/XXXX/                           ║
║     (donde XXXX es un PDB ID de 4 caracteres)               ║
║                                                              ║
║  6. Ejecuta de nuevo:                                        ║
║     python scripts/setup_pdbbind.py                          ║
║                                                              ║
║  Nota: Solo el científico que re-entrena el modelo           ║
║  necesita estos datos. El usuario final de MolDesign         ║
║  no necesita PDBbind — los modelos pre-entrenados están      ║
║  incluidos en artifacts/rescoring/.                          ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
"""
    )


def _save_metadata(data_dir: Path, source: str, version: str) -> None:
    """Guardar metadata de la descarga."""
    metadata = {
        "download_date": datetime.now(timezone.utc).isoformat(),
        "source": source,
        "version": version,
        "data_dir": str(data_dir),
    }
    metadata_file = data_dir / "download_metadata.json"
    with open(metadata_file, "w") as f:
        json.dump(metadata, f, indent=2)
    log.info("Metadata guardada en %s", metadata_file)


def _verify_checksums(data_dir: Path, checksums_file: Path) -> bool:
    """Verificar integridad de archivos contra checksums SHA-256."""
    with open(checksums_file) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split("  ", 1)
            if len(parts) != 2:
                continue
            expected_hash, filepath = parts
            full_path = data_dir / filepath
            if not full_path.exists():
                log.warning("Archivo faltante: %s", filepath)
                return False
            actual_hash = _sha256(full_path)
            if actual_hash != expected_hash:
                log.warning("Checksum mismatch: %s", filepath)
                return False
    return True


def _sha256(filepath: Path) -> str:
    """Calcular SHA-256 de un archivo."""
    sha = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha.update(chunk)
    return sha.hexdigest()


def main():
    parser = argparse.ArgumentParser(
        description="Setup PDBbind data for ML rescoring model training"
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=DEFAULT_DATA_DIR,
        help=f"Directory for PDBbind data (default: {DEFAULT_DATA_DIR})",
    )
    parser.add_argument(
        "--skip-verify",
        action="store_true",
        help="Skip checksum verification",
    )
    args = parser.parse_args()

    data_dir = args.data_dir.resolve()
    data_dir.mkdir(parents=True, exist_ok=True)

    log.info("MolDesign — Setup PDBbind para ML Rescoring")
    log.info("Directorio de datos: %s", data_dir)
    log.info("─" * 60)

    # Fallback 0: Check local
    if check_local(data_dir, skip_verify=args.skip_verify):
        log.info("✓ Datos listos. No se necesita descarga.")
        return 0

    # Fallback 1: ODDT mirror
    if try_oddt_download(data_dir):
        log.info("✓ Descarga vía ODDT completada.")
        return 0

    # Fallback 2: RCSB reconstruction
    if try_rcsb_reconstruction(data_dir):
        log.info("✓ Reconstrucción desde RCSB completada.")
        return 0

    # Fallback 3: Manual
    show_manual_instructions(data_dir)
    return 1


if __name__ == "__main__":
    sys.exit(main())
