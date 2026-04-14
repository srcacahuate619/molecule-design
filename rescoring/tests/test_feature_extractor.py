"""
tests/test_feature_extractor.py

Tests unitarios para el extractor de features 3D.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from feature_extractor import FeatureExtractor, INTERACTION_FEATURES


class TestFeatureExtractorInit:
    """Tests de inicialización y disponibilidad de ODDT."""

    def test_init_does_not_crash(self):
        """FeatureExtractor debe instanciarse sin error (ODDT puede no estar)."""
        extractor = FeatureExtractor()
        assert extractor is not None

    def test_oddt_available_is_bool(self):
        """El flag de ODDT debe ser booleano."""
        extractor = FeatureExtractor()
        assert isinstance(extractor._oddt_available, bool)


class TestZeroFeatures:
    """Tests de la degradación elegante (features en cero)."""

    def test_zero_features_has_all_interactions(self):
        """Features en cero deben contener todas las interaction features."""
        extractor = FeatureExtractor()
        zero_feats = extractor._zero_features()
        for feat_name in INTERACTION_FEATURES:
            assert feat_name in zero_feats
            assert zero_feats[feat_name] == 0.0

    def test_zero_features_length(self):
        """Deben haber exactamente len(INTERACTION_FEATURES) features en cero."""
        extractor = FeatureExtractor()
        zero_feats = extractor._zero_features()
        assert len(zero_feats) == len(INTERACTION_FEATURES)


class TestGetFeatureNames:
    """Tests del listado de features."""

    def test_feature_names_not_empty(self):
        """La lista de features no debe estar vacía."""
        extractor = FeatureExtractor()
        names = extractor.get_feature_names()
        assert len(names) > 0

    def test_feature_names_order(self):
        """Features se dividen en 4 grupos: 1D/2D, Vina, 3D, Pose variance."""
        extractor = FeatureExtractor()
        names = extractor.get_feature_names()
        # Primeros 7: descriptores 1D/2D
        assert names[0] == "mw"
        assert names[6] == "qed"
        # Grupo 2: Vina
        assert names[7] == "vina_best_score"
        # Grupo 3: 3D interactions
        assert names[8] == INTERACTION_FEATURES[0]
        # Grupo 4: Pose variance features al final
        assert names[-1] == "poses_passing_ratio"
        assert names[-2] == "pose_score_range"
        assert names[-3] == "pose_score_variance"

    def test_feature_names_unique(self):
        """Todos los nombres de features deben ser únicos."""
        extractor = FeatureExtractor()
        names = extractor.get_feature_names()
        assert len(names) == len(set(names))

    def test_total_feature_count(self):
        """
        7 (1D/2D) + 1 (vina) + 9 (3D) + 3 (variance) = 20 features.
        """
        extractor = FeatureExtractor()
        names = extractor.get_feature_names()
        assert len(names) == 20


class TestExtract3dFeatures:
    """Tests de extracción de features 3D con mock pose."""

    class MockPose:
        def __init__(self, score: float):
            self.pdbqt_block = "ATOM      1  C1  LIG A   1       0.000   0.000   0.000  1.00  0.00     C"
            self.vina_score = score

    def test_extract_includes_vina_score(self):
        """Las features extraídas deben incluir vina_best_score."""
        extractor = FeatureExtractor()
        pose = self.MockPose(-8.5)
        features = extractor.extract_3d_features(
            pose, smiles="CCO", target_pdb_path="/nonexistent/target.pdb"
        )
        assert "vina_best_score" in features
        assert features["vina_best_score"] == -8.5

    def test_extract_without_oddt_returns_zeros(self):
        """Sin ODDT, las features 3D deben ser 0."""
        extractor = FeatureExtractor()
        # Forzar que ODDT no esté disponible
        extractor._oddt_available = False
        pose = self.MockPose(-7.0)
        features = extractor.extract_3d_features(
            pose, smiles="CCO", target_pdb_path="/nonexistent/target.pdb"
        )
        for feat_name in INTERACTION_FEATURES:
            assert features[feat_name] == 0.0

    def test_extract_returns_dict(self):
        """El resultado debe ser un diccionario."""
        extractor = FeatureExtractor()
        pose = self.MockPose(-6.0)
        features = extractor.extract_3d_features(
            pose, smiles="c1ccccc1", target_pdb_path="/tmp/target.pdb"
        )
        assert isinstance(features, dict)
        assert len(features) > 0
