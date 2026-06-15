"""
services/docking/preparer.py

Preparación del receptor para AutoDock Vina usando una estrategia explícita:

1. Descargar PDB raw del RCSB si no existe en MinIO.
2. Filtrar la cadena objetivo y eliminar aguas evidentes.
3. Ejecutar preparación real a PDBQT mediante Meeko si está disponible.

Importante:
Este módulo NO simula preparación química. Si la herramienta necesaria no está
disponible, falla con un error explícito para no introducir falsa ciencia.
"""

from __future__ import annotations

import asyncio
import shutil
import sys
import tempfile
from pathlib import Path

from core.config import get_settings
from core.exceptions import ProteinPreparationError
from utils.file_handlers import (
    StoragePath,
    download_text,
    download_pdb_from_rcsb,
    object_exists,
    temp_file_from_minio,
    upload_file_from_path,
    upload_text,
    validate_pdbqt_content,
)
from utils.logger import get_logger

settings = get_settings()
log = get_logger(__name__)

_WATER_RESIDUES = {"HOH", "WAT", "DOD"}

# Residuos HETATM que NUNCA deben incluirse en el receptor.
# Incluye aguas, ligandos comunes co-cristalizados, lípidos y detergentes.
# Si un HETATM no está en esta lista pero tampoco es un aminoácido estándar,
# se excluye igualmente (ver _filter_pdb_content).
_STANDARD_RESIDUES = {
    "ALA", "ARG", "ASN", "ASP", "CYS", "GLN", "GLU", "GLY", "HIS", "ILE",
    "LEU", "LYS", "MET", "PHE", "PRO", "SER", "THR", "TRP", "TYR", "VAL",
    # Variantes comunes de protonación / modificación que Meeko maneja
    "HID", "HIE", "HIP", "CYX", "ASH", "GLH",
    # Residuos modificados frecuentes en cryo-EM
    "MSE",  # selenometionina → tratada como MET
    "SEP", "TPO", "PTR",  # fosfo-residuos
}


def _resolve_executable(path_or_name: str) -> str | None:
    candidate = Path(path_or_name)
    if candidate.exists():
        return str(candidate)

    found = shutil.which(path_or_name)
    if found:
        return found

    scripts_dir = Path(sys.executable).resolve().parent
    
    # Try scripts_dir / path_or_name directly (e.g. for files with extensions in the bin/scripts folder)
    direct_candidate = scripts_dir / path_or_name
    if direct_candidate.exists():
        return str(direct_candidate)

    windows_candidate = scripts_dir / f"{path_or_name}.exe"
    if windows_candidate.exists():
        return str(windows_candidate)

    py_candidate = scripts_dir / f"{path_or_name}.py"
    if py_candidate.exists():
        return str(py_candidate)

    return None


def _filter_pdb_content(
    pdb_content: str,
    chain_id: str,
    keep_hetatm: bool = False,
    cofactors_whitelist: list[str] | None = None,
) -> str:
    """
    Filtra la cadena de interés para preparación del receptor.

    Estrategia de filtrado (ortodoxo para docking molecular):
    1. Solo conserva la cadena especificada (auth chain ID, columna 22 del PDB).
    2. Elimina aguas (HOH, WAT, DOD).
    3. Por defecto, elimina TODOS los registros HETATM — ligandos co-cristalizados,
       colesterol, detergentes, iones, etc. NO deben estar en el receptor.
    4. Solo conserva ATOM records (aminoácidos estándar de la proteína).

    Si keep_hetatm=True, conserva HETATM que sean residuos estándar modificados
    (MSE, SEP, TPO, PTR) que Meeko sabe reconvertir. Esto es útil para
    proteínas con selenometioninas de cristalografía.

    Justificación científica:
    - En docking rígido contra un GPCR, el receptor debe contener SOLO la proteína.
    - Incluir ligandos co-cristalizados (ej. serotonina en 7E2Y) contamina el
      binding site y produce afinidades artificiales.
    - Incluir colesterol/lípidos de la membrana crea una envolvente no fisiológica.
    - Meeko (mk_prepare_receptor) añade hidrógenos polares y cargas Gasteiger
      solo a residuos proteicos reconocidos.

    Referencia: Morris et al. (2009) J Comput Chem 30:2785-2791.
    """
    filtered_lines: list[str] = []
    excluded_hetatm: dict[str, int] = {}  # residue_name → count (para logging)

    for line in pdb_content.splitlines():
        record = line[:6].strip()
        if record not in {"ATOM", "HETATM", "TER", "END", "MODEL", "ENDMDL"}:
            continue

        if record in {"TER", "END", "MODEL", "ENDMDL"}:
            filtered_lines.append(line)
            continue

        residue_name = line[17:20].strip()
        current_chain = line[21].strip() or "A"

        residue_seq_raw = line[22:26].strip()
        try:
            residue_seq = int(residue_seq_raw)
        except ValueError:
            residue_seq = 0

        # --- Filtros básicos ---
        if residue_name in _WATER_RESIDUES:
            continue
        if current_chain != chain_id:
            continue
        if residue_seq <= 0:
            continue

        # --- Filtro de HETATM: eliminar ligandos, lípidos, retener cofactores ---
        if record == "HETATM":
            if keep_hetatm and residue_name in _STANDARD_RESIDUES:
                # Residuo modificado reconocible (MSE, SEP, etc.) → conservar
                filtered_lines.append(line)
            elif cofactors_whitelist and residue_name in cofactors_whitelist:
                # Cofactor orgánico o metal específico del receptor → conservar
                filtered_lines.append(line)
            else:
                # Ligando, colesterol, solvente genérico, etc. → excluir
                excluded_hetatm[residue_name] = excluded_hetatm.get(residue_name, 0) + 1
            continue

        # ATOM records (aminoácidos estándar) → siempre conservar
        filtered_lines.append(line)

    # Logging de lo que se excluyó para trazabilidad
    if excluded_hetatm:
        log.info(
            "HETATM excluidos de la preparación del receptor",
            chain=chain_id,
            excluded=excluded_hetatm,
            total_excluded=sum(excluded_hetatm.values()),
        )

    atom_count = sum(1 for l in filtered_lines if l.startswith("ATOM"))
    if atom_count == 0:
        raise ProteinPreparationError(
            pdb_id="unknown",
            step="chain_filtering",
            detail=(
                f"No quedaron átomos ATOM tras filtrar la cadena '{chain_id}' "
                f"(HETATM excluidos: {excluded_hetatm or 'ninguno'}). "
                "Verifica el chain ID objetivo."
            ),
        )

    log.info(
        "PDB filtrado para preparación",
        chain=chain_id,
        atom_records=atom_count,
        hetatm_excluded=sum(excluded_hetatm.values()),
    )

    return "\n".join(filtered_lines) + "\n"


async def prepare_target(
    pdb_id: str,
    chain_id: str,
    center: tuple[float, float, float],
    size: tuple[float, float, float],
    force_reprepare: bool = False,
    cofactors_whitelist: list[str] | None = None,
) -> str:
    """
    Prepara un receptor para Vina y lo guarda en MinIO.

    Retorna la ruta del archivo `.pdbqt` en MinIO.
    """
    pdb_id = pdb_id.upper()
    prepared_path = StoragePath.target_prepared(pdb_id)
    raw_path = StoragePath.target_raw(pdb_id)

    # --- [NUEVO] Asegurar PDB en volumen compartido para Rescoring ---
    shared_pdb_path = Path("/data/targets") / f"{pdb_id}.pdb"
    if not shared_pdb_path.exists():
        log.info("asegurando_pdb_para_rescoring", pdb_id=pdb_id)
        if not await object_exists(raw_path):
            pdb_content = await download_pdb_from_rcsb(pdb_id)
            await upload_text(pdb_content, raw_path)
        
        # Descargar y filtrar para el volumen compartido
        pdb_content = await download_text(raw_path)
        filtered_content = _filter_pdb_content(
            pdb_content, 
            chain_id=chain_id, 
            keep_hetatm=True,
            cofactors_whitelist=cofactors_whitelist
        )
        
        # Guardar en volumen compartido
        shared_pdb_path.parent.mkdir(parents=True, exist_ok=True)
        shared_pdb_path.write_text(filtered_content, encoding="utf-8")
        log.info("pdb_persisted_for_rescoring", path=str(shared_pdb_path))

    if not force_reprepare and await object_exists(prepared_path):
        return prepared_path

    prepare_receptor_cmd = _resolve_executable(settings.meeko_prepare_receptor_path)
    if not prepare_receptor_cmd:
        raise ProteinPreparationError(
            pdb_id=pdb_id,
            step="prepare_receptor_executable",
            detail=(
                "No se encontró 'mk_prepare_receptor.py'. Instala Meeko o provee "
                "la ruta correcta en MEEKO_PREPARE_RECEPTOR_PATH. Sin esta herramienta "
                "no es científicamente defendible preparar el receptor para Vina."
            ),
        )

    # El contenido ya fue descargado arriba si no existía el PDB compartido
    raw_content = await download_text(raw_path)

    try:
        filtered_content = _filter_pdb_content(
            raw_content,
            chain_id,
            keep_hetatm=False,  # Ortodoxo: solo proteína para docking, excepto cofactores
            cofactors_whitelist=cofactors_whitelist,
        )
    except ProteinPreparationError as e:
        e.pdb_id = pdb_id
        raise

    Path(settings.vina_temp_dir).mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(dir=settings.vina_temp_dir) as tmp_dir:
        tmp_dir_path = Path(tmp_dir)
        input_pdb = tmp_dir_path / f"{pdb_id}_{chain_id}.pdb"
        output_basename = tmp_dir_path / f"{pdb_id}_{chain_id}_prepared"

        input_pdb.write_text(filtered_content, encoding="utf-8")

        center_x, center_y, center_z = center
        size_x, size_y, size_z = size


        # Usar el módulo CLI de Meeko para asegurar entorno correcto
        conda_python = "/opt/conda/bin/python"
        command = [
            conda_python,
            "-m", "meeko.cli.mk_prepare_receptor",
            "-i", str(input_pdb),
            "-o", str(output_basename),
            "-p",
            "-v",
            "-a",
            "--default_altloc", settings.meeko_default_altloc,
            "--box_size", str(size_x), str(size_y), str(size_z),
            "--box_center", str(center_x), str(center_y), str(center_z),
        ]

        log.debug(
            "Invocando mk_prepare_receptor.py",
            command=command,
            input_pdb=str(input_pdb),
            output_basename=str(output_basename),
            cwd=str(tmp_dir_path),
        )

        process = await asyncio.create_subprocess_exec(
            *command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(tmp_dir_path),
        )
        stdout, stderr = await process.communicate()

        if process.returncode != 0:
            log.error(
                "mk_prepare_receptor.py falló",
                returncode=process.returncode,
                stderr=stderr.decode("utf-8", errors="replace"),
                stdout=stdout.decode("utf-8", errors="replace"),
                command=command,
            )
            raise ProteinPreparationError(
                pdb_id=pdb_id,
                step="mk_prepare_receptor",
                detail=f"STDERR: {stderr.decode('utf-8', errors='replace')}\nSTDOUT: {stdout.decode('utf-8', errors='replace')}\nCMD: {' '.join(command)}",
            )

        output_pdbqt = Path(f"{output_basename}.pdbqt")
        if not output_pdbqt.exists():
            raise ProteinPreparationError(
                pdb_id=pdb_id,
                step="mk_prepare_receptor_output",
                detail="La preparación terminó sin generar el archivo receptor .pdbqt esperado.",
            )

        content = output_pdbqt.read_text(encoding="utf-8", errors="replace")
        is_valid, validation_error = validate_pdbqt_content(content)
        if not is_valid:
            raise ProteinPreparationError(
                pdb_id=pdb_id,
                step="validate_pdbqt",
                detail=validation_error,
            )

        # --- Validación de calidad del PDBQT resultante ---
        pdbqt_atom_count = sum(1 for l in content.splitlines() if l.startswith(("ATOM", "HETATM")))
        pdbqt_has_charges = any(
            len(l) >= 77 and l[70:77].strip() not in ("", "0.000")
            for l in content.splitlines()
            if l.startswith(("ATOM", "HETATM"))
        )

        if pdbqt_atom_count < 500:
            log.warning(
                "PDBQT tiene pocos átomos — puede indicar preparación incompleta",
                pdb_id=pdb_id,
                atom_count=pdbqt_atom_count,
                expected_min=2000,
            )

        log.info(
            "receptor PDBQT validado",
            pdb_id=pdb_id,
            chain=chain_id,
            pdbqt_atoms=pdbqt_atom_count,
            has_gasteiger_charges=pdbqt_has_charges,
        )

        await upload_file_from_path(output_pdbqt, prepared_path)

    log.info("receptor preparado para Vina", pdb_id=pdb_id, chain=chain_id, path=prepared_path)
    return prepared_path
