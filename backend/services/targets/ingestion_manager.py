"""
services/targets/ingestion_manager.py

Motor de ingesta científica de proteínas.
Automatiza la descarga, análisis de pockets y preparación estructural.
"""

import asyncio
from typing import Any
from sqlalchemy.ext.asyncio import AsyncSession
from core.models import TargetORM
from db.repository import Repository
from services.docking.preparer import prepare_target
from utils.file_handlers import download_pdb_from_rcsb, upload_text, StoragePath, object_exists, fetch_target_cofactors_from_rcsb
from utils.structural import discover_pocket_from_pdb
from utils.logger import get_logger

log = get_logger(__name__)

async def ingest_new_target(
    pdb_id: str,
    db: AsyncSession,
    chain_id: str = "A",
    ligand_chain: str | None = None,
    is_hot: bool = False,
    structural_family: str | None = None,
    cofactors_whitelist: list[str] | None = None,
    force_reingest: bool = False
) -> dict:
    """
    Orquesta la ingesta completa de un target desde el PDB ID.
    1. Descarga metadata y estructura.
    2. Descubre pocket automáticamente.
    3. Prepara receptor (PDBQT).
    4. Persiste en DB.
    """
    pdb_id = pdb_id.upper().strip()
    repo = Repository(db)
    
    # 1. Verificar si ya existe
    existing = await repo.get_target_by_pdb_id(pdb_id)
    if existing and existing.is_prepared and not force_reingest:
        return {"success": True, "message": f"Target {pdb_id} ya existe y está preparado.", "target": existing}

    # 2. Descargar PDB crudo
    log.info("ingesta_iniciada", pdb_id=pdb_id)
    raw_path = StoragePath.target_raw(pdb_id)
    if not await object_exists(raw_path):
        pdb_content = await download_pdb_from_rcsb(pdb_id)
        await upload_text(pdb_content, raw_path)
    else:
        from utils.file_handlers import download_text
        pdb_content = await download_text(raw_path)

    # 3. Descubrir Pocket y Hotspots
    pocket_info = discover_pocket_from_pdb(pdb_content, chain_id, ligand_chain)
    if not pocket_info["success"]:
        log.warning("pocket_discovery_fallido", pdb_id=pdb_id, error=pocket_info.get("error"))
        # Fallback a centro (0,0,0) o error? Por rigor científico, fallamos si no hay ligando
        # a menos que el usuario provea coordenadas manuales (futura mejora).
        raise ValueError(f"No se pudo encontrar un pocket automático para {pdb_id}: {pocket_info.get('error')}")

    center = pocket_info["grid_center"]
    size = (25.0, 25.0, 25.0) # Tamaño estándar sugerido
    hotspots = pocket_info["suggested_hotspots"]

    # Extraer el nombre de 3 letras del ligando de referencia (ej: "A:HEM123" -> "HEM")
    ligand_id = pocket_info.get("ligand_id", "")
    main_ligand_name = ""
    if ":" in ligand_id:
        res_part = ligand_id.split(":")[1]
        # Filtrar números para quedarse solo con letras ("HEM123" -> "HEM")
        main_ligand_name = "".join([c for c in res_part if c.isalpha()])

    # 3.5 Cofactors Whitelist (Automatizado si no se provee)
    if cofactors_whitelist is None:
        cofactors_whitelist = await fetch_target_cofactors_from_rcsb(pdb_id)
        
    # Asegurarnos de no conservar el ligando principal contra el que vamos a hacer docking
    if main_ligand_name and main_ligand_name in cofactors_whitelist:
        cofactors_whitelist.remove(main_ligand_name)
        log.info("ligando principal removido de la lista blanca", pdb_id=pdb_id, removed=main_ligand_name)

    log.info("cofactores a conservar", pdb_id=pdb_id, whitelist=cofactors_whitelist)

    # 4. Preparar Estructuralmente (PDBQT)
    try:
        prepared_file_path = await prepare_target(
            pdb_id=pdb_id,
            chain_id=chain_id,
            center=center,
            size=size,
            force_reprepare=True,
            cofactors_whitelist=cofactors_whitelist
        )
    except Exception as e:
        log.error("preparacion_fallida", pdb_id=pdb_id, error=str(e))
        raise

    # 5. Persistir en DB
    if not existing:
        target = TargetORM(
            pdb_id=pdb_id,
            name=f"Ingested Target {pdb_id}", # Se puede mejorar con fetch de metadata real
            chain=chain_id,
            grid_center_x=center[0],
            grid_center_y=center[1],
            grid_center_z=center[2],
            grid_size_x=size[0],
            grid_size_y=size[1],
            grid_size_z=size[2],
            requires_cns=False,
            is_prepared=True,
            prepared_file_path=prepared_file_path,
            is_hot=is_hot,
            structural_family=structural_family,
            hotspots=hotspots,
            cofactors_whitelist=cofactors_whitelist
        )
        db.add(target)
    else:
        existing.is_prepared = True
        existing.prepared_file_path = prepared_file_path
        existing.grid_center_x = center[0]
        existing.grid_center_y = center[1]
        existing.grid_center_z = center[2]
        existing.hotspots = hotspots
        existing.cofactors_whitelist = cofactors_whitelist
        if structural_family:
            existing.structural_family = structural_family
        existing.is_hot = is_hot
        target = existing

    await db.commit()
    log.info("ingesta_completada", pdb_id=pdb_id, center=center, hotspots_count=len(hotspots))
    
    return {
        "success": True,
        "pdb_id": pdb_id,
        "center": center,
        "hotspots_mined": len(hotspots),
        "ligand_reference": pocket_info.get("ligand_id")
    }

async def ingest_custom_target(
    file_content: bytes,
    filename: str,
    name: str,
    is_curated: bool,
    db: AsyncSession,
    chain_id: str = "A",
    grid_center: tuple[float, float, float] | None = None,
    grid_size: tuple[float, float, float] = (20.0, 20.0, 20.0),
    cofactors_whitelist: list[str] | None = None
) -> dict:
    """
    Ingesta un target subido manualmente por el usuario.
    Si is_curated=True, asume que es un archivo .pdbqt listo.
    Si is_curated=False, asume que es un .pdb y lo cura.
    """
    import uuid
    pdb_id = f"USR_{uuid.uuid4().hex[:6].upper()}"
    repo = Repository(db)
    
    log.info("ingesta_custom_iniciada", pdb_id=pdb_id, is_curated=is_curated)
    
    if is_curated:
        if not filename.endswith(".pdbqt"):
            raise ValueError("Los archivos curados deben ser formato .pdbqt")
        if not grid_center:
            raise ValueError("Debe proporcionar las coordenadas del grid (centro) para archivos curados (.pdbqt)")
            
        prepared_path = StoragePath.target_prepared(pdb_id)
        await upload_text(file_content.decode('utf-8'), prepared_path)
        
        target = TargetORM(
            pdb_id=pdb_id,
            name=name,
            chain=chain_id,
            grid_center_x=grid_center[0],
            grid_center_y=grid_center[1],
            grid_center_z=grid_center[2],
            grid_size_x=grid_size[0],
            grid_size_y=grid_size[1],
            grid_size_z=grid_size[2],
            requires_cns=False,
            is_prepared=True,
            prepared_file_path=prepared_path,
            is_hot=False,
            is_private=True,
            is_community=False,
            cofactors_whitelist=cofactors_whitelist or []
        )
        db.add(target)
        await db.commit()
        return {"success": True, "message": f"Target personalizado {pdb_id} subido exitosamente.", "target": target}
    else:
        if not filename.endswith(".pdb"):
            raise ValueError("Los archivos crudos deben ser formato .pdb")
            
        raw_path = StoragePath.target_raw(pdb_id)
        log.info("ingesta_custom_decodificando_archivo", pdb_id=pdb_id)
        try:
            decoded_content = file_content.decode('utf-8')
            log.info("ingesta_custom_decodificado_ok", pdb_id=pdb_id, size=len(decoded_content))
        except Exception as e:
            log.error("ingesta_custom_decodificado_error", pdb_id=pdb_id, error=str(e))
            raise ValueError(f"El archivo no es UTF-8 válido: {str(e)}")
            
        log.info("ingesta_custom_subiendo_minio_raw", pdb_id=pdb_id, path=raw_path)
        await upload_text(decoded_content, raw_path)
        log.info("ingesta_custom_subido_minio_raw_ok", pdb_id=pdb_id)
        
        pdb_text = file_content.decode('utf-8')
        hotspots = []
        center = grid_center
        
        if not center:
            # Intentar descubrir pocket
            pocket_info = discover_pocket_from_pdb(pdb_text, chain_id)
            if not pocket_info["success"]:
                raise ValueError(f"No se pudo autodescubrir el sitio activo: {pocket_info.get('error')}. Por favor proporcione las coordenadas manuales.")
            center = pocket_info["grid_center"]
            hotspots = pocket_info["suggested_hotspots"]
            
        # Curacion
        try:
            prepared_file_path = await prepare_target(
                pdb_id=pdb_id,
                chain_id=chain_id,
                center=center,
                size=grid_size,
                force_reprepare=True,
                cofactors_whitelist=cofactors_whitelist or []
            )
        except Exception as e:
            log.error("preparacion_custom_fallida", pdb_id=pdb_id, error=str(e))
            raise ValueError(f"Error curando el receptor: {str(e)}")
            
        target = TargetORM(
            pdb_id=pdb_id,
            name=name,
            chain=chain_id,
            grid_center_x=center[0],
            grid_center_y=center[1],
            grid_center_z=center[2],
            grid_size_x=grid_size[0],
            grid_size_y=grid_size[1],
            grid_size_z=grid_size[2],
            requires_cns=False,
            is_prepared=True,
            prepared_file_path=prepared_file_path,
            is_hot=False,
            is_private=True,
            is_community=False,
            hotspots=hotspots,
            cofactors_whitelist=cofactors_whitelist or []
        )
        db.add(target)
        await db.commit()
        return {"success": True, "message": f"Target personalizado {pdb_id} curado e ingestado exitosamente.", "target": target}
