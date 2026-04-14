"""Tests unitarios del sistema de scoring del MVP."""

import pytest

from core.models import DockingResult, PhysicochemicalProperties
from scoring.engine import calculate_score_breakdown
from scoring.normalizer import (
    calculate_adme_score,
    calculate_druglikeness_score,
    normalize_affinity,
    normalize_logp,
    normalize_rotatable_bonds,
    normalize_tpsa,
)


@pytest.fixture
def sample_properties() -> PhysicochemicalProperties:
    return PhysicochemicalProperties(
        molecular_weight=180.16,
        log_p=1.19,
        tpsa=63.6,
        hbd=1,
        hba=4,
        rotatable_bonds=3,
        heavy_atom_count=13,
        ring_count=1,
        qed=0.55,
        lipinski_pass=True,
        veber_pass=True,
    )


@pytest.fixture
def sample_docking() -> DockingResult:
    return DockingResult(
        best_affinity=-8.5,
        poses=[
            {"rank": 1, "affinity": -8.5, "rmsd_lb": 0.0, "rmsd_ub": 0.0},
            {"rank": 2, "affinity": -7.1, "rmsd_lb": 1.8, "rmsd_ub": 3.2},
        ],
        poses_file_path="poses/hash/7E2Y/poses.sdf",
    )


def test_affinity_normalization_midrange():
    # With range [-10, -4]: (-8 - (-4)) / (-10 - (-4)) * 100 = 66.67
    score = normalize_affinity(-8.0)
    assert score == pytest.approx(66.67, abs=0.01)


def test_affinity_normalization_best_cap():
    assert normalize_affinity(-13.5) == 100.0


def test_affinity_normalization_worst_cap():
    assert normalize_affinity(-3.0) == 0.0


def test_logp_optimum_is_high_score():
    assert normalize_logp(2.5) == 100.0


def test_tpsa_ideal_range_scores_max():
    assert normalize_tpsa(60.0) == 100.0


def test_rotatable_bonds_penalizes_excess():
    assert normalize_rotatable_bonds(12) < normalize_rotatable_bonds(3)


def test_adme_score_is_bounded(sample_properties):
    score = calculate_adme_score(sample_properties)
    assert 0 <= score <= 100


def test_druglikeness_full_compliance_is_100(sample_properties):
    assert calculate_druglikeness_score(sample_properties) == 100.0


def test_breakdown_returns_valid_total(sample_properties, sample_docking):
    breakdown = calculate_score_breakdown(sample_docking, sample_properties)
    assert 0 <= breakdown.total_score <= 100
    assert breakdown.affinity_score >= 0
    assert breakdown.adme_score >= 0
    assert breakdown.druglikeness_score >= 0


def test_breakdown_identifies_dimensions(sample_properties, sample_docking):
    breakdown = calculate_score_breakdown(sample_docking, sample_properties)
    assert breakdown.strongest_dimension in {"affinity", "ADME", "drug-likeness"}
    assert breakdown.weakest_dimension in {"affinity", "ADME", "drug-likeness"}


def test_breakdown_has_improvement_hint(sample_properties, sample_docking):
    breakdown = calculate_score_breakdown(sample_docking, sample_properties)
    assert isinstance(breakdown.improvement_hint, str)
    assert len(breakdown.improvement_hint) > 0


def test_bad_properties_reduce_druglikeness_score():
    bad = PhysicochemicalProperties(
        molecular_weight=650.0,
        log_p=6.2,
        tpsa=155.0,
        hbd=7,
        hba=12,
        rotatable_bonds=14,
        heavy_atom_count=42,
        ring_count=3,
        qed=0.08,
        lipinski_pass=False,
        veber_pass=False,
    )
    assert calculate_druglikeness_score(bad) < 100.0