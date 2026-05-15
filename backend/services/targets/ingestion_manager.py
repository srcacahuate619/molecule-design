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
from utils.file_handlers import download_pdb_from_rcsb, upload_text, StoragePath, object_exists
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

    # 4. Preparar Estructuralmente (PDBQT)
    try:
        prepared_file_path = await prepare_target(
            pdb_id=pdb_id,
            chain_id=chain_id,
            center=center,
            size=size,
            force_reprepare=True
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
            hotspots=hotspots
        )
        db.add(target)
    else:
        existing.is_prepared = True
        existing.prepared_file_path = prepared_file_path
        existing.grid_center_x = center[0]
        existing.grid_center_y = center[1]
        existing.grid_center_z = center[2]
        existing.hotspots = hotspots
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
