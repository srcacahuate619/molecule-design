"""
tests/unit/test_calibration_health.py

Tests para el Calibration Health Monitor.
Verifica:
  - Checks locales sin red (staleness, normalization, grid, panel, software)
  - Generación correcta de reportes
  - Detección de problemas conocidos
  - Comportamiento gracioso cuando faltan datos
"""

from __future__ import annotations

import json
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest


def _has_rdkit() -> bool:
    """Check if RDKit is available in the current environment."""
    try:
        from rdkit import Chem  # noqa: F401
        return True
    except ImportError:
        return False


from scoring.calibration_health import (
    CalibrationHealthMonitor,
    CalibrationHealthReport,
    CheckStatus,
    CheckSeverity,
    HealthCheckResult,
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
def benchmark_data() -> dict:
    """Simulated benchmark results."""
    return {
        "results": [
            {"smiles": "CC(=O)Oc1ccccc1C(=O)O", "best_affinity_kcal": -5.8},
            {"smiles": "Cn1c(=O)c2c(ncn2C)n(C)c1=O", "best_affinity_kcal": -5.2},
            {"smiles": "CC(C)Cc1ccc(cc1)C(C)C(=O)O", "best_affinity_kcal": -7.1},
            {"smiles": "c1ccc2c(c1)cc1ccc3cccc4ccc2c1c34", "best_affinity_kcal": -8.5},
            {"smiles": "CCO", "best_affinity_kcal": -3.1},  # Outside normalization range
        ],
    }


@pytest.fixture
def panel_data_small() -> dict:
    """Panel with fewer than 30 molecules."""
    return {
        "records": [
            {"canonical_smiles": f"C{'C' * i}", "p_activity": 5.0 + i * 0.1}
            for i in range(16)
        ],
        "criteria": {
            "tier_counts": {
                "strong_lt_100nM": 8,
                "moderate_100nM_10uM": 8,
                "weak_gt_10uM": 0,
            },
        },
    }


@pytest.fixture
def panel_data_good() -> dict:
    """Panel with 40+ molecules and good range."""
    records = []
    for i in range(42):
        records.append({
            "canonical_smiles": f"C{'C' * i}O",
            "p_activity": 4.5 + i * 0.12,  # Range: 4.5 to ~9.5 = 5 log units
        })
    return {
        "records": records,
        "criteria": {
            "tier_counts": {
                "strong_lt_100nM": 14,
                "moderate_100nM_10uM": 14,
                "weak_gt_10uM": 14,
            },
        },
    }


@pytest.fixture
def tmp_benchmark(benchmark_data: dict) -> Path:
    """Write benchmark data to temp file."""
    tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
    json.dump(benchmark_data, tmp)
    tmp.close()
    return Path(tmp.name)


@pytest.fixture
def tmp_panel_small(panel_data_small: dict) -> Path:
    tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
    json.dump(panel_data_small, tmp)
    tmp.close()
    return Path(tmp.name)


@pytest.fixture
def tmp_panel_good(panel_data_good: dict) -> Path:
    tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
    json.dump(panel_data_good, tmp)
    tmp.close()
    return Path(tmp.name)


# ── HealthCheckReport Tests ─────────────────────────────────────────────────


class TestHealthCheckReport:
    def test_empty_report_is_pass(self) -> None:
        report = CalibrationHealthReport(
            generated_at=datetime.now(UTC).isoformat(),
            registry_hash="abc123",
        )
        assert report.overall_status == CheckStatus.PASS

    def test_adding_pass_keeps_pass(self) -> None:
        report = CalibrationHealthReport(
            generated_at=datetime.now(UTC).isoformat(),
            registry_hash="abc123",
        )
        report.add_check(HealthCheckResult(
            check_name="test",
            status=CheckStatus.PASS,
            severity=CheckSeverity.INFO,
            message="All good",
        ))
        assert report.overall_status == CheckStatus.PASS

    def test_adding_warning_degrades_overall(self) -> None:
        report = CalibrationHealthReport(
            generated_at=datetime.now(UTC).isoformat(),
            registry_hash="abc123",
        )
        report.add_check(HealthCheckResult(
            check_name="ok",
            status=CheckStatus.PASS,
            severity=CheckSeverity.INFO,
            message="Fine",
        ))
        report.add_check(HealthCheckResult(
            check_name="warn",
            status=CheckStatus.WARNING,
            severity=CheckSeverity.MEDIUM,
            message="Heads up",
        ))
        assert report.overall_status == CheckStatus.WARNING

    def test_adding_fail_degrades_overall(self) -> None:
        report = CalibrationHealthReport(
            generated_at=datetime.now(UTC).isoformat(),
            registry_hash="abc123",
        )
        report.add_check(HealthCheckResult(
            check_name="warn",
            status=CheckStatus.WARNING,
            severity=CheckSeverity.MEDIUM,
            message="Warn",
        ))
        report.add_check(HealthCheckResult(
            check_name="fail",
            status=CheckStatus.FAIL,
            severity=CheckSeverity.HIGH,
            message="Failed",
        ))
        assert report.overall_status == CheckStatus.FAIL

    def test_to_dict_structure(self) -> None:
        report = CalibrationHealthReport(
            generated_at=datetime.now(UTC).isoformat(),
            registry_hash="abc123",
        )
        report.add_check(HealthCheckResult(
            check_name="test",
            status=CheckStatus.PASS,
            severity=CheckSeverity.INFO,
            message="OK",
        ))
        d = report.to_dict()
        assert "overall_status" in d
        assert "n_checks" in d
        assert d["n_pass"] == 1
        assert d["n_checks"] == 1


# ── CalibrationHealthMonitor Local Checks ───────────────────────────────────


class TestCalibrationHealthMonitorLocal:
    def test_local_checks_pass_on_fresh_registry(
        self, default_registry: SciConfigRegistry,
    ) -> None:
        monitor = CalibrationHealthMonitor(default_registry)
        report = monitor.run_local_checks()
        # Fresh registry should have no staleness issues
        staleness_check = next(
            (c for c in report.checks if c.check_name == "parameter_staleness"),
            None,
        )
        assert staleness_check is not None
        assert staleness_check.status == CheckStatus.PASS

    def test_staleness_detected_for_old_params(self) -> None:
        registry = SciConfigRegistry()
        old_time = (datetime.now(UTC) - timedelta(days=200)).isoformat()
        registry.register(SciParameter(
            name="old_target",
            category=ParameterCategory.TARGET,
            unit="PDB ID",
            description="Old target",
            max_age_days=90,
            versions=[ParameterVersion(
                value="XXXX",
                version=1,
                adopted_at=old_time,
                reason="Very old",
                reference=ParameterReference(source="test"),
            )],
        ))

        monitor = CalibrationHealthMonitor(registry)
        report = monitor.run_local_checks()
        staleness_check = next(
            c for c in report.checks if c.check_name == "parameter_staleness"
        )
        assert staleness_check.status == CheckStatus.WARNING

    def test_normalization_coverage_without_benchmark(
        self, default_registry: SciConfigRegistry,
    ) -> None:
        monitor = CalibrationHealthMonitor(default_registry)
        report = monitor.run_local_checks()
        norm_check = next(
            c for c in report.checks if c.check_name == "normalization_coverage"
        )
        assert norm_check.status == CheckStatus.UNABLE

    def test_normalization_coverage_with_benchmark_in_range(
        self, default_registry: SciConfigRegistry,
    ) -> None:
        """Benchmark with all affinities within [-10, -4] → PASS."""
        data = {
            "results": [
                {"best_affinity_kcal": -6.0},
                {"best_affinity_kcal": -7.5},
                {"best_affinity_kcal": -8.0},
            ],
        }
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(data, f)
            f.flush()
            monitor = CalibrationHealthMonitor(default_registry, benchmark_path=f.name)
            report = monitor.run_local_checks()

        norm_check = next(
            c for c in report.checks if c.check_name == "normalization_coverage"
        )
        assert norm_check.status == CheckStatus.PASS

    def test_normalization_coverage_warns_on_out_of_range(
        self, default_registry: SciConfigRegistry, tmp_benchmark: Path,
    ) -> None:
        """Benchmark with -3.1 outside [-10, -4] → WARNING."""
        monitor = CalibrationHealthMonitor(default_registry, benchmark_path=tmp_benchmark)
        report = monitor.run_local_checks()
        norm_check = next(
            c for c in report.checks if c.check_name == "normalization_coverage"
        )
        assert norm_check.status == CheckStatus.WARNING
        assert "above worst" in norm_check.details.get("issues", [""])[0].lower() or \
               "n_above_worst" in str(norm_check.details)

    def test_grid_adequacy_pass_for_25(
        self, default_registry: SciConfigRegistry,
    ) -> None:
        monitor = CalibrationHealthMonitor(default_registry)
        report = monitor.run_local_checks()
        grid_check = next(
            c for c in report.checks if c.check_name == "grid_adequacy"
        )
        assert grid_check.status == CheckStatus.PASS

    def test_grid_adequacy_fail_for_small_grid(self) -> None:
        registry = SciConfigRegistry()
        registry.register(SciParameter(
            name="grid_size",
            category=ParameterCategory.GRID_BOX,
            unit="Å",
            description="Small grid",
            versions=[ParameterVersion(
                value=[15.0, 15.0, 15.0],
                version=1,
                adopted_at=datetime.now(UTC).isoformat(),
                reason="Too small",
                reference=ParameterReference(source="test"),
            )],
        ))
        monitor = CalibrationHealthMonitor(registry)
        report = monitor.run_local_checks()
        grid_check = next(
            c for c in report.checks if c.check_name == "grid_adequacy"
        )
        assert grid_check.status == CheckStatus.FAIL

    def test_panel_quality_warns_on_small_panel(
        self, default_registry: SciConfigRegistry, tmp_panel_small: Path,
    ) -> None:
        monitor = CalibrationHealthMonitor(
            default_registry, panel_path=tmp_panel_small,
        )
        report = monitor.run_local_checks()
        panel_check = next(
            c for c in report.checks if c.check_name == "panel_quality"
        )
        assert panel_check.status == CheckStatus.WARNING

    def test_panel_quality_pass_on_good_panel(
        self, default_registry: SciConfigRegistry, tmp_panel_good: Path,
    ) -> None:
        monitor = CalibrationHealthMonitor(
            default_registry, panel_path=tmp_panel_good,
        )
        report = monitor.run_local_checks()
        panel_check = next(
            c for c in report.checks if c.check_name == "panel_quality"
        )
        assert panel_check.status == CheckStatus.PASS

    @pytest.mark.skipif(
        not _has_rdkit(),
        reason="RDKit not available (expected on Python 3.14 local env)",
    )
    def test_software_versions_pass(
        self, default_registry: SciConfigRegistry,
    ) -> None:
        """RDKit should be installed in the test environment."""
        monitor = CalibrationHealthMonitor(default_registry)
        report = monitor.run_local_checks()
        sw_check = next(
            c for c in report.checks if c.check_name == "software_versions"
        )
        assert sw_check.status == CheckStatus.PASS
        assert "rdkit" in sw_check.details.get("versions", {})

    def test_report_save_and_load(
        self, default_registry: SciConfigRegistry,
    ) -> None:
        monitor = CalibrationHealthMonitor(default_registry)
        report = monitor.run_local_checks()

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "health_report.json"
            report.save(path)

            loaded = json.loads(path.read_text())
            assert "overall_status" in loaded
            assert "checks" in loaded
            assert isinstance(loaded["checks"], list)

    def test_pdb_check_skipped_in_local_mode(
        self, default_registry: SciConfigRegistry,
    ) -> None:
        monitor = CalibrationHealthMonitor(default_registry)
        report = monitor.run_local_checks()
        pdb_check = next(
            c for c in report.checks if c.check_name == "better_pdb_structure"
        )
        assert pdb_check.status == CheckStatus.SKIPPED
