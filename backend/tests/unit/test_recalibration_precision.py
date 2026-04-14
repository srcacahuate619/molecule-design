"""
tests/unit/test_recalibration_precision.py

Precision tests for scientific pipeline recalibration.

These tests enforce that ALL scoring formulas produce results with
< 1% relative error (or < 0.01 absolute error for near-zero values)
compared to hand-computed expected values.

Coverage:
  1. normalize_affinity — all regions (capped low/high, linear interpolation)
  2. normalize_logp — optimum, decay, boundaries
  3. normalize_tpsa — 4 zones (near-zero, sweet, decay, far)
  4. normalize_rotatable_bonds — 3 zones (excellent, moderate, high)
  5. calculate_adme_score — composite 40/40/20 weighting
  6. calculate_druglikeness_score — all 6 penalty paths + gradual zones
  7. calculate_score_breakdown — end-to-end weight application
  8. Scoring weights sum to exactly 1.0
  9. Registry-code consistency
  10. Benchmark data integrity

Error criterion: |actual - expected| / max(expected, 0.01) < 0.01  (1%)
For zero-expected values: actual must also be 0 (absolute 0.01 tolerance).
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import pytest

from core.models import DockingResult, PhysicochemicalProperties
from scoring.engine import calculate_score_breakdown
from scoring.normalizer import (
    calculate_adme_score,
    calculate_druglikeness_score,
    clamp_score,
    normalize_affinity,
    normalize_logp,
    normalize_rotatable_bonds,
    normalize_tpsa,
)

ARTIFACTS_DIR = Path("artifacts")


# ═══════════════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════════════

def _relative_error(actual: float, expected: float) -> float:
    """Relative error with protection against zero division."""
    if expected == 0.0:
        return 0.0 if actual == 0.0 else abs(actual)
    return abs(actual - expected) / abs(expected)


def _assert_precision(
    actual: float,
    expected: float,
    label: str,
    max_relative_error: float = 0.01,  # 1%
    max_absolute_error: float = 0.01,
) -> None:
    """Assert value matches expected within <1% relative or <0.01 absolute error."""
    abs_err = abs(actual - expected)
    rel_err = _relative_error(actual, expected)
    assert (
        abs_err <= max_absolute_error or rel_err <= max_relative_error
    ), (
        f"{label}: actual={actual:.6f}, expected={expected:.6f}, "
        f"abs_err={abs_err:.6f}, rel_err={rel_err:.4%}"
    )


def _mk_props(
    mw: float = 250.0,
    lp: float = 2.0,
    tp: float = 60.0,
    hbd: int = 2,
    hba: int = 4,
    rot: int = 3,
) -> PhysicochemicalProperties:
    """Create PhysicochemicalProperties with correct Lipinski/Veber pass flags."""
    lip = not (mw > 500 or lp > 5.0 or hbd > 5 or hba > 10)
    veb = not (rot > 10 or tp > 140)
    return PhysicochemicalProperties(
        molecular_weight=mw,
        log_p=lp,
        tpsa=tp,
        hbd=hbd,
        hba=hba,
        rotatable_bonds=rot,
        heavy_atom_count=18,
        ring_count=2,
        qed=0.7,
        lipinski_pass=lip,
        veber_pass=veb,
    )


def _mk_docking(aff: float) -> DockingResult:
    return DockingResult(
        best_affinity=aff,
        poses=[{"rank": 1, "affinity": aff, "rmsd_lb": 0.0, "rmsd_ub": 0.0}],
        poses_file_path="test/pose.sdf",
    )


# ═══════════════════════════════════════════════════════════════════════════════
# 1. normalize_affinity precision
# ═══════════════════════════════════════════════════════════════════════════════

class TestAffinityPrecision:
    """
    normalize_affinity: linear interpolation [-10, -4] -> [100, 0].
    Formula: ((worst - x) / (worst - best)) * 100
    with best=-10, worst=-4, clamped to [0, 100].
    """

    @pytest.mark.parametrize(
        "affinity,expected",
        [
            (-10.0, 100.0),
            (-4.0, 0.0),
            (-7.0, 50.0),
            (-8.0, 66.67),
            (-5.0, 16.67),
            (-6.0, 33.33),
            (-9.0, 83.33),
            (-12.0, 100.0),  # capped
            (-1.0, 0.0),     # capped
            (0.0, 0.0),      # capped
            (5.0, 0.0),      # positive = no binding
            (-5.848, 30.80), # aspirin benchmark
            (-5.814, 30.23), # caffeine benchmark
            (-6.98, 49.67),  # ibuprofen benchmark
        ],
    )
    def test_affinity_precision(self, affinity: float, expected: float) -> None:
        actual = normalize_affinity(affinity)
        _assert_precision(actual, expected, f"normalize_affinity({affinity})")

    def test_affinity_monotonicity(self) -> None:
        """More negative affinity -> higher score (strictly monotonic in [-10, -4])."""
        values = [-4.0, -5.0, -6.0, -7.0, -8.0, -9.0, -10.0]
        scores = [normalize_affinity(v) for v in values]
        for i in range(len(scores) - 1):
            assert scores[i] < scores[i + 1], (
                f"Monotonicity violated: score({values[i]})={scores[i]} "
                f">= score({values[i+1]})={scores[i+1]}"
            )

    def test_affinity_all_in_0_100(self) -> None:
        """Every possible input maps to [0, 100]."""
        for val in range(-20, 10):
            result = normalize_affinity(float(val))
            assert 0.0 <= result <= 100.0


# ═══════════════════════════════════════════════════════════════════════════════
# 2. normalize_logp precision
# ═══════════════════════════════════════════════════════════════════════════════

class TestLogPPrecision:
    """
    normalize_logp: optimum at 2.5, linear decay to 0 at distance >= 3.5.
    Formula: (1 - |logP - 2.5| / 3.5) * 100, clamped to [0, 100].
    """

    @pytest.mark.parametrize(
        "logp,expected",
        [
            (2.5, 100.0),
            (6.0, 0.0),
            (-1.0, 0.0),
            (4.0, 57.14),
            (1.0, 57.14),
            (0.0, 28.57),
            (5.0, 28.57),
            (3.0, 85.71),
            (2.0, 85.71),
            (-2.0, 0.0),
            (8.0, 0.0),
        ],
    )
    def test_logp_precision(self, logp: float, expected: float) -> None:
        actual = normalize_logp(logp)
        _assert_precision(actual, expected, f"normalize_logp({logp})")

    def test_logp_symmetry(self) -> None:
        """Equidistant from optimum -> same score."""
        for d in [0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5]:
            low = normalize_logp(2.5 - d)
            high = normalize_logp(2.5 + d)
            assert abs(low - high) < 0.01, f"Asymmetry at distance {d}"


# ═══════════════════════════════════════════════════════════════════════════════
# 3. normalize_tpsa precision
# ═══════════════════════════════════════════════════════════════════════════════

class TestTPSAPrecision:
    """
    normalize_tpsa: 4 zones.
    <20: linear ramp from 0.
    20-90: 100 (sweet spot).
    90-140: linear decay to 0.
    >=140: 0.
    """

    @pytest.mark.parametrize(
        "tpsa,expected",
        [
            (0.0, 0.0),
            (10.0, 50.0),
            (20.0, 100.0),
            (55.0, 100.0),
            (90.0, 100.0),
            (115.0, 50.0),
            (140.0, 0.0),
            (200.0, 0.0),
            (5.0, 25.0),
            (15.0, 75.0),
            (100.0, 80.0),
            (130.0, 20.0),
        ],
    )
    def test_tpsa_precision(self, tpsa: float, expected: float) -> None:
        actual = normalize_tpsa(tpsa)
        _assert_precision(actual, expected, f"normalize_tpsa({tpsa})")


# ═══════════════════════════════════════════════════════════════════════════════
# 4. normalize_rotatable_bonds precision
# ═══════════════════════════════════════════════════════════════════════════════

class TestRotatableBondsPrecision:
    """
    normalize_rotatable_bonds: 3 zones.
    0-3: 100.
    4-10: gentle decay (40 points over 7 steps).
    11-14: steep decay (60 points over 5 steps).
    >=15: 0.
    """

    @pytest.mark.parametrize(
        "rot,expected",
        [
            (0, 100.0),
            (3, 100.0),
            (5, 88.57),
            (7, 77.14),
            (10, 60.0),
            (12, 36.0),
            (15, 0.0),
            (20, 0.0),
        ],
    )
    def test_rot_precision(self, rot: int, expected: float) -> None:
        actual = normalize_rotatable_bonds(rot)
        _assert_precision(actual, expected, f"normalize_rotatable_bonds({rot})")

    def test_rot_monotonically_decreasing(self) -> None:
        scores = [normalize_rotatable_bonds(i) for i in range(0, 21)]
        for i in range(len(scores) - 1):
            assert scores[i] >= scores[i + 1]


# ═══════════════════════════════════════════════════════════════════════════════
# 5. ADME composite precision
# ═══════════════════════════════════════════════════════════════════════════════

class TestADMEPrecision:
    """
    calculate_adme_score = logP_norm * 0.4 + TPSA_norm * 0.4 + RotBonds_norm * 0.2
    """

    @pytest.mark.parametrize(
        "lp,tp,rot,expected_adme",
        [
            (2.5, 60.0, 3, 100.0),         # perfect
            (7.0, 60.0, 3, 60.0),           # bad logP
            (2.5, 150.0, 3, 60.0),          # bad TPSA
            (2.5, 60.0, 15, 80.0),          # bad RotBonds
            (1.19, 63.6, 3, 85.03),         # aspirin-like
            (4.0, 100.0, 8, 69.14),         # mixed
        ],
    )
    def test_adme_precision(
        self, lp: float, tp: float, rot: int, expected_adme: float
    ) -> None:
        props = _mk_props(lp=lp, tp=tp, rot=rot)
        actual = calculate_adme_score(props)
        # Verify by recomputing
        l = normalize_logp(lp)
        t = normalize_tpsa(tp)
        r = normalize_rotatable_bonds(rot)
        hand = round(max(0.0, min(100.0, l * 0.4 + t * 0.4 + r * 0.2)), 2)
        _assert_precision(actual, hand, f"ADME({lp},{tp},{rot})")


# ═══════════════════════════════════════════════════════════════════════════════
# 6. Drug-likeness precision
# ═══════════════════════════════════════════════════════════════════════════════

class TestDruglikenessPrecision:
    """
    calculate_druglikeness_score: base 100, penalties for Lipinski/Veber violations
    with gradual zones near thresholds.
    """

    @pytest.mark.parametrize(
        "mw,lp,tp,hbd,hba,rot,expected",
        [
            # Perfect molecule
            (250.0, 2.0, 60.0, 2, 4, 3, 100.0),
            # Single Lipinski violations (hard)
            (550.0, 2.0, 60.0, 2, 4, 3, 80.0),   # MW > 500
            (250.0, 6.0, 60.0, 2, 4, 3, 80.0),   # logP > 5
            (250.0, 2.0, 60.0, 7, 4, 3, 80.0),   # HBD > 5
            (250.0, 2.0, 60.0, 2, 12, 3, 80.0),  # HBA > 10
            # Gradual penalties
            (475.0, 2.0, 60.0, 2, 4, 3, 95.0),   # MW in [450, 500]
            (250.0, 4.7, 60.0, 2, 4, 3, 96.0),   # logP in [4.5, 5.0]
            (250.0, 2.0, 60.0, 2, 9, 3, 95.0),   # HBA in [8, 10]
            # Veber violations
            (250.0, 2.0, 60.0, 2, 4, 12, 90.0),  # RotBonds > 10
            (250.0, 2.0, 150.0, 2, 4, 3, 90.0),  # TPSA > 140
            # Gradual Veber
            (250.0, 2.0, 130.0, 2, 4, 3, 97.5),  # TPSA in [120, 140]
            (250.0, 2.0, 60.0, 2, 4, 9, 97.5),   # RotBonds in [8, 10]
            # Multiple violations clamped at 0
            (600.0, 7.0, 160.0, 8, 13, 16, 0.0),
        ],
    )
    def test_druglikeness_precision(
        self, mw: float, lp: float, tp: float,
        hbd: int, hba: int, rot: int, expected: float,
    ) -> None:
        props = _mk_props(mw=mw, lp=lp, tp=tp, hbd=hbd, hba=hba, rot=rot)
        actual = calculate_druglikeness_score(props)
        _assert_precision(actual, expected, f"DL(mw={mw},lp={lp},tp={tp},hbd={hbd},hba={hba},rot={rot})")


# ═══════════════════════════════════════════════════════════════════════════════
# 7. Composite score precision
# ═══════════════════════════════════════════════════════════════════════════════

class TestCompositeScorePrecision:
    """
    total = aff_score * 0.45 + adme_score * 0.30 + dl_score * 0.25
    Verify the composite score equals weighted sum of sub-scores.
    """

    @pytest.mark.parametrize(
        "aff,mw,lp,tp,hbd,hba,rot",
        [
            (-5.848, 180.16, 1.19, 63.6, 1, 4, 3),    # aspirin
            (-5.814, 194.08, -0.07, 58.44, 0, 6, 0),   # caffeine
            (-6.98, 206.13, 3.5, 37.3, 1, 2, 4),       # ibuprofen
            (-9.0, 350.0, 2.5, 60.0, 2, 5, 3),         # ideal drug-like
            (-7.0, 300.0, 3.0, 80.0, 3, 6, 5),         # moderate
            (-3.0, 600.0, 7.0, 160.0, 8, 13, 16),      # terrible
            (-10.0, 250.0, 2.5, 60.0, 2, 4, 3),        # best affinity
            (-4.0, 250.0, 2.5, 60.0, 2, 4, 3),         # worst affinity
        ],
    )
    def test_composite_equals_weighted_sum(
        self, aff: float, mw: float, lp: float,
        tp: float, hbd: int, hba: int, rot: int,
    ) -> None:
        props = _mk_props(mw=mw, lp=lp, tp=tp, hbd=hbd, hba=hba, rot=rot)
        dock = _mk_docking(aff)
        result = calculate_score_breakdown(dock, props)

        expected_total = clamp_score(
            result.affinity_score * 0.45
            + result.adme_score * 0.30
            + result.druglikeness_score * 0.25
        )
        _assert_precision(
            result.total_score,
            expected_total,
            f"composite(aff={aff})",
        )

    def test_all_subscores_bounded(self) -> None:
        """Every sub-score and total must be in [0, 100]."""
        test_vals = [
            (-9.0, 300.0, 2.5, 60.0, 2, 4, 3),
            (-5.0, 500.0, 5.0, 140.0, 5, 10, 10),
            (-3.0, 800.0, 8.0, 200.0, 10, 15, 20),
        ]
        for aff, mw, lp, tp, hbd, hba, rot in test_vals:
            props = _mk_props(mw=mw, lp=lp, tp=tp, hbd=hbd, hba=hba, rot=rot)
            dock = _mk_docking(aff)
            r = calculate_score_breakdown(dock, props)
            for name, val in [
                ("affinity_score", r.affinity_score),
                ("adme_score", r.adme_score),
                ("druglikeness_score", r.druglikeness_score),
                ("total_score", r.total_score),
            ]:
                assert 0.0 <= val <= 100.0, f"{name}={val} out of [0,100]"


# ═══════════════════════════════════════════════════════════════════════════════
# 8. Weight integrity
# ═══════════════════════════════════════════════════════════════════════════════

class TestWeightIntegrity:
    def test_weights_sum_to_one(self) -> None:
        from core.config import get_settings
        s = get_settings()
        total = s.score_weight_affinity + s.score_weight_adme + s.score_weight_druglikeness
        assert abs(total - 1.0) < 1e-9, f"Weights sum to {total}, expected 1.0"

    def test_weight_ordering(self) -> None:
        from core.config import get_settings
        s = get_settings()
        assert s.score_weight_affinity >= s.score_weight_adme >= s.score_weight_druglikeness

    def test_weight_values(self) -> None:
        from core.config import get_settings
        s = get_settings()
        assert s.score_weight_affinity == 0.45
        assert s.score_weight_adme == 0.30
        assert s.score_weight_druglikeness == 0.25


# ═══════════════════════════════════════════════════════════════════════════════
# 9. Registry-code consistency
# ═══════════════════════════════════════════════════════════════════════════════

class TestRegistryCodeConsistency:
    """Verify hardcoded values in normalizer match the SciConfigRegistry."""

    def test_affinity_normalization_best(self) -> None:
        from scoring.sci_config_registry import SciConfigRegistry
        registry = SciConfigRegistry.create_default()
        assert registry.get_value("affinity_normalization_best") == -10.0

    def test_affinity_normalization_worst(self) -> None:
        from scoring.sci_config_registry import SciConfigRegistry
        registry = SciConfigRegistry.create_default()
        assert registry.get_value("affinity_normalization_worst") == -4.0

    def test_grid_center_matches_config(self) -> None:
        from scoring.sci_config_registry import SciConfigRegistry
        from core.config import get_settings
        registry = SciConfigRegistry.create_default()
        s = get_settings()
        reg_center = registry.get_value("grid_center")
        code_center = [s.vina_center_x, s.vina_center_y, s.vina_center_z]
        assert reg_center == code_center

    def test_grid_size_matches_config(self) -> None:
        from scoring.sci_config_registry import SciConfigRegistry
        from core.config import get_settings
        registry = SciConfigRegistry.create_default()
        s = get_settings()
        reg_size = registry.get_value("grid_size")
        code_size = [s.vina_size_x, s.vina_size_y, s.vina_size_z]
        assert reg_size == code_size

    def test_target_pdb_matches_config(self) -> None:
        from scoring.sci_config_registry import SciConfigRegistry
        from core.config import get_settings
        registry = SciConfigRegistry.create_default()
        s = get_settings()
        assert registry.get_value("target_pdb_id") == s.default_target_pdb_id

    def test_score_weights_match_config(self) -> None:
        from scoring.sci_config_registry import SciConfigRegistry
        from core.config import get_settings
        registry = SciConfigRegistry.create_default()
        s = get_settings()
        reg = registry.get_value("score_weights")
        assert reg["affinity"] == s.score_weight_affinity
        assert reg["adme"] == s.score_weight_adme
        assert reg["druglikeness"] == s.score_weight_druglikeness


# ═══════════════════════════════════════════════════════════════════════════════
# 10. Benchmark data integrity
# ═══════════════════════════════════════════════════════════════════════════════

class TestBenchmarkIntegrity:
    """Verify the benchmark reference panel data is consistent."""

    @pytest.fixture
    def benchmark(self) -> dict | None:
        path = ARTIFACTS_DIR / "benchmark_reference_panel.json"
        if not path.exists():
            pytest.skip("Benchmark artifact not found")
        return json.loads(path.read_text(encoding="utf-8"))

    def test_benchmark_target_is_7e2y(self, benchmark: dict) -> None:
        assert benchmark["protocol"]["target_pdb_id"] == "7E2Y"

    def test_benchmark_deterministic(self, benchmark: dict) -> None:
        """Each molecule should produce identical affinity across runs."""
        for name in ["aspirin", "caffeine", "ibuprofen"]:
            runs = [r for r in benchmark["runs"] if r["name"] == name]
            affinities = [r["best_affinity"] for r in runs]
            assert len(set(affinities)) == 1, (
                f"{name} not deterministic: {affinities}"
            )

    def test_benchmark_affinities_in_normalization_range(self, benchmark: dict) -> None:
        """All benchmark affinities must fall within [-10, -4]."""
        for run in benchmark["runs"]:
            aff = run["best_affinity"]
            assert -10.0 <= aff <= -4.0, (
                f"{run['name']} affinity {aff} outside normalization range [-10, -4]"
            )

    def test_benchmark_scores_consistent(self, benchmark: dict) -> None:
        """Stored affinity_scores must match recomputed values."""
        for run in benchmark["runs"]:
            stored = run["score_affinity"]
            recomputed = normalize_affinity(run["best_affinity"])
            _assert_precision(
                stored, recomputed,
                f"benchmark {run['name']} affinity_score",
            )


# ═══════════════════════════════════════════════════════════════════════════════
# 11. External calibration validity
# ═══════════════════════════════════════════════════════════════════════════════

class TestExternalCalibrationValidity:
    """Verify external calibration report status."""

    @pytest.fixture
    def ecr(self) -> dict | None:
        path = ARTIFACTS_DIR / "external_calibration_report.json"
        if not path.exists():
            pytest.skip("External calibration report not found")
        return json.loads(path.read_text(encoding="utf-8"))

    def test_external_cal_flagged_if_wrong_target(self, ecr: dict) -> None:
        """If report uses wrong target, it must be flagged INVALID."""
        target = ecr["protocol"]["target_pdb_id"]
        if target != "7E2Y":
            assert "INVALIDATED" in ecr, (
                f"External calibration against {target} (not 7E2Y) "
                f"is NOT flagged as INVALIDATED. This is dangerous."
            )

    def test_recalibration_proposal_flagged_if_invalid_source(self) -> None:
        """If proposal is based on invalid data, it must be flagged."""
        path = ARTIFACTS_DIR / "recalibration_proposal.json"
        if not path.exists():
            pytest.skip("Recalibration proposal not found")
        proposal = json.loads(path.read_text(encoding="utf-8"))
        for change in proposal.get("proposed_changes", []):
            if change.get("parameter_name") == "affinity_normalization_range":
                proposed = change.get("proposed_value", {})
                if isinstance(proposed, dict):
                    best = proposed.get("best", -10.0)
                    if best > -3.0:  # Nonsensical range
                        assert "INVALIDATED" in proposal, (
                            f"Proposal with range best={best} is nonsensical "
                            f"but NOT flagged as INVALIDATED."
                        )
