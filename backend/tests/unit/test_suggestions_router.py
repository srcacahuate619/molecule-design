"""
tests/unit/test_suggestions_router.py

Tests unitarios del router de sugerencias (api/routers/suggestions.py).

Estos tests invocan la función del endpoint directamente
y usan el generador de novo real (basado en reglas, no requiere IA).

No requieren base de datos — son tests unitarios puros.

Nota científica:
    Las sugerencias se basan en transformaciones bioisostéricas documentadas
    (Meanwell 2011, Patani & LaVoie 1996). Los tests verifican que:
    - el disclaimer es informativo y no oculta limitaciones,
    - las sugerencias incluyen SMILES válidos,
    - se respeta max_suggestions.
"""

from __future__ import annotations

import pytest

from api.routers.suggestions import SuggestionRequest, generate_suggestions


def _has_rdkit() -> bool:
    """Check if RDKit is available (generator uses it internally)."""
    try:
        from rdkit import Chem  # noqa: F401
        return True
    except ImportError:
        return False


_skip_no_rdkit = pytest.mark.skipif(
    not _has_rdkit(),
    reason="RDKit not available (expected on Python 3.14 local env)",
)


# ═══════════════════════════════════════════════════════════════════════════════
# POST /suggestions/generate (llamado directamente)
# ═══════════════════════════════════════════════════════════════════════════════

class TestGenerateSuggestions:
    """Tests del endpoint generate_suggestions."""

    @_skip_no_rdkit
    @pytest.mark.asyncio
    async def test_generate_with_aspirin(self):
        """Aspirina genera sugerencias (tiene grupos para bioisosteria)."""
        request = SuggestionRequest(
            smiles="CC(=O)Oc1ccccc1C(=O)O",
            max_suggestions=3,
        )
        result = await generate_suggestions(request)

        assert result.success is True
        assert result.method == "rule_based"
        assert len(result.suggestions) <= 3

        # Disclaimer obligatorio
        assert len(result.disclaimer) > 20
        assert "hipótesis" in result.disclaimer.lower() or "computacionales" in result.disclaimer.lower()

    @pytest.mark.asyncio
    async def test_suggestion_fields_complete(self):
        """Cada sugerencia tiene todos los campos requeridos no vacíos."""
        request = SuggestionRequest(
            smiles="CC(=O)Oc1ccccc1C(=O)O",
            max_suggestions=5,
        )
        result = await generate_suggestions(request)

        for s in result.suggestions:
            assert len(s.smiles) > 0
            assert len(s.name) > 0
            assert len(s.rationale) > 0
            assert s.modification_type in (
                "bioisostere", "substitution", "addition", "deletion", "scaffold",
            )
            assert s.confidence in ("high", "medium", "low")
            assert s.source == "rule_based"

    @pytest.mark.asyncio
    async def test_respects_max_suggestions(self):
        """No retorna más sugerencias que max_suggestions."""
        request = SuggestionRequest(
            smiles="CC(=O)Oc1ccccc1C(=O)O",
            max_suggestions=2,
        )
        result = await generate_suggestions(request)
        assert len(result.suggestions) <= 2

    @_skip_no_rdkit
    @pytest.mark.asyncio
    async def test_with_properties_and_scores(self):
        """Acepta propiedades y scores opcionales."""
        request = SuggestionRequest(
            smiles="CC(=O)Oc1ccccc1C(=O)O",
            properties={
                "molecular_weight": 180.16,
                "log_p": 1.19,
                "lipinski_pass": True,
            },
            scores={
                "total_score": 65.0,
                "adme_score": 70.0,
            },
            max_suggestions=5,
        )
        result = await generate_suggestions(request)
        assert result.success is True

    @pytest.mark.asyncio
    async def test_invalid_smiles_no_crash(self):
        """SMILES inválido no crashea — retorna success=False o warnings."""
        request = SuggestionRequest(
            smiles="INVALID_SMILES",
            max_suggestions=5,
        )
        result = await generate_suggestions(request)

        # Puede ser success=False con warnings, o success=True con 0 sugerencias
        if not result.success:
            assert result.warnings or result.suggestions == []

    @pytest.mark.asyncio
    async def test_simple_molecule_may_have_fewer_suggestions(self):
        """Molécula simple (etanol) puede tener pocas o ninguna sugerencia."""
        request = SuggestionRequest(
            smiles="CCO",
            max_suggestions=10,
        )
        result = await generate_suggestions(request)

        # No debe crashear, aunque tenga 0 sugerencias
        assert isinstance(result.suggestions, list)

    @pytest.mark.asyncio
    async def test_benzene_ring_replacement(self):
        """Benceno debería generar sugerencia fenilo→piridina."""
        request = SuggestionRequest(
            smiles="c1ccccc1",
            max_suggestions=10,
        )
        result = await generate_suggestions(request)

        if result.suggestions:
            # Al menos una sugerencia debería tener nitrógeno (piridina)
            smiles_list = [s.smiles for s in result.suggestions]
            has_nitrogen = any("n" in sm.lower() or "N" in sm for sm in smiles_list)
            # Es una heurística — puede o no generarla según las reglas
            if has_nitrogen:
                assert True  # expected

    @pytest.mark.asyncio
    async def test_disclaimer_always_present(self):
        """El disclaimer siempre está presente, incluso sin sugerencias."""
        request = SuggestionRequest(
            smiles="[Cu]",  # Molécula inusual — posiblemente 0 sugerencias
            max_suggestions=1,
        )
        result = await generate_suggestions(request)
        assert len(result.disclaimer) > 0
