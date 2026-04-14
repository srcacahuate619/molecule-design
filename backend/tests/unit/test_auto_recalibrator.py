"""
tests/unit/test_auto_recalibrator.py

Tests para el Auto-Recalibrator Pipeline.
Verifica:
  - Generación de propuestas de recalibración
  - Propuestas correctas según el estado de los checks
  - Re-anclaje de normalización basado en benchmark
  - Aplicación de cambios no destructivos
  - Manejo gracioso de datos faltantes
"""

from __future__ import annotations

import json
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from scoring.auto_recalibrator import (
    AutoRecalibrator,
    ProposalAction,
    ProposalPriority,
    ProposedChange,
    RecalibrationProposal,
)
from scoring.sci_config_registry import (
    ParameterCategory,
    ParameterReference,
    ParameterVersion,
    SciConfigRegistry,
    SciParameter,
)


# ── Fixtures ────────────────────────────────────────────────────────────────


@pytest.fixture
def default_registry() -> SciConfigRegistry:
    return SciConfigRegistry.create_default()


@pytest.fixture
def benchmark_in_range() -> dict:
    """Benchmark with all affinities within [-10, -4] and wide enough range."""
    return {
        "results": [
            {"best_affinity_kcal": -9.5},
            {"best_affinity_kcal": -8.5},
            {"best_affinity_kcal": -7.5},
            {"best_affinity_kcal": -6.5},
            {"best_affinity_kcal": -5.5},
            {"best_affinity_kcal": -4.5},
        ],
    }


@pytest.fixture
def benchmark_out_of_range() -> dict:
    """Benchmark with affinities outside [-10, -4] suggesting re-anchoring."""
    return {
        "results": [
            {"best_affinity_kcal": -12.5},
            {"best_affinity_kcal": -11.0},
            {"best_affinity_kcal": -9.0},
            {"best_affinity_kcal": -7.5},
            {"best_affinity_kcal": -6.0},
            {"best_affinity_kcal": -4.5},
            {"best_affinity_kcal": -3.0},
            {"best_affinity_kcal": -2.5},
        ],
    }


def _write_json(data: dict) -> Path:
    tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
    json.dump(data, tmp)
    tmp.close()
    return Path(tmp.name)


# ── RecalibrationProposal Tests ─────────────────────────────────────────────


class TestRecalibrationProposal:
    def test_empty_proposal(self) -> None:
        p = RecalibrationProposal(
            generated_at=datetime.now(UTC).isoformat(),
            registry_hash_before="abc",
            health_report_summary={},
        )
        assert p.n_changes == 0
        assert not p.has_critical_changes

    def test_add_change(self) -> None:
        p = RecalibrationProposal(
            generated_at=datetime.now(UTC).isoformat(),
            registry_hash_before="abc",
            health_report_summary={},
        )
        p.add_change(ProposedChange(
            action=ProposalAction.UPDATE_PARAMETER,
            priority=ProposalPriority.HIGH,
            parameter_name="test",
            current_value=1,
            proposed_value=2,
            reason="Test",
            evidence="Test",
        ))
        assert p.n_changes == 1
        assert not p.has_critical_changes

    def test_has_critical_changes(self) -> None:
        p = RecalibrationProposal(
            generated_at=datetime.now(UTC).isoformat(),
            registry_hash_before="abc",
            health_report_summary={},
        )
        p.add_change(ProposedChange(
            action=ProposalAction.NO_ACTION,
            priority=ProposalPriority.CRITICAL,
            parameter_name=None,
            current_value=None,
            proposed_value=None,
            reason="Critical issue",
            evidence="Missing dependency",
        ))
        assert p.has_critical_changes

    def test_to_dict_structure(self) -> None:
        p = RecalibrationProposal(
            generated_at=datetime.now(UTC).isoformat(),
            registry_hash_before="abc",
            health_report_summary={"overall_status": "pass"},
        )
        d = p.to_dict()
        assert "n_proposed_changes" in d
        assert "has_critical_changes" in d
        assert "health_report_summary" in d

    def test_save_and_load(self) -> None:
        p = RecalibrationProposal(
            generated_at=datetime.now(UTC).isoformat(),
            registry_hash_before="abc",
            health_report_summary={},
            overall_recommendation="No changes needed.",
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "proposal.json"
            p.save(path)
            loaded = json.loads(path.read_text())
            assert loaded["overall_recommendation"] == "No changes needed."


# ── AutoRecalibrator Tests ──────────────────────────────────────────────────


class TestAutoRecalibrator:
    def test_local_run_with_fresh_registry(
        self, default_registry: SciConfigRegistry,
    ) -> None:
        """Fresh registry, no benchmark/panel → mostly informational."""
        recalibrator = AutoRecalibrator(registry=default_registry)
        proposal = recalibrator.run_local()
        assert proposal is not None
        assert proposal.n_changes >= 0
        assert proposal.overall_recommendation

    def test_local_run_proposes_panel_expansion_for_small_panel(
        self, default_registry: SciConfigRegistry,
    ) -> None:
        panel = {
            "records": [{"canonical_smiles": f"C{'C'*i}", "p_activity": 6.0} for i in range(10)],
            "criteria": {"tier_counts": {"strong_lt_100nM": 5, "moderate_100nM_10uM": 5, "weak_gt_10uM": 0}},
        }
        panel_path = _write_json(panel)
        recalibrator = AutoRecalibrator(
            registry=default_registry, panel_path=panel_path,
        )
        proposal = recalibrator.run_local()
        expand_changes = [
            c for c in proposal.proposed_changes if c.action == ProposalAction.EXPAND_PANEL
        ]
        assert len(expand_changes) >= 1

    def test_normalization_reanchor_when_out_of_range(
        self, default_registry: SciConfigRegistry, benchmark_out_of_range: dict,
    ) -> None:
        """Benchmark with affinities well outside [-10,-4] → proposes re-anchoring."""
        benchmark_path = _write_json(benchmark_out_of_range)
        recalibrator = AutoRecalibrator(
            registry=default_registry, benchmark_path=benchmark_path,
        )
        proposal = recalibrator.run_local()

        # Should propose normalization update
        norm_changes = [
            c for c in proposal.proposed_changes
            if c.parameter_name and "normalization" in c.parameter_name
        ]
        assert len(norm_changes) >= 1

    def test_no_reanchor_when_in_range(
        self, default_registry: SciConfigRegistry, benchmark_in_range: dict,
    ) -> None:
        """Benchmark within [-10,-4] → no re-anchoring needed."""
        benchmark_path = _write_json(benchmark_in_range)
        recalibrator = AutoRecalibrator(
            registry=default_registry, benchmark_path=benchmark_path,
        )
        proposal = recalibrator.run_local()

        # Should NOT propose normalization re-anchoring (all within range)
        norm_reanchor = [
            c for c in proposal.proposed_changes
            if c.parameter_name and "normalization_range" in c.parameter_name
            and c.action == ProposalAction.UPDATE_PARAMETER
        ]
        assert len(norm_reanchor) == 0

    def test_apply_non_destructive_does_not_apply_human_review(
        self, default_registry: SciConfigRegistry,
    ) -> None:
        """Changes requiring human review should NOT be auto-applied."""
        recalibrator = AutoRecalibrator(registry=default_registry)
        proposal = RecalibrationProposal(
            generated_at=datetime.now(UTC).isoformat(),
            registry_hash_before="abc",
            health_report_summary={},
        )
        proposal.add_change(ProposedChange(
            action=ProposalAction.EVALUATE_NEW_PDB,
            priority=ProposalPriority.HIGH,
            parameter_name="target_pdb_id",
            current_value="7E2Y",
            proposed_value="XXXX",
            reason="Better resolution",
            evidence="RCSB PDB",
            requires_human_review=True,
        ))
        applied = recalibrator.apply_non_destructive_changes(proposal)
        assert len(applied) == 0
        # Registry unchanged
        assert default_registry.get_value("target_pdb_id") == "7E2Y"

    def test_apply_non_destructive_applies_safe_changes(
        self, default_registry: SciConfigRegistry,
    ) -> None:
        """Safe parameter updates should be applied to registry."""
        recalibrator = AutoRecalibrator(registry=default_registry)
        proposal = RecalibrationProposal(
            generated_at=datetime.now(UTC).isoformat(),
            registry_hash_before="abc",
            health_report_summary={},
        )

        # Check that affinity_normalization_best exists before trying to update
        param = default_registry.get("affinity_normalization_best")
        assert param is not None

        proposal.add_change(ProposedChange(
            action=ProposalAction.UPDATE_PARAMETER,
            priority=ProposalPriority.HIGH,
            parameter_name="affinity_normalization_best",
            current_value=-10.0,
            proposed_value=-11.5,
            reason="Benchmark shows tighter binders",
            evidence="P5=-11.2 from 40 molecules",
            requires_benchmark=False,
            requires_human_review=False,
        ))
        applied = recalibrator.apply_non_destructive_changes(proposal)
        assert len(applied) == 1
        assert default_registry.get_value("affinity_normalization_best") == -11.5

    def test_overall_recommendation_no_changes(
        self, default_registry: SciConfigRegistry, benchmark_in_range: dict,
    ) -> None:
        """When no changes needed, recommendation says so."""
        benchmark_path = _write_json(benchmark_in_range)
        # Also provide a good panel
        panel = {
            "records": [{"canonical_smiles": f"C{'C'*i}O", "p_activity": 4.0+i*0.15} for i in range(42)],
            "criteria": {"tier_counts": {"strong_lt_100nM": 14, "moderate_100nM_10uM": 14, "weak_gt_10uM": 14}},
        }
        panel_path = _write_json(panel)

        recalibrator = AutoRecalibrator(
            registry=default_registry,
            benchmark_path=benchmark_path,
            panel_path=panel_path,
        )
        proposal = recalibrator.run_local()
        # With fresh registry, good benchmark, and good panel → minimal changes
        assert proposal.overall_recommendation

    def test_impact_estimation(self) -> None:
        recalibrator = AutoRecalibrator()
        proposal = RecalibrationProposal(
            generated_at=datetime.now(UTC).isoformat(),
            registry_hash_before="abc",
            health_report_summary={},
        )
        proposal.add_change(ProposedChange(
            action=ProposalAction.EVALUATE_NEW_PDB,
            priority=ProposalPriority.HIGH,
            parameter_name="target_pdb_id",
            current_value="7E2Y",
            proposed_value="XXXX",
            reason="Test",
            evidence="Test",
        ))
        impact = recalibrator._estimate_impact(proposal)
        assert "recalculated" in impact.lower()

    def test_staleness_generates_rerun_proposals(self) -> None:
        """Stale parameters should generate RE_RUN_BENCHMARK proposals."""
        registry = SciConfigRegistry()
        old_time = (datetime.now(UTC) - timedelta(days=200)).isoformat()
        registry.register(SciParameter(
            name="affinity_normalization_best",
            category=ParameterCategory.NORMALIZATION,
            unit="kcal/mol",
            description="Old normalization",
            max_age_days=90,
            tags=["calibration-dependent"],
            versions=[ParameterVersion(
                value=-10.0,
                version=1,
                adopted_at=old_time,
                reason="Old",
                reference=ParameterReference(source="test"),
            )],
        ))
        # Need grid_size for grid check not to error
        registry.register(SciParameter(
            name="grid_size",
            category=ParameterCategory.GRID_BOX,
            unit="Å",
            description="Grid",
            versions=[ParameterVersion(
                value=[25.0, 25.0, 25.0],
                version=1,
                adopted_at=datetime.now(UTC).isoformat(),
                reason="Current",
                reference=ParameterReference(source="test"),
            )],
        ))

        recalibrator = AutoRecalibrator(registry=registry)
        proposal = recalibrator.run_local()

        rerun_changes = [
            c for c in proposal.proposed_changes
            if c.action == ProposalAction.RE_RUN_BENCHMARK
        ]
        assert len(rerun_changes) >= 1
