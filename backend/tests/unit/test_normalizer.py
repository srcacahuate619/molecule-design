"""
tests/unit/test_normalizer.py

Tests para scoring/normalizer.py — funciones de normalización del pipeline científico.

Cada función de normalización convierte métricas crudas a escala 0-100.
Los tests verifican:
1. Valores en los extremos (boundaries).
2. Monotonía (más negativo = mejor para afinidad, óptimo para logP/TPSA).
3. Clamping a [0, 100].
4. Valores intermedios calculados correctamente.
"""

import pytest

from scoring.normalizer import (
    clamp_score,
    normalize_affinity,
    normalize_logp,
    normalize_tpsa,
    normalize_rotatable_bonds,
    calculate_adme_score,
    calculate_druglikeness_score,
)
from core.models import PhysicochemicalProperties


# ═══════════════════════════════════════════════════════════════════════════════
# clamp_score
# ═══════════════════════════════════════════════════════════════════════════════

class TestClampScore:
    def test_value_in_range_unchanged(self):
        assert clamp_score(50.0) == 50.0

    def test_zero_stays_zero(self):
        assert clamp_score(0.0) == 0.0

    def test_hundred_stays_hundred(self):
        assert clamp_score(100.0) == 100.0

    def test_negative_clamped_to_zero(self):
        assert clamp_score(-5.0) == 0.0

    def test_above_hundred_clamped(self):
        assert clamp_score(150.0) == 100.0

    def test_result_is_rounded(self):
        result = clamp_score(33.333333)
        assert result == 33.33


# ═══════════════════════════════════════════════════════════════════════════════
# normalize_affinity
# ═══════════════════════════════════════════════════════════════════════════════

class TestNormalizeAffinity:
    """
    Rango calibrado: [-10, -4] kcal/mol → [100, 0].
    Referencia: Trott & Olson (2010), valores típicos de Vina para GPCRs.
    """

    def test_excellent_affinity_is_100(self):
        """Afinidad ≤ -10 kcal/mol → 100."""
        assert normalize_affinity(-10.0) == 100.0

    def test_better_than_excellent_is_100(self):
        """Afinidad mejor que -10 también → 100 (capped)."""
        assert normalize_affinity(-12.0) == 100.0

    def test_poor_affinity_is_0(self):
        """Afinidad ≥ -4 kcal/mol → 0."""
        assert normalize_affinity(-4.0) == 0.0

    def test_worse_than_poor_is_0(self):
        """Afinidad peor que -4 → 0 (capped)."""
        assert normalize_affinity(-1.0) == 0.0

    def test_positive_affinity_is_0(self):
        """Valores positivos (no-binding) → 0."""
        assert normalize_affinity(0.0) == 0.0
        assert normalize_affinity(5.0) == 0.0

    def test_midpoint(self):
        """Punto medio -7 → 50."""
        result = normalize_affinity(-7.0)
        assert result == 50.0

    def test_typical_drug_value(self):
        """
        -8 kcal/mol es un valor típico para un buen ligando de GPCR.
        Debe dar ~66.67.
        """
        result = normalize_affinity(-8.0)
        expected = (((-4.0) - (-8.0)) / ((-4.0) - (-10.0))) * 100.0
        assert abs(result - expected) < 0.01

    def test_weak_binding(self):
        """
        -5 kcal/mol → binding débil, score bajo pero no cero.
        """
        result = normalize_affinity(-5.0)
        expected = (((-4.0) - (-5.0)) / ((-4.0) - (-10.0))) * 100.0
        assert abs(result - expected) < 0.01

    def test_monotonically_increasing_with_stronger_affinity(self):
        """Más negativo = mejor afinidad = mayor score."""
        scores = [normalize_affinity(a) for a in [-4, -5, -6, -7, -8, -9, -10]]
        for i in range(len(scores) - 1):
            assert scores[i] < scores[i + 1], (
                f"normalize_affinity debe ser monótona: "
                f"score({-4-i})={scores[i]} >= score({-5-i})={scores[i+1]}"
            )

    def test_result_always_in_range(self):
        """Todos los valores posibles deben estar en [0, 100]."""
        for val in [-20, -15, -10, -7, -4, -1, 0, 5]:
            result = normalize_affinity(val)
            assert 0.0 <= result <= 100.0, f"normalize_affinity({val}) = {result} fuera de rango"


# ═══════════════════════════════════════════════════════════════════════════════
# normalize_logp
# ═══════════════════════════════════════════════════════════════════════════════

class TestNormalizeLogP:
    """logP óptimo en 2.5, decae linealmente a 0 a distancia ≥ 3.5."""

    def test_optimum_is_100(self):
        assert normalize_logp(2.5) == 100.0

    def test_far_positive_is_0(self):
        assert normalize_logp(6.0) == 0.0

    def test_far_negative_is_0(self):
        assert normalize_logp(-1.0) == 0.0

    def test_symmetric_around_optimum(self):
        """Equidistant values from 2.5 give same score."""
        assert normalize_logp(1.0) == normalize_logp(4.0)

    def test_intermediate_value(self):
        """logP=4.0 → distancia 1.5 del óptimo → score ~57.14."""
        result = normalize_logp(4.0)
        expected = (1.0 - (1.5 / 3.5)) * 100.0
        assert abs(result - expected) < 0.1

    def test_result_in_range(self):
        for val in [-5, -1, 0, 1, 2.5, 4, 5, 6, 10]:
            result = normalize_logp(val)
            assert 0.0 <= result <= 100.0


# ═══════════════════════════════════════════════════════════════════════════════
# normalize_tpsa
# ═══════════════════════════════════════════════════════════════════════════════

class TestNormalizeTPSA:
    """TPSA: 20-90 Å² = 100, 0 at 0 or ≥140."""

    def test_sweet_spot_lower_boundary(self):
        assert normalize_tpsa(20.0) == 100.0

    def test_sweet_spot_upper_boundary(self):
        assert normalize_tpsa(90.0) == 100.0

    def test_sweet_spot_middle(self):
        assert normalize_tpsa(60.0) == 100.0

    def test_high_tpsa_is_0(self):
        assert normalize_tpsa(140.0) == 0.0

    def test_very_high_tpsa_is_0(self):
        assert normalize_tpsa(200.0) == 0.0

    def test_very_low_tpsa(self):
        assert normalize_tpsa(0.0) == 0.0

    def test_intermediate_high_tpsa(self):
        """TPSA=115 → en zona 90-140 → ~50%."""
        result = normalize_tpsa(115.0)
        expected = ((140.0 - 115.0) / 50.0) * 100.0
        assert abs(result - expected) < 0.1

    def test_result_in_range(self):
        for val in [0, 10, 20, 50, 90, 110, 140, 200]:
            result = normalize_tpsa(val)
            assert 0.0 <= result <= 100.0


# ═══════════════════════════════════════════════════════════════════════════════
# normalize_rotatable_bonds
# ═══════════════════════════════════════════════════════════════════════════════

class TestNormalizeRotatableBonds:

    def test_zero_bonds_is_100(self):
        assert normalize_rotatable_bonds(0) == 100.0

    def test_three_bonds_is_100(self):
        assert normalize_rotatable_bonds(3) == 100.0

    def test_fifteen_or_more_is_0(self):
        assert normalize_rotatable_bonds(15) == 0.0
        assert normalize_rotatable_bonds(20) == 0.0

    def test_monotonically_decreasing(self):
        scores = [normalize_rotatable_bonds(i) for i in range(0, 16)]
        for i in range(len(scores) - 1):
            assert scores[i] >= scores[i + 1]

    def test_result_in_range(self):
        for val in range(0, 25):
            result = normalize_rotatable_bonds(val)
            assert 0.0 <= result <= 100.0


# ═══════════════════════════════════════════════════════════════════════════════
# calculate_adme_score
# ═══════════════════════════════════════════════════════════════════════════════

class TestCalculateADMEScore:

    @staticmethod
    def _make_props(**overrides) -> PhysicochemicalProperties:
        """Helper que genera un PhysicochemicalProperties con defaults drug-like."""
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

    def test_perfect_adme_is_100(self):
        """logP=2.5, TPSA=60, rotBonds=3 → score ~100."""
        props = self._make_props(log_p=2.5, tpsa=60.0, rotatable_bonds=3)
        score = calculate_adme_score(props)
        assert score == 100.0

    def test_bad_logp_lowers_score(self):
        good = self._make_props(log_p=2.5)
        bad = self._make_props(log_p=7.0, lipinski_pass=False)
        assert calculate_adme_score(good) > calculate_adme_score(bad)

    def test_bad_tpsa_lowers_score(self):
        good = self._make_props(tpsa=60.0)
        bad = self._make_props(tpsa=150.0)
        assert calculate_adme_score(good) > calculate_adme_score(bad)

    def test_many_rotatable_bonds_lowers_score(self):
        good = self._make_props(rotatable_bonds=2)
        bad = self._make_props(rotatable_bonds=15)
        assert calculate_adme_score(good) > calculate_adme_score(bad)

    def test_result_in_range(self):
        props = self._make_props()
        score = calculate_adme_score(props)
        assert 0.0 <= score <= 100.0


# ═══════════════════════════════════════════════════════════════════════════════
# calculate_druglikeness_score
# ═══════════════════════════════════════════════════════════════════════════════

class TestCalculateDruglikenessScore:

    @staticmethod
    def _make_props(**overrides) -> PhysicochemicalProperties:
        defaults = dict(
            molecular_weight=250.0,
            log_p=2.0,
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

    def test_perfect_molecule_is_100(self):
        """Molécula que cumple todo → 100."""
        props = self._make_props()
        score = calculate_druglikeness_score(props)
        assert score == 100.0

    def test_lipinski_violation_reduces_score(self):
        """MW > 500 → penalización de 20 puntos."""
        props = self._make_props(
            molecular_weight=550.0,
            lipinski_pass=False,
        )
        score = calculate_druglikeness_score(props)
        assert score == 80.0

    def test_gradual_penalty_near_mw_threshold(self):
        """MW=475 → en zona gradual [450, 500] → penalización parcial."""
        props = self._make_props(molecular_weight=475.0)
        score = calculate_druglikeness_score(props)
        assert 90.0 < score < 100.0, f"Expected gradual penalty, got {score}"

    def test_no_penalty_well_below_threshold(self):
        """MW=300 → lejos del umbral → sin penalización."""
        props = self._make_props(molecular_weight=300.0)
        score = calculate_druglikeness_score(props)
        assert score == 100.0

    def test_multiple_violations(self):
        """MW > 500 + logP > 5 → -20 -20 = 60."""
        props = self._make_props(
            molecular_weight=550.0,
            log_p=6.0,
            lipinski_pass=False,
        )
        score = calculate_druglikeness_score(props)
        assert score == 60.0

    def test_veber_violation_reduces_score(self):
        """RotBonds > 10 → -10 puntos."""
        props = self._make_props(
            rotatable_bonds=12,
            veber_pass=False,
        )
        score = calculate_druglikeness_score(props)
        assert score == 90.0

    def test_result_never_negative(self):
        """Muchas violaciones → clamped a 0, nunca negativo."""
        props = self._make_props(
            molecular_weight=800.0,
            log_p=8.0,
            hbd=10,
            hba=15,
            rotatable_bonds=15,
            tpsa=200.0,
            lipinski_pass=False,
            veber_pass=False,
        )
        score = calculate_druglikeness_score(props)
        assert score >= 0.0

    def test_result_in_range(self):
        props = self._make_props()
        score = calculate_druglikeness_score(props)
        assert 0.0 <= score <= 100.0
