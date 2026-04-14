"""
tests/unit/test_sci_config_registry.py

Tests para el Scientific Configuration Registry.
Verifica:
  - Creación y registro de parámetros
  - Versionamiento y superseding
  - Detección de staleness
  - Serialización/deserialización JSON
  - Creación del registry default con todos los parámetros del MVP
"""

from __future__ import annotations

import json
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from scoring.sci_config_registry import (
    ParameterCategory,
    ParameterReference,
    ParameterVersion,
    SciConfigRegistry,
    SciParameter,
    StalenessReason,
)


# ── Fixtures ────────────────────────────────────────────────────────────────


@pytest.fixture
def empty_registry() -> SciConfigRegistry:
    return SciConfigRegistry()


@pytest.fixture
def sample_reference() -> ParameterReference:
    return ParameterReference(
        source="Test et al. (2024)",
        doi="10.1234/test",
        method="Unit test fixture",
        notes="For testing only",
    )


@pytest.fixture
def sample_param(sample_reference: ParameterReference) -> SciParameter:
    return SciParameter(
        name="test_param",
        category=ParameterCategory.NORMALIZATION,
        unit="kcal/mol",
        description="A test parameter",
        max_age_days=30,
        tags=["test"],
        versions=[ParameterVersion(
            value=-10.0,
            version=1,
            adopted_at=datetime.now(UTC).isoformat(),
            reason="Initial value for testing",
            reference=sample_reference,
        )],
    )


@pytest.fixture
def default_registry() -> SciConfigRegistry:
    return SciConfigRegistry.create_default()


# ── SciParameter Tests ──────────────────────────────────────────────────────


class TestSciParameter:
    def test_current_version_returns_active(self, sample_param: SciParameter) -> None:
        cv = sample_param.current_version
        assert cv is not None
        assert cv.value == -10.0
        assert cv.version == 1
        assert cv.is_active()

    def test_current_value_shortcut(self, sample_param: SciParameter) -> None:
        assert sample_param.current_value == -10.0

    def test_add_version_supersedes_previous(
        self, sample_param: SciParameter, sample_reference: ParameterReference,
    ) -> None:
        new_ver = sample_param.add_version(
            value=-12.0,
            reason="Updated based on new benchmark",
            reference=sample_reference,
        )
        assert new_ver.version == 2
        assert new_ver.value == -12.0
        assert new_ver.is_active()

        # Previous version is now superseded
        assert sample_param.versions[0].superseded_at is not None
        assert not sample_param.versions[0].is_active()

        # Current value is the new one
        assert sample_param.current_value == -12.0

    def test_days_since_last_update_is_recent(self, sample_param: SciParameter) -> None:
        days = sample_param.days_since_last_update()
        assert days is not None
        assert days < 1.0  # Just created

    def test_is_stale_when_recent(self, sample_param: SciParameter) -> None:
        assert not sample_param.is_stale()  # max_age_days=30, just created

    def test_is_stale_when_old(self, sample_reference: ParameterReference) -> None:
        old_time = (datetime.now(UTC) - timedelta(days=100)).isoformat()
        param = SciParameter(
            name="old_param",
            category=ParameterCategory.TARGET,
            unit="PDB ID",
            description="Old parameter",
            max_age_days=30,
            versions=[ParameterVersion(
                value="OLD",
                version=1,
                adopted_at=old_time,
                reason="Old test value",
                reference=sample_reference,
            )],
        )
        assert param.is_stale()

    def test_is_stale_when_no_versions(self) -> None:
        param = SciParameter(
            name="empty",
            category=ParameterCategory.TARGET,
            unit="",
            description="No versions",
        )
        assert param.is_stale()
        assert param.current_value is None


# ── SciConfigRegistry Tests ─────────────────────────────────────────────────


class TestSciConfigRegistry:
    def test_register_and_get(
        self, empty_registry: SciConfigRegistry, sample_param: SciParameter,
    ) -> None:
        empty_registry.register(sample_param)
        retrieved = empty_registry.get("test_param")
        assert retrieved is not None
        assert retrieved.name == "test_param"
        assert retrieved.current_value == -10.0

    def test_register_duplicate_raises(
        self, empty_registry: SciConfigRegistry, sample_param: SciParameter,
    ) -> None:
        empty_registry.register(sample_param)
        with pytest.raises(ValueError, match="already registered"):
            empty_registry.register(sample_param)

    def test_get_value_shortcut(
        self, empty_registry: SciConfigRegistry, sample_param: SciParameter,
    ) -> None:
        empty_registry.register(sample_param)
        assert empty_registry.get_value("test_param") == -10.0
        assert empty_registry.get_value("nonexistent") is None

    def test_get_by_category(
        self, empty_registry: SciConfigRegistry, sample_param: SciParameter,
    ) -> None:
        empty_registry.register(sample_param)
        normalization_params = empty_registry.get_by_category(ParameterCategory.NORMALIZATION)
        assert len(normalization_params) == 1
        assert normalization_params[0].name == "test_param"

        target_params = empty_registry.get_by_category(ParameterCategory.TARGET)
        assert len(target_params) == 0

    def test_update_existing(
        self,
        empty_registry: SciConfigRegistry,
        sample_param: SciParameter,
        sample_reference: ParameterReference,
    ) -> None:
        empty_registry.register(sample_param)
        new_ver = empty_registry.update(
            "test_param",
            value=-8.0,
            reason="Recalibrated",
            reference=sample_reference,
        )
        assert new_ver.value == -8.0
        assert empty_registry.get_value("test_param") == -8.0

    def test_update_nonexistent_raises(
        self, empty_registry: SciConfigRegistry, sample_reference: ParameterReference,
    ) -> None:
        with pytest.raises(KeyError, match="not found"):
            empty_registry.update("ghost", value=1, reason="test", reference=sample_reference)

    def test_generate_hash_deterministic(
        self, empty_registry: SciConfigRegistry, sample_param: SciParameter,
    ) -> None:
        empty_registry.register(sample_param)
        h1 = empty_registry.generate_hash()
        h2 = empty_registry.generate_hash()
        assert h1 == h2
        assert len(h1) == 64  # SHA-256 hex

    def test_generate_hash_changes_on_update(
        self,
        empty_registry: SciConfigRegistry,
        sample_param: SciParameter,
        sample_reference: ParameterReference,
    ) -> None:
        empty_registry.register(sample_param)
        h_before = empty_registry.generate_hash()
        empty_registry.update("test_param", value=-8.0, reason="test", reference=sample_reference)
        h_after = empty_registry.generate_hash()
        assert h_before != h_after

    def test_get_stale_parameters_empty_when_fresh(
        self, empty_registry: SciConfigRegistry, sample_param: SciParameter,
    ) -> None:
        empty_registry.register(sample_param)
        stale = empty_registry.get_stale_parameters()
        assert len(stale) == 0

    def test_get_stale_parameters_detects_old(
        self, empty_registry: SciConfigRegistry,
    ) -> None:
        old_time = (datetime.now(UTC) - timedelta(days=100)).isoformat()
        param = SciParameter(
            name="old_param",
            category=ParameterCategory.TARGET,
            unit="",
            description="Old",
            max_age_days=30,
            versions=[ParameterVersion(
                value="OLD",
                version=1,
                adopted_at=old_time,
                reason="Old",
                reference=ParameterReference(source="test"),
            )],
        )
        empty_registry.register(param)
        stale = empty_registry.get_stale_parameters()
        assert len(stale) == 1
        assert stale[0][0].name == "old_param"
        assert stale[0][1] == StalenessReason.AGE

    def test_summary(
        self, empty_registry: SciConfigRegistry, sample_param: SciParameter,
    ) -> None:
        empty_registry.register(sample_param)
        s = empty_registry.summary()
        assert s["total_parameters"] == 1
        assert s["stale_parameters"] == 0
        assert s["healthy_parameters"] == 1
        assert "normalization" in s["categories"]

    def test_to_dict_structure(
        self, empty_registry: SciConfigRegistry, sample_param: SciParameter,
    ) -> None:
        empty_registry.register(sample_param)
        d = empty_registry.to_dict()
        assert "registry_version" in d
        assert "config_hash" in d
        assert "parameters" in d
        assert "test_param" in d["parameters"]

    def test_save_and_load_roundtrip(
        self, empty_registry: SciConfigRegistry, sample_param: SciParameter,
    ) -> None:
        empty_registry.register(sample_param)

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "registry.json"
            empty_registry.save(path)

            loaded = SciConfigRegistry.load(path)
            assert loaded.get_value("test_param") == -10.0
            assert loaded.generate_hash() == empty_registry.generate_hash()

    def test_save_and_load_with_multiple_versions(
        self,
        empty_registry: SciConfigRegistry,
        sample_param: SciParameter,
        sample_reference: ParameterReference,
    ) -> None:
        empty_registry.register(sample_param)
        empty_registry.update("test_param", value=-8.0, reason="v2", reference=sample_reference)

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "registry.json"
            empty_registry.save(path)

            loaded = SciConfigRegistry.load(path)
            param = loaded.get("test_param")
            assert param is not None
            assert len(param.versions) == 2
            assert param.current_value == -8.0
            assert param.versions[0].superseded_at is not None


# ── Default Registry Tests ──────────────────────────────────────────────────


class TestDefaultRegistry:
    """Verifica que el registry por defecto está completo y consistente."""

    def test_creates_successfully(self, default_registry: SciConfigRegistry) -> None:
        assert default_registry is not None

    def test_has_required_parameters(self, default_registry: SciConfigRegistry) -> None:
        required = [
            "target_pdb_id",
            "target_chain",
            "target_resolution_angstrom",
            "grid_center",
            "grid_size",
            "vina_exhaustiveness_production",
            "vina_exhaustiveness_calibration",
            "vina_seed",
            "affinity_normalization_best",
            "affinity_normalization_worst",
            "score_weights",
            "lipinski_thresholds",
            "veber_thresholds",
            "molecular_weight_range",
        ]
        for name in required:
            param = default_registry.get(name)
            assert param is not None, f"Missing required parameter: {name}"
            assert param.current_value is not None, f"No active value for: {name}"

    def test_target_is_7e2y(self, default_registry: SciConfigRegistry) -> None:
        assert default_registry.get_value("target_pdb_id") == "7E2Y"

    def test_grid_center_is_sro_centroid(self, default_registry: SciConfigRegistry) -> None:
        center = default_registry.get_value("grid_center")
        assert isinstance(center, list)
        assert len(center) == 3
        assert abs(center[0] - 103.03) < 0.01

    def test_grid_size_is_25(self, default_registry: SciConfigRegistry) -> None:
        size = default_registry.get_value("grid_size")
        assert isinstance(size, list)
        assert all(s == 25.0 for s in size)

    def test_normalization_range(self, default_registry: SciConfigRegistry) -> None:
        best = default_registry.get_value("affinity_normalization_best")
        worst = default_registry.get_value("affinity_normalization_worst")
        assert best == -10.0
        assert worst == -4.0
        assert best < worst  # best is more negative

    def test_score_weights_sum_to_one(self, default_registry: SciConfigRegistry) -> None:
        weights = default_registry.get_value("score_weights")
        assert isinstance(weights, dict)
        total = sum(weights.values())
        assert abs(total - 1.0) < 1e-9

    def test_all_parameters_have_references(self, default_registry: SciConfigRegistry) -> None:
        for name, param in default_registry.get_all().items():
            cv = param.current_version
            assert cv is not None, f"No active version for {name}"
            assert cv.reference is not None, f"No reference for {name}"
            assert cv.reference.source, f"Empty source for {name}"

    def test_no_stale_parameters_on_creation(self, default_registry: SciConfigRegistry) -> None:
        stale = default_registry.get_stale_parameters()
        assert len(stale) == 0, f"Stale params on fresh creation: {stale}"

    def test_hash_is_deterministic(self, default_registry: SciConfigRegistry) -> None:
        h1 = default_registry.generate_hash()
        # Create another instance
        other = SciConfigRegistry.create_default()
        h2 = other.generate_hash()
        # Note: timestamps differ, but hash is based on values only
        assert h1 == h2

    def test_all_categories_represented(self, default_registry: SciConfigRegistry) -> None:
        categories_found = set()
        for param in default_registry.get_all().values():
            categories_found.add(param.category)
        expected = {
            ParameterCategory.TARGET,
            ParameterCategory.GRID_BOX,
            ParameterCategory.DOCKING_ENGINE,
            ParameterCategory.NORMALIZATION,
            ParameterCategory.SCORING_WEIGHTS,
            ParameterCategory.ADME_RULES,
            ParameterCategory.VALIDATION,
        }
        assert categories_found == expected

    def test_serialization_roundtrip(self, default_registry: SciConfigRegistry) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "default_registry.json"
            default_registry.save(path)
            loaded = SciConfigRegistry.load(path)

            # All params present
            for name in default_registry.get_all():
                assert loaded.get(name) is not None
                assert (
                    loaded.get_value(name) == default_registry.get_value(name)
                ), f"Value mismatch for {name}"
