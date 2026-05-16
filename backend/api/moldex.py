from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_db, get_current_user, get_current_user_optional
from core.models import UserORM
from db.repository import Repository
from utils.logger import get_logger

log = get_logger(__name__)

router = APIRouter(prefix="/moldex", tags=["Moldex"])

@router.get("", summary="Obtiene el catálogo de moléculas evaluadas (Moldex)")
async def get_moldex(
    target_pdb_id: str | None = Query(None, description="Filtrar por ID de PDB (ej: 7E2Y)"),
    current_user: UserORM | None = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    repo = Repository(db)
    
    if current_user is None:
        current_user = await repo.get_or_create_test_user()
    
    results = await repo.get_moldex_molecules(
        user_id=current_user.id,
        target_pdb_id=target_pdb_id
    )
    
    # Formatear respuesta para la UI de Pokedex
    catalog = []
    for res in results:
        mol = res.molecule
        target = mol.target
        
        catalog.append({
            "id": str(mol.id),
            "name": mol.name or f"Ligando {mol.smiles_hash[:8]}",
            "smiles": mol.smiles,
            "smiles_hash": mol.smiles_hash,
            "created_at": mol.created_at.isoformat(),
            "target": {
                "pdb_id": target.pdb_id,
                "name": target.name,
                "family": target.structural_family,
            },
            "metrics": {
                "affinity": res.affinity_kcal,
                "log_p": res.log_p,
                "mw": res.molecular_weight,
                "tpsa": res.tpsa,
                "score": res.total_score,
            },
            "hotspots_hit": res.hotspots_hit or [],
            "blockchain": {
                "certified": bool(res.blockchain_tx_id),
                "tx_signature": res.blockchain_tx_id,
            }
        })
        
    return {
        "count": len(catalog),
        "results": catalog
    }
