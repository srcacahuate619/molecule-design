"""
api/routers/targets.py

Endpoints para gestión de targets biológicos, incluyendo
búsqueda en AlphaFold DB para targets sin estructura experimental.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from core.models import Target
from db.repository import Repository

from utils.logger import get_logger

log = get_logger(__name__)

router = APIRouter(prefix="/targets", tags=["Targets biológicos"])

@router.get(
    "/",
    response_model=list[Target],
    summary="Listar todos los targets biológicos disponibles",
)
async def list_targets(db: AsyncSession = Depends(get_db)) -> list[Target]:
    repo = Repository(db)
    targets = await repo.get_all_targets()
    # Ensure default target is seeded if empty
    if not targets:
        await repo.ensure_default_target()
        targets = await repo.get_all_targets()
    return [Target.model_validate(t) for t in targets]


class AlphaFoldLookupRequest(BaseModel):
    uniprot_id: str = Field(..., min_length=4, max_length=20, description="UniProt accession (ej: P08908)")


class AlphaFoldEntryResponse(BaseModel):
    uniprot_id: str
    gene: str | None
    organism: str | None
    model_url: str
    mean_plddt: float | None
    high_confidence_residues: int | None
    total_residues: int | None
    warnings: list[str]


class TargetSearchResponse(BaseModel):
    results: list[AlphaFoldEntryResponse]
    source: str = "AlphaFold DB"
    disclaimer: str = (
        "Las estructuras de AlphaFold son modelos computacionales (predicciones). "
        "No equivalen a datos experimentales cryo-EM o cristalográficos. "
        "Los resultados de docking contra estas estructuras tienen mayor incertidumbre."
    )


@router.get(
    "/alphafold/lookup/{uniprot_id}",
    response_model=AlphaFoldEntryResponse,
    summary="Buscar proteína en AlphaFold DB por UniProt ID",
)
async def alphafold_lookup(uniprot_id: str) -> AlphaFoldEntryResponse:
    """
    Busca una proteína en AlphaFold Database por UniProt accession.

    Devuelve metadata del modelo incluyendo métricas de confianza (pLDDT)
    que deben consultarse antes de usar la estructura para docking.
    """
    from services.alphafold.client import download_structure, lookup_uniprot

    entry = await lookup_uniprot(uniprot_id.strip().upper())
    if entry is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Proteína {uniprot_id} no encontrada en AlphaFold DB",
        )

    # Descargar y analizar confianza
    try:
        structure = await download_structure(entry)
        return AlphaFoldEntryResponse(
            uniprot_id=entry.uniprot_id,
            gene=entry.gene,
            organism=entry.organism,
            model_url=entry.model_url,
            mean_plddt=entry.mean_plddt,
            high_confidence_residues=entry.high_confidence_residues,
            total_residues=entry.total_residues,
            warnings=structure.warnings,
        )
    except Exception as e:
        log.error("error procesando estructura AlphaFold", error=str(e))
        return AlphaFoldEntryResponse(
            uniprot_id=entry.uniprot_id,
            gene=entry.gene,
            organism=entry.organism,
            model_url=entry.model_url,
            mean_plddt=None,
            high_confidence_residues=None,
            total_residues=None,
            warnings=[
                f"No se pudo analizar la estructura: {str(e)}",
                "La estructura puede descargarse manualmente desde AlphaFold DB.",
            ],
        )


@router.get(
    "/alphafold/search",
    response_model=TargetSearchResponse,
    summary="Buscar proteínas por nombre de gen",
)
async def alphafold_search(
    gene: str = Query(..., min_length=2, max_length=50, description="Nombre del gen (ej: HTR1A)"),
    organism: str = Query(default="Homo sapiens", description="Organismo"),
) -> TargetSearchResponse:
    """
    Busca proteínas en AlphaFold DB a través de UniProt por nombre de gen.
    Útil cuando se quiere explorar targets nuevos sin conocer el UniProt ID.
    """
    from services.alphafold.client import search_by_gene

    entries = await search_by_gene(gene.strip(), organism)

    results = [
        AlphaFoldEntryResponse(
            uniprot_id=e.uniprot_id,
            gene=e.gene,
            organism=e.organism,
            model_url=e.model_url,
            mean_plddt=e.mean_plddt,
            high_confidence_residues=e.high_confidence_residues,
            total_residues=e.total_residues,
            warnings=[],
        )
        for e in entries
    ]

    return TargetSearchResponse(results=results)
