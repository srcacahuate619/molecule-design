"""
services/docking/vina_service.py

Orquestación del docking real con AutoDock Vina.

Estrategia del MVP:
- preparar receptor con Meeko,
- preparar ligando desde SDF con Meeko,
- ejecutar Vina con parámetros explícitos,
- exportar poses a SDF con Meeko,
- parsear poses y cachear resultado.

Si alguna herramienta necesaria no existe, el servicio falla explícitamente.
"""

from __future__ import annotations

import asyncio
import re
import shutil
import sys
import tempfile
import os
import math
import json
from pathlib import Path

from core.config import get_settings
from core.exceptions import DockingFailed, VinaExecutableNotFound
from core.models import DockingPose, DockingResult
from services.docking.preparer import prepare_target
from utils.cache import cache
from utils.file_handlers import (
    StoragePath,
    download_text,
    object_exists,
    parse_vina_output_sdf,
    parse_vina_output_pdbqt,
    extract_pdbqt_poses,
    temp_file_from_minio,
    upload_file_from_path,
    upload_text,
    validate_pdbqt_content,
)
from utils.logger import get_logger

settings = get_settings()
log = get_logger(__name__)


def _resolve_executable(path_or_name: str) -> str | None:
    candidate = Path(path_or_name)
    if candidate.exists():
        return str(candidate)

    found = shutil.which(path_or_name)
    if found:
        return found

    scripts_dir = Path(sys.executable).resolve().parent
    windows_candidate = scripts_dir / f"{path_or_name}.exe"
    if windows_candidate.exists():
        return str(windows_candidate)

    py_candidate = scripts_dir / f"{path_or_name}.py"
    if py_candidate.exists():
        return str(py_candidate)

    return None


def _parse_vina_stdout(stdout: str) -> list[DockingPose]:
    mode_table_pattern = re.compile(
        r"^\s*(\d+)\s+([-+]?\d*\.?\d+(?:[eE][-+]?\d+)?)\s+([-+]?\d*\.?\d+(?:[eE][-+]?\d+)?)\s+([-+]?\d*\.?\d+(?:[eE][-+]?\d+)?)\s*$"
    )

    poses: list[DockingPose] = []
    in_mode_table = False

    for line in stdout.splitlines():
        stripped = line.strip()
        if not stripped:
            continue

        if stripped.lower().startswith("mode |"):
            in_mode_table = True
            continue

        if not in_mode_table:
            continue

        if stripped.startswith("-----+"):
            continue

        match = mode_table_pattern.match(stripped)
        if not match:
            if poses:
                break
            continue

        rank, affinity, rmsd_lb, rmsd_ub = match.groups()

        try:
            poses.append(
                DockingPose(
                    rank=int(rank),
                    affinity=float(affinity),
                    rmsd_lb=float(rmsd_lb),
                    rmsd_ub=float(rmsd_ub),
                )
            )
        except ValueError:
            continue

    return poses


def _parse_vina_metadata(stdout: str) -> tuple[str | None, int | None]:
    version_match = re.search(r"AutoDock Vina\s+v([\d\.]+)", stdout)
    seed_match = re.search(r"random seed:\s*(-?\d+)", stdout)

    vina_version = version_match.group(1) if version_match else None
    random_seed = int(seed_match.group(1)) if seed_match else None
    return vina_version, random_seed


def _relative_error_pct(observed: float, reference: float) -> float:
    denominator = max(abs(reference), 1e-12)
    return abs(observed - reference) / denominator * 100.0


async def _prepare_ligand_pdbqt(smiles_hash: str) -> str:
    ligand_prepare_cmd = _resolve_executable(settings.meeko_prepare_ligand_path)
    if not ligand_prepare_cmd:
        raise DockingFailed(
            molecule_id=smiles_hash,
            target_pdb_id=settings.default_target_pdb_id,
            detail=(
                "No se encontró 'mk_prepare_ligand.py'. Instala Meeko o configura "
                "MEEKO_PREPARE_LIGAND_PATH correctamente."
            ),
        )

    object_name = StoragePath.ligand_vina_input(smiles_hash)
    if await object_exists(object_name):
        return object_name

    conformer_path = StoragePath.ligand_conformer(smiles_hash)
    async with temp_file_from_minio(conformer_path, suffix=".sdf") as local_sdf:
        Path(settings.vina_temp_dir).mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=settings.vina_temp_dir) as tmp_dir:
            output_pdbqt = Path(tmp_dir) / f"{smiles_hash}.pdbqt"
            command = [
                ligand_prepare_cmd,
                "-i", str(local_sdf),
                "-o", str(output_pdbqt),
            ]

            process = await asyncio.create_subprocess_exec(
                *command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await process.communicate()

            if process.returncode != 0:
                raise DockingFailed(
                    molecule_id=smiles_hash,
                    target_pdb_id=settings.default_target_pdb_id,
                    vina_exit_code=process.returncode,
                    detail=stderr.decode("utf-8", errors="replace") or stdout.decode("utf-8", errors="replace"),
                )

            content = output_pdbqt.read_text(encoding="utf-8", errors="replace")
            is_valid, validation_error = validate_pdbqt_content(content)
            if not is_valid:
                raise DockingFailed(
                    molecule_id=smiles_hash,
                    target_pdb_id=settings.default_target_pdb_id,
                    detail=f"Ligando PDBQT inválido: {validation_error}",
                )

            await upload_file_from_path(output_pdbqt, object_name)

    return object_name


async def _run_vina_subprocess(
    receptor_path: Path,
    ligand_path: Path,
    output_path: Path,
    log_path: Path,
    target_pdb_id: str,
    center: tuple[float, float, float],
    size: tuple[float, float, float],
) -> str:
    vina_executable = _resolve_executable(settings.vina_executable_path)
    if not vina_executable:
        raise VinaExecutableNotFound(settings.vina_executable_path)

    command = [
        vina_executable,
        "--receptor", str(receptor_path),
        "--ligand", str(ligand_path),
        "--center_x", str(center[0]),
        "--center_y", str(center[1]),
        "--center_z", str(center[2]),
        "--size_x", str(size[0]),
        "--size_y", str(size[1]),
        "--size_z", str(size[2]),
        "--exhaustiveness", str(settings.vina_exhaustiveness),
        "--num_modes", str(settings.vina_num_poses),
        "--cpu", str(settings.vina_cpu),
        "--seed", str(settings.vina_seed),
        "--out", str(output_path),
    ]

    process = await asyncio.create_subprocess_exec(
        *command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        # Timeout de 10 minutos para soportar ex=32 en GPCRs
        stdout_bytes, stderr_bytes = await asyncio.wait_for(
            process.communicate(), timeout=600.0
        )
    except asyncio.TimeoutError:
        process.kill()
        await process.communicate()  # clean up
        raise DockingFailed(
            molecule_id="unknown",
            target_pdb_id=target_pdb_id,
            detail="AutoDock Vina excedió el timeout de 600 segundos. "
                   "La molécula puede ser demasiado grande o compleja para este setup.",
        )

    stdout = stdout_bytes.decode("utf-8", errors="replace")
    stderr = stderr_bytes.decode("utf-8", errors="replace")

    log_content = (
        f"# target={target_pdb_id}\n"
        f"# receptor={receptor_path}\n"
        f"# ligand={ligand_path}\n"
        f"# exhaustiveness={settings.vina_exhaustiveness}\n"
        f"# num_modes={settings.vina_num_poses}\n\n"
        f"STDOUT:\n{stdout}\n\nSTDERR:\n{stderr}\n"
    )
    log_path.write_text(log_content, encoding="utf-8")

    if process.returncode != 0:
        raise DockingFailed(
            molecule_id=ligand_path.stem,
            target_pdb_id=target_pdb_id,
            vina_exit_code=process.returncode,
            detail=stderr or stdout,
        )

    return stdout


async def run_vina_docking(
    smiles_hash: str,
    target_pdb_id: str,
    target_chain: str,
    target_center: tuple[float, float, float],
    target_size: tuple[float, float, float],
    force_redock: bool = False,
    hotspots: list[dict] | None = None,
) -> DockingResult:
    """Ejecuta docking real o devuelve cache si ya existe un cálculo idéntico."""
    # DEBUG: Bypass cache completely for all jobs (force recompute every time)
    cached = None
    # if cached is not None:
    #     return DockingResult(**cached)

    # Use a unique subdirectory for each job to avoid race conditions in parallel runs
    job_temp_dir = Path(tempfile.mkdtemp(prefix=f"vina-{smiles_hash[:8]}-{target_pdb_id}-", dir=settings.vina_temp_dir))
    
    try:
        receptor_object_path = await prepare_target(
            pdb_id=target_pdb_id,
            chain_id=target_chain,
            center=target_center,
            size=target_size,
            force_reprepare=False,
        )
        ligand_object_path = await _prepare_ligand_pdbqt(smiles_hash)

        export_cmd = _resolve_executable(settings.meeko_export_path)
        if not export_cmd:
            raise DockingFailed(
                molecule_id=smiles_hash,
                target_pdb_id=target_pdb_id,
                detail=(
                    "No se encontró 'mk_export.py'. La exportación a SDF es necesaria para "
                    "conservar conectividad y órdenes de enlace de forma defendible."
                ),
            )

        async with temp_file_from_minio(receptor_object_path, suffix=".pdbqt") as receptor_local:
            async with temp_file_from_minio(ligand_object_path, suffix=".pdbqt") as ligand_local:
                # We use the job_temp_dir we created
                tmp_dir_path = job_temp_dir
                output_pdbqt = tmp_dir_path / f"{smiles_hash}_{target_pdb_id}_out.pdbqt"
                output_sdf = tmp_dir_path / f"{smiles_hash}_{target_pdb_id}_out.sdf"
                output_log = tmp_dir_path / f"{smiles_hash}_{target_pdb_id}.log"

                stdout = await _run_vina_subprocess(
                    receptor_path=receptor_local,
                    ligand_path=ligand_local,
                    output_path=output_pdbqt,
                    log_path=output_log,
                    target_pdb_id=target_pdb_id,
                    center=target_center,
                    size=target_size,
                )

                export_process = await asyncio.create_subprocess_exec(
                    export_cmd,
                    str(output_pdbqt),
                    "-s",
                    str(output_sdf),
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                export_stdout, export_stderr = await export_process.communicate()

                if export_process.returncode != 0 or not output_sdf.exists():
                    raise DockingFailed(
                        molecule_id=smiles_hash,
                        target_pdb_id=target_pdb_id,
                        detail=(
                            export_stderr.decode("utf-8", errors="replace")
                            or export_stdout.decode("utf-8", errors="replace")
                            or "mk_export.py no generó el SDF esperado"
                        ),
                    )

                sdf_content = output_sdf.read_text(encoding="utf-8", errors="replace")
                # Strict SDF validation: must contain 'M  END' and at least one atom line
                def is_valid_sdf(s: str) -> bool:
                    if not s or not isinstance(s, str):
                        return False
                    lines = s.splitlines()
                    if not any("M  END" in line for line in lines):
                        return False
                    if len(lines) < 4:
                        return False
                    try:
                        atom_count = int(lines[3][0:3])
                    except Exception:
                        atom_count = 0
                    atom_lines = lines[4:4+atom_count]
                    has_atoms = any(len(l.strip()) > 0 for l in atom_lines)
                    return has_atoms and atom_count > 0

                scientific_warnings: list[str] = []
                def cast_pose_dict(p):
                    return {
                        "rank": int(p["rank"]),
                        "affinity": float(p["affinity"]),
                        "rmsd_lb": float(p["rmsd_lb"]),
                        "rmsd_ub": float(p["rmsd_ub"]),
                    }

                pdbqt_content = output_pdbqt.read_text(encoding="utf-8", errors="replace")
                pdbqt_pose_blocks = extract_pdbqt_poses(pdbqt_content)

                parsed_poses = parse_vina_output_sdf(sdf_content) if is_valid_sdf(sdf_content) else []
                poses: list[DockingPose] = []
                for i, pose_dict in enumerate(parsed_poses):
                    # Asignamos el bloque PDBQT correspondiente si existe
                    block = pdbqt_pose_blocks[i] if i < len(pdbqt_pose_blocks) else None
                    poses.append(DockingPose(**cast_pose_dict(pose_dict), pdbqt_block=block))
                
                parsing_source = "sdf" if poses else None

                # Fallback: if SDF is zombie, try OpenBabel to convert PDBQT to SDF
                if not poses:
                    try:
                        import subprocess
                        pdbqt_content = output_pdbqt.read_text(encoding="utf-8", errors="replace")
                        # Write PDBQT to temp file
                        with tempfile.NamedTemporaryFile("w", suffix=".pdbqt", delete=False) as tmp_pdbqt:
                            tmp_pdbqt.write(pdbqt_content)
                            tmp_pdbqt.flush()
                            pdbqt_path = tmp_pdbqt.name
                        with tempfile.NamedTemporaryFile("r", suffix=".sdf", delete=False) as tmp_sdf:
                            sdf_path = tmp_sdf.name
                        # Call OpenBabel
                        babel_cmd = ["obabel", "-ipdbqt", pdbqt_path, "-osdf", "-O", sdf_path]
                        result = subprocess.run(babel_cmd, capture_output=True, text=True, timeout=30)
                        if result.returncode == 0:
                            with open(sdf_path, "r", encoding="utf-8", errors="replace") as f:
                                sdf_content_babel = f.read()
                            if is_valid_sdf(sdf_content_babel):
                                parsed_poses = parse_vina_output_sdf(sdf_content_babel)
                                poses = []
                                for i, pose_dict in enumerate(parsed_poses):
                                    block = pdbqt_pose_blocks[i] if i < len(pdbqt_pose_blocks) else None
                                    poses.append(DockingPose(**cast_pose_dict(pose_dict), pdbqt_block=block))
                                parsing_source = "openbabel"
                                log.warning("SDF fallback: OpenBabel used because Meeko export was invalid.")
                        else:
                            scientific_warnings.append(f"OpenBabel fallback falló: {result.stderr}")
                        # Limpieza explícita de archivos temporales solo si existen
                        try:
                            if os.path.exists(pdbqt_path):
                                os.remove(pdbqt_path)
                            if os.path.exists(sdf_path):
                                os.remove(sdf_path)
                        except Exception as cleanup_exc:
                            scientific_warnings.append(f"Error limpiando archivos temporales de OpenBabel: {cleanup_exc}")
                    except Exception as ob_exc:
                        scientific_warnings.append(f"OpenBabel fallback exception: {ob_exc}")

                # Fallback: if still no poses, try parsing PDBQT for affinity only
                if not poses:
                    pdbqt_content = output_pdbqt.read_text(encoding="utf-8", errors="replace")
                    # --- Debug: guardar PDBQT crudo en /tmp (nunca bloquea el pipeline) ---
                    try:
                        import datetime
                        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                        artifact_dir = Path(settings.vina_temp_dir) / "pdbqt_debug"
                        artifact_dir.mkdir(parents=True, exist_ok=True)
                        artifact_path = artifact_dir / f"{smiles_hash}_{target_pdb_id}_{timestamp}.pdbqt"
                        artifact_path.write_text(pdbqt_content, encoding="utf-8")
                        log.warning("[DEBUG] PDBQT crudo guardado", path=str(artifact_path), warnings=scientific_warnings)
                    except Exception as _debug_exc:
                        log.warning("[DEBUG] No se pudo guardar PDBQT de debug", error=str(_debug_exc))
                    # --- Fin debug ---
                    pdbqt_pose_blocks = extract_pdbqt_poses(pdbqt_content)
                    parsed_poses_pdbqt = parse_vina_output_pdbqt(pdbqt_content)
                    poses = []
                    for i, pose in enumerate(parsed_poses_pdbqt):
                        block = pdbqt_pose_blocks[i] if i < len(pdbqt_pose_blocks) else None
                        poses.append(DockingPose(**cast_pose_dict(pose), pdbqt_block=block))
                    if poses:
                        parsing_source = "pdbqt"
                        log.warning("Affinity fallback: Extracted from REMARK VINA RESULT because SDF lacked numeric metadata.")

                if not poses:
                    if not settings.docking_allow_stdout_fallback:
                        raise DockingFailed(
                            molecule_id=smiles_hash,
                            target_pdb_id=target_pdb_id,
                            detail=(
                                "No se pudieron extraer poses estructuradas desde SDF/PDBQT y el fallback "
                                "a stdout está deshabilitado por rigor científico."
                            ),
                        )

                    poses_stdout = _parse_vina_stdout(stdout)
                    pdbqt_pose_blocks = extract_pdbqt_poses(pdbqt_content)
                    poses = []
                    for i, pose in enumerate(poses_stdout):
                        block = pdbqt_pose_blocks[i] if i < len(pdbqt_pose_blocks) else None
                        poses.append(DockingPose(**cast_pose_dict(pose.model_dump()), pdbqt_block=block))
                    if poses:
                        parsing_source = "vina_stdout"
                        scientific_warnings.append(
                            "Las afinidades se extrajeron de la tabla de stdout de Vina; revisa el log para trazabilidad completa."
                        )

                if not poses:
                    raise DockingFailed(
                        molecule_id=smiles_hash,
                        target_pdb_id=target_pdb_id,
                        detail="Vina terminó pero no se pudieron parsear poses válidas.",
                    )

                if poses[0].affinity > -3.0:
                    scientific_warnings.append(
                        "La mejor afinidad es débil (> -3.0 kcal/mol); interpretar como baja evidencia de unión en este setup de docking."
                    )

                stdout_poses = _parse_vina_stdout(stdout)
                if stdout_poses:
                    best_delta_pct = _relative_error_pct(poses[0].affinity, stdout_poses[0].affinity)
                    if best_delta_pct > settings.docking_max_consistency_error_pct:
                        raise DockingFailed(
                            molecule_id=smiles_hash,
                            target_pdb_id=target_pdb_id,
                            detail=(
                                "Inconsistencia numérica de afinidad entre parser estructurado y stdout de Vina "
                                f"({best_delta_pct:.4f}% > {settings.docking_max_consistency_error_pct:.4f}%)."
                            ),
                        )

                vina_version, vina_random_seed = _parse_vina_metadata(stdout)
                if vina_random_seed is not None and vina_random_seed != settings.vina_seed:
                    scientific_warnings.append(
                        "La semilla reportada por Vina difiere de la semilla configurada; revisar reproducibilidad del entorno."
                    )

                poses_path = StoragePath.docking_poses(smiles_hash, target_pdb_id)
                log_path = StoragePath.docking_log(smiles_hash, target_pdb_id)

                await upload_file_from_path(output_sdf, poses_path)
                await upload_text(output_log.read_text(encoding="utf-8"), log_path)

                # --- [NUEVO] Análisis de Hotspots Dinámico ---
                hotspots_hit = []
                if hotspots and poses and poses[0].pdbqt_block:
                    try:
                        hotspots_hit = _analyze_hotspot_interactions(
                            receptor_local, 
                            poses[0].pdbqt_block, 
                            hotspots
                        )
                        if hotspots_hit:
                            log.info("Hotspots hit detectados", hits=hotspots_hit)
                        else:
                            scientific_warnings.append("No se detectaron interacciones con los residuos críticos (hotspots) del receptor.")
                    except Exception as e:
                        log.error("Error analizando hotspots", error=str(e))
                        scientific_warnings.append(f"Error en análisis de hotspots: {e}")

                result = DockingResult(
                    best_affinity=poses[0].affinity,
                    poses=poses,
                    poses_file_path=poses_path,
                    parsing_source=parsing_source,
                    vina_version=vina_version,
                    vina_random_seed=vina_random_seed,
                    scientific_warnings=scientific_warnings,
                    hotspots_hit=hotspots_hit,
                )
                await cache.set_docking_result(smiles_hash, target_pdb_id, result.model_dump())

                log.info(
                    f"docking completado: smiles_hash={smiles_hash}, target={target_pdb_id}, best_affinity={result.best_affinity}, poses={len(result.poses)}"
                )
                return result
    finally:
        shutil.rmtree(job_temp_dir, ignore_errors=True)

def _analyze_hotspot_interactions(
    receptor_path: Path, 
    ligand_pdbqt: str, 
    hotspots: list[dict]
) -> list[str]:
    """
    Analiza si el ligando interactúa con los residuos críticos.
    Lógica: Distancia mínima < 4.0 Å entre cualquier átomo del ligando
    y cualquier átomo de la cadena lateral del residuo hotspot.
    """
    if not hotspots:
        return []

    # 1. Extraer coordenadas de los átomos del ligando
    ligand_coords = []
    for line in ligand_pdbqt.splitlines():
        if line.startswith(("ATOM", "HETATM")):
            try:
                x = float(line[30:38])
                y = float(line[38:46])
                z = float(line[46:54])
                ligand_coords.append((x, y, z))
            except:
                continue
    
    if not ligand_coords:
        return []

    # 2. Extraer coordenadas del receptor para los residuos hotspot
    # Formato esperado de hotspot['name']: "MET97", "ASP116", "A:TYR100"
    hotspot_names_full = {h["name"].upper() for h in hotspots}
    
    # Precomputar una versión sin cadena para fallbacks
    hotspot_names_no_chain = {}
    for h in hotspot_names_full:
        if ":" in h:
            hotspot_names_no_chain[h.split(":")[1]] = h
        else:
            hotspot_names_no_chain[h] = h

    receptor_atoms = {} # name -> list of coords

    with open(receptor_path, "r") as f:
        for line in f:
            if line.startswith(("ATOM", "HETATM")):
                res_name = line[17:20].strip()
                res_chain = line[21].strip() # Capturar cadena si existe
                res_seq = line[22:26].strip()
                
                full_res_no_chain = f"{res_name}{res_seq}"
                full_res_with_chain = f"{res_chain}:{res_name}{res_seq}" if res_chain else full_res_no_chain
                
                # Verificar si alguna de las formas está en hotspots
                matched_id = None
                if full_res_with_chain in hotspot_names_full:
                    matched_id = full_res_with_chain
                elif full_res_no_chain in hotspot_names_full:
                    matched_id = full_res_no_chain
                elif full_res_no_chain in hotspot_names_no_chain:
                    # Fallback: si el PDBQT perdió la cadena, usar la versión sin cadena
                    matched_id = hotspot_names_no_chain[full_res_no_chain]
                
                if matched_id:
                    try:
                        x = float(line[30:38])
                        y = float(line[38:46])
                        z = float(line[46:54])
                        if matched_id not in receptor_atoms:
                            receptor_atoms[matched_id] = []
                        receptor_atoms[matched_id].append((x, y, z))
                    except:
                        continue

    # 3. Calcular distancias mínimas
    hits = []
    # Aumentamos a 5.0 Å para capturar interacciones hidrofóbicas/apilamiento (stacking) 
    # que son comunes en hotspots y tienen un rango mayor que los H-bonds.
    THRESHOLD_SQ = 5.0 * 5.0 
    
    for res_name, res_coords in receptor_atoms.items():
        min_dist_sq = float('inf')
        for r_coord in res_coords:
            for l_coord in ligand_coords:
                d2 = (r_coord[0]-l_coord[0])**2 + (r_coord[1]-l_coord[1])**2 + (r_coord[2]-l_coord[2])**2
                if d2 < min_dist_sq:
                    min_dist_sq = d2
        
        min_dist = min_dist_sq**0.5
        log.info(f"Hotspot distance: {res_name} -> {min_dist:.2f} A")
        
        if min_dist_sq < THRESHOLD_SQ:
            hits.append(res_name)
    
    return hits
