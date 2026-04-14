"""
tests/unit/test_targets_router.py

Tests unitarios del router de targets (api/routers/targets.py).

Estos tests invocan las funciones del endpoint directamente
(sin HTTP client) y mockean las llamadas a AlphaFold DB.

No requieren base de datos — son tests unitarios puros.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from services.alphafold.client import AlphaFoldEntry, AlphaFoldStructure


# ═══════════════════════════════════════════════════════════════════════════════
# MOCK DATA
# ═══════════════════════════════════════════════════════════════════════════════

def _make_entry(
    uniprot_id: str = "P08908",
    gene: str = "HTR1A",
    organism: str = "Homo sapiens",
) -> AlphaFoldEntry:
    return AlphaFoldEntry(
        uniprot_id=uniprot_id,
        gene=gene,
        organism=organism,
        model_url=f"https://alphafold.ebi.ac.uk/files/AF-{uniprot_id}-F1-model_v4.pdb",
        pae_url=None,
        plddt_url=None,
        confidence_version=4,
        model_created_date="2023-01-01",
        sequence_length=422,
        high_confidence_residues=350,
        total_residues=422,
        mean_plddt=85.3,
    )


def _make_structure(entry=None, warnings=None) -> AlphaFoldStructure:
    return AlphaFoldStructure(
        entry=entry or _make_entry(),
        pdb_path="/tmp/AF-P08908-F1-model_v4.pdb",
        plddt_scores=[85.0] * 422,
        warnings=warnings or [],
    )


# ═══════════════════════════════════════════════════════════════════════════════
# alphafold_lookup
# ═══════════════════════════════════════════════════════════════════════════════

class TestAlphaFoldLookup:
    """Tests del endpoint alphafold_lookup llamado directamente."""

    @pytest.mark.asyncio
    async def test_lookup_success(self):
        """Lookup exitoso retorna datos con pLDDT."""
        from api.routers.targets import alphafold_lookup

        entry = _make_entry()
        structure = _make_structure(entry)

        with patch("services.alphafold.client.lookup_uniprot", new_callable=AsyncMock) as mock_lookup, \
             patch("services.alphafold.client.download_structure", new_callable=AsyncMock) as mock_download:
            mock_lookup.return_value = entry
            mock_download.return_value = structure

            result = await alphafold_lookup("P08908")

        assert result.uniprot_id == "P08908"
        assert result.gene == "HTR1A"
        assert result.organism == "Homo sapiens"
        assert result.mean_plddt == pytest.approx(85.3, abs=0.1)
        assert result.high_confidence_residues == 350
        assert result.total_residues == 422
        assert "alphafold" in result.model_url.lower()

    @pytest.mark.asyncio
    async def test_lookup_not_found(self):
        """UniProt ID inexistente lanza HTTPException 404."""
        from fastapi import HTTPException
        from api.routers.targets import alphafold_lookup

        with patch("services.alphafold.client.lookup_uniprot", new_callable=AsyncMock) as mock_lookup:
            mock_lookup.return_value = None

            with pytest.raises(HTTPException) as exc_info:
                await alphafold_lookup("XXXXXX")

        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_lookup_structure_download_error(self):
        """Si download_structure falla, retorna datos parciales con warnings."""
        from api.routers.targets import alphafold_lookup

        entry = _make_entry()

        with patch("services.alphafold.client.lookup_uniprot", new_callable=AsyncMock) as mock_lookup, \
             patch("services.alphafold.client.download_structure", new_callable=AsyncMock) as mock_download:
            mock_lookup.return_value = entry
            mock_download.side_effect = RuntimeError("Connection timed out")

            result = await alphafold_lookup("P08908")

        assert result.uniprot_id == "P08908"
        assert result.mean_plddt is None
        assert len(result.warnings) > 0
        assert any("no se pudo" in w.lower() for w in result.warnings)

    @pytest.mark.asyncio
    async def test_lookup_normalizes_to_uppercase(self):
        """El endpoint normaliza el UniProt ID a mayúsculas."""
        from api.routers.targets import alphafold_lookup

        entry = _make_entry()
        structure = _make_structure(entry)

        with patch("services.alphafold.client.lookup_uniprot", new_callable=AsyncMock) as mock_lookup, \
             patch("services.alphafold.client.download_structure", new_callable=AsyncMock) as mock_download:
            mock_lookup.return_value = entry
            mock_download.return_value = structure

            await alphafold_lookup("p08908")

        mock_lookup.assert_called_once_with("P08908")

    @pytest.mark.asyncio
    async def test_lookup_with_warnings(self):
        """Warnings de la estructura se pasan al response."""
        from api.routers.targets import alphafold_lookup

        entry = _make_entry()
        structure = _make_structure(
            entry,
            warnings=["Low pLDDT in loop region 200-230"],
        )

        with patch("services.alphafold.client.lookup_uniprot", new_callable=AsyncMock) as mock_lookup, \
             patch("services.alphafold.client.download_structure", new_callable=AsyncMock) as mock_download:
            mock_lookup.return_value = entry
            mock_download.return_value = structure

            result = await alphafold_lookup("P08908")

        assert "Low pLDDT in loop region 200-230" in result.warnings


# ═══════════════════════════════════════════════════════════════════════════════
# alphafold_search
# ═══════════════════════════════════════════════════════════════════════════════

class TestAlphaFoldSearch:
    """Tests del endpoint alphafold_search llamado directamente."""

    @pytest.mark.asyncio
    async def test_search_success(self):
        """Búsqueda exitosa retorna resultados con disclaimer."""
        from api.routers.targets import alphafold_search

        entries = [
            _make_entry("P08908", "HTR1A", "Homo sapiens"),
            _make_entry("Q64264", "HTR1A", "Mus musculus"),
        ]

        with patch("services.alphafold.client.search_by_gene", new_callable=AsyncMock) as mock_search:
            mock_search.return_value = entries

            result = await alphafold_search(gene="HTR1A")

        assert len(result.results) == 2
        assert result.source == "AlphaFold DB"
        # Disclaimer sobre limitaciones de modelos predichos es obligatorio
        assert "predicciones" in result.disclaimer.lower() or "computacionales" in result.disclaimer.lower()

    @pytest.mark.asyncio
    async def test_search_no_results(self):
        """Búsqueda sin resultados retorna lista vacía."""
        from api.routers.targets import alphafold_search

        with patch("services.alphafold.client.search_by_gene", new_callable=AsyncMock) as mock_search:
            mock_search.return_value = []

            result = await alphafold_search(gene="NONEXISTENT")

        assert result.results == []

    @pytest.mark.asyncio
    async def test_search_passes_organism(self):
        """El parámetro organism se pasa a search_by_gene."""
        from api.routers.targets import alphafold_search

        with patch("services.alphafold.client.search_by_gene", new_callable=AsyncMock) as mock_search:
            mock_search.return_value = []

            await alphafold_search(gene="HTR1A", organism="Mus musculus")

        mock_search.assert_called_once_with("HTR1A", "Mus musculus")

    @pytest.mark.asyncio
    async def test_search_default_organism(self):
        """Sin parámetro organism explícito, se usa 'Homo sapiens' como default."""
        from api.routers.targets import alphafold_search

        with patch("services.alphafold.client.search_by_gene", new_callable=AsyncMock) as mock_search:
            mock_search.return_value = []

            # Pasar explícitamente el default para simular HTTP
            await alphafold_search(gene="HTR1A", organism="Homo sapiens")

        mock_search.assert_called_once_with("HTR1A", "Homo sapiens")
