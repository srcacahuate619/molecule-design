"""
tests/unit/test_engine.py

Tests para scoring/engine.py — motor de score compuesto.

Verifica:
1. Score total es combinación ponderada de las 3 dimensiones.
2. Pesos configurados se respetan.
3. Strongest/weakest dimension se identifica correctamente.
4. Improvement hints son coherentes.
5. Score siempre en [0, 100].
"""

import pytest

from scoring.engine import calculate_score_breakdown, _pick_dimensions, _build_improvement_hint
from core.models import DockingResult, DockingPose, PhysicochemicalProperties
from core.config import get_settings


# ═══════════════════════════════════════════════════════════════════════════════
# Fixtures / Helpers
# ═══════════════════════════════════════════════════════════════════════════════

def _make_docking(affinity: float = -7.0) -> DockingResult:
    """Crea un DockingResult mínimo válido."""
    return DockingResult(
        best_affinity=affinity,
        poses=[DockingPose(rank=1, affinity=affinity, rmsd_lb=0.0, rmsd_ub=0.0)],
        poses_file_path="test/path.sdf",
        parsing_source="sdf",
    )


def _make_props(**overrides) -> PhysicochemicalProperties:
    """Crea PhysicochemicalProperties con defaults drug-like."""
    defaults = dict(
        molecular_weight=250.0,
        log_p=2.5,
        tpsa=60.0,
        hbd=2,
        hba=4,
        rotatable_bonds=3,
        heavy_atom_count=18,
        ring_count=2,
        qed=0.7,
        lipinski_pass=True,
        veber_pass=True,
    )
    defaults.update(overrides)
    return PhysicochemicalProperties(**defaults)


# ═══════════════════════════════════════════════════════════════════════════════
# _pick_dimensions
# ═══════════════════════════════════════════════════════════════════════════════

class TestPickDimensions:
    def test_strongest_is_highest(self):
        strongest, _ = _pick_dimensions(80, 60, 40)
        assert strongest == "affinity"

    def test_weakest_is_lowest(self):
        _, weakest = _pick_dimensions(80, 60, 40)
        assert weakest == "drug-likeness"

    def test_adme_can_be_strongest(self):
        strongest, _ = _pick_dimensions(40, 90, 60)
        assert strongest == "ADME"

    def test_all_equal(self):
        strongest, weakest = _pick_dimensions(50, 50, 50)
        # Any dimension is valid when all equal
        assert strongest in ("affinity", "ADME", "drug-likeness")
        assert weakest in ("affinity", "ADME", "drug-likeness")


# ═══════════════════════════════════════════════════════════════════════════════
# calculate_score_breakdown
# ═══════════════════════════════════════════════════════════════════════════════

class TestCalculateScoreBreakdown:

    def test_returns_score_breakdown_type(self):
        docking = _make_docking(-7.0)
        props = _make_props()
        result = calculate_score_breakdown(docking, props)
        assert hasattr(result, "total_score")
        assert hasattr(result, "affinity_score")
        assert hasattr(result, "adme_score")
        assert hasattr(result, "druglikeness_score")

    def test_total_score_in_range(self):
        docking = _make_docking(-7.0)
        props = _make_props()
        result = calculate_score_breakdown(docking, props)
        assert 0.0 <= result.total_score <= 100.0

    def test_sub_scores_in_range(self):
        docking = _make_docking(-7.0)
        props = _make_props()
        result = calculate_score_breakdown(docking, props)
        assert 0.0 <= result.affinity_score <= 100.0
        assert 0.0 <= result.adme_score <= 100.0
        assert 0.0 <= result.druglikeness_score <= 100.0

    def test_weights_sum_to_one(self):
        docking = _make_docking(-7.0)
        props = _make_props()
        result = calculate_score_breakdown(docking, props)
        total_weights = result.weight_affinity + result.weight_adme + result.weight_druglikeness
        assert abs(total_weights - 1.0) < 1e-9

    def test_total_is_weighted_sum(self):
        """Total score = affinity*w_a + adme*w_adme + druglikeness*w_dl."""
        docking = _make_docking(-7.0)
        props = _make_props()
        result = calculate_score_breakdown(docking, props)

        expected = (
            result.affinity_score * result.weight_affinity
            + result.adme_score * result.weight_adme
            + result.druglikeness_score * result.weight_druglikeness
        )
        # clamp_score does rounding
        assert abs(result.total_score - round(max(0, min(100, expected)), 2)) < 0.1

    def test_perfect_molecule_high_score(self):
        """Molécula con buena afinidad + propiedades perfectas → score alto."""
        docking = _make_docking(-9.0)
        props = _make_props(log_p=2.5, tpsa=60.0, rotatable_bonds=2)
        result = calculate_score_breakdown(docking, props)
        assert result.total_score > 80.0

    def test_poor_affinity_lowers_total(self):
        """Afinidad débil (-4) reduce total significativamente."""
        good_docking = _make_docking(-9.0)
        bad_docking = _make_docking(-4.0)
        props = _make_props()
        good_result = calculate_score_breakdown(good_docking, props)
        bad_result = calculate_score_breakdown(bad_docking, props)
        assert good_result.total_score > bad_result.total_score

    def test_poor_properties_lower_total(self):
        """Propiedades malas reducen total."""
        docking = _make_docking(-7.0)
        good_props = _make_props()
        bad_props = _make_props(
            molecular_weight=600.0,
            log_p=7.0,
            tpsa=200.0,
            rotatable_bonds=15,
            lipinski_pass=False,
            veber_pass=False,
        )
        good_result = calculate_score_breakdown(docking, good_props)
        bad_result = calculate_score_breakdown(docking, bad_props)
        assert good_result.total_score > bad_result.total_score

    def test_has_strongest_and_weakest(self):
        docking = _make_docking(-7.0)
        props = _make_props()
        result = calculate_score_breakdown(docking, props)
        assert result.strongest_dimension in ("affinity", "ADME", "drug-likeness")
        assert result.weakest_dimension in ("affinity", "ADME", "drug-likeness")

    def test_has_improvement_hint(self):
        docking = _make_docking(-7.0)
        props = _make_props()
        result = calculate_score_breakdown(docking, props)
        assert isinstance(result.improvement_hint, str)
        assert len(result.improvement_hint) > 10


# ═══════════════════════════════════════════════════════════════════════════════
# _build_improvement_hint
# ═══════════════════════════════════════════════════════════════════════════════

class TestBuildImprovementHint:

    def test_affinity_hint(self):
        props = _make_props()
        hint = _build_improvement_hint(props, "affinity")
        assert "afinidad" in hint.lower() or "complementariedad" in hint.lower()

    def test_adme_hint_high_logp(self):
        props = _make_props(log_p=6.0, lipinski_pass=False)
        hint = _build_improvement_hint(props, "ADME")
        assert "logp" in hint.lower() or "lipofilia" in hint.lower()

    def test_adme_hint_high_tpsa(self):
        props = _make_props(tpsa=150.0, veber_pass=False)
        hint = _build_improvement_hint(props, "ADME")
        assert "tpsa" in hint.lower()

    def test_druglikeness_hint_with_violations(self):
        props = _make_props(
            molecular_weight=600.0,
            lipinski_pass=False,
        )
        hint = _build_improvement_hint(props, "drug-likeness")
        assert "violaci" in hint.lower() or "mejora" in hint.lower()

    def test_hint_is_nonempty_string(self):
        props = _make_props()
        for dim in ["affinity", "ADME", "drug-likeness"]:
            hint = _build_improvement_hint(props, dim)
            assert isinstance(hint, str) and len(hint) > 5


# ═══════════════════════════════════════════════════════════════════════════════
# Edge cases
# ═══════════════════════════════════════════════════════════════════════════════

class TestEdgeCases:

    def test_very_strong_affinity(self):
        """Afinidad -12 kcal/mol → affinity_score=100."""
        docking = _make_docking(-12.0)
        props = _make_props()
        result = calculate_score_breakdown(docking, props)
        assert result.affinity_score == 100.0

    def test_zero_affinity_rejected(self):
        """Afinidad 0 kcal/mol es científicamente inválida para Vina — debe rechazarse."""
        import pytest
        with pytest.raises(Exception):
            _make_docking(0.0)

    def test_borderline_affinity(self):
        """Afinidad exactamente -4 kcal/mol → affinity_score=0."""
        docking = _make_docking(-4.0)
        props = _make_props()
        result = calculate_score_breakdown(docking, props)
        assert result.affinity_score == 0.0
