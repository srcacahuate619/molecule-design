"""
tests/unit/test_file_handlers.py

Tests unitarios para los parsers de formato molecular en utils/file_handlers.py.
Verifican que parse_vina_output_sdf y parse_vina_output_pdbqt extraigan
correctamente las afinidades y metadatos de poses.
"""

import pytest

from utils.file_handlers import parse_vina_output_sdf, parse_vina_output_pdbqt


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Fixtures: SDF content samples
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

MEEKO_SDF_3_POSES = """\
UNL
     RDKit          3D

  5  4  0  0  0  0  0  0  0  0999 V2000
    1.0000    2.0000    3.0000 C   0  0  0  0  0  0  0  0  0  0  0  0
    1.5000    2.0000    3.0000 O   0  0  0  0  0  0  0  0  0  0  0  0
    2.0000    2.0000    3.0000 N   0  0  0  0  0  0  0  0  0  0  0  0
    2.5000    2.0000    3.0000 C   0  0  0  0  0  0  0  0  0  0  0  0
    3.0000    2.0000    3.0000 C   0  0  0  0  0  0  0  0  0  0  0  0
  1  2  1  0
  2  3  1  0
  3  4  1  0
  4  5  1  0
M  END
> <meeko>
{"is_sidechain": false, "free_energy": -8.5, "intermolecular_energy": -9.1}

$$$$
UNL
     RDKit          3D

  5  4  0  0  0  0  0  0  0  0999 V2000
    1.1000    2.1000    3.1000 C   0  0  0  0  0  0  0  0  0  0  0  0
    1.6000    2.1000    3.1000 O   0  0  0  0  0  0  0  0  0  0  0  0
    2.1000    2.1000    3.1000 N   0  0  0  0  0  0  0  0  0  0  0  0
    2.6000    2.1000    3.1000 C   0  0  0  0  0  0  0  0  0  0  0  0
    3.1000    2.1000    3.1000 C   0  0  0  0  0  0  0  0  0  0  0  0
  1  2  1  0
  2  3  1  0
  3  4  1  0
  4  5  1  0
M  END
> <meeko>
{"is_sidechain": false, "free_energy": -7.2}

$$$$
UNL
     RDKit          3D

  5  4  0  0  0  0  0  0  0  0999 V2000
    1.2000    2.2000    3.2000 C   0  0  0  0  0  0  0  0  0  0  0  0
    1.7000    2.2000    3.2000 O   0  0  0  0  0  0  0  0  0  0  0  0
    2.2000    2.2000    3.2000 N   0  0  0  0  0  0  0  0  0  0  0  0
    2.7000    2.2000    3.2000 C   0  0  0  0  0  0  0  0  0  0  0  0
    3.2000    2.2000    3.2000 C   0  0  0  0  0  0  0  0  0  0  0  0
  1  2  1  0
  2  3  1  0
  3  4  1  0
  4  5  1  0
M  END
> <meeko>
{"is_sidechain": false, "free_energy": -6.0}

$$$$
"""

LEGACY_SDF_2_POSES = """\
UNL
     RDKit          3D

  2  1  0  0  0  0  0  0  0  0999 V2000
    1.0000    2.0000    3.0000 C   0  0  0  0  0  0  0  0  0  0  0  0
    1.5000    2.0000    3.0000 O   0  0  0  0  0  0  0  0  0  0  0  0
  1  2  1  0
M  END
> <minimizedAffinity>
-9.3

> <minimizedRMSD_lowerBound>
0.0

> <minimizedRMSD_upperBound>
0.0

$$$$
UNL
     RDKit          3D

  2  1  0  0  0  0  0  0  0  0999 V2000
    1.1000    2.1000    3.1000 C   0  0  0  0  0  0  0  0  0  0  0  0
    1.6000    2.1000    3.1000 O   0  0  0  0  0  0  0  0  0  0  0  0
  1  2  1  0
M  END
> <minimizedAffinity>
-8.1

> <minimizedRMSD_lowerBound>
1.5

> <minimizedRMSD_upperBound>
3.2

$$$$
"""

EMPTY_SDF = ""

SDF_NO_AFFINITY = """\
UNL
     RDKit          3D

  2  1  0  0  0  0  0  0  0  0999 V2000
    1.0000    2.0000    3.0000 C   0  0  0  0  0  0  0  0  0  0  0  0
    1.5000    2.0000    3.0000 O   0  0  0  0  0  0  0  0  0  0  0  0
  1  2  1  0
M  END
> <meeko>
{"is_sidechain": false}

$$$$
"""

PDBQT_3_POSES = """\
REMARK VINA RESULT:   -8.5      0.000      0.000
MODEL 1
ATOM      1  C1  UNL     1       1.000   2.000   3.000  1.00  0.00     0.000 C
ENDMDL
REMARK VINA RESULT:   -7.2      1.234      2.345
MODEL 2
ATOM      1  C1  UNL     1       1.100   2.100   3.100  1.00  0.00     0.000 C
ENDMDL
REMARK VINA RESULT:   -6.0      3.456      5.678
MODEL 3
ATOM      1  C1  UNL     1       1.200   2.200   3.200  1.00  0.00     0.000 C
ENDMDL
"""


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Tests: parse_vina_output_sdf — Meeko JSON format
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class TestParseVinaOutputSdfMeeko:
    """Tests para la propiedad > <meeko> de Meeko 0.5+."""

    def test_parses_3_meeko_poses(self):
        poses = parse_vina_output_sdf(MEEKO_SDF_3_POSES)
        assert len(poses) == 3

    def test_meeko_affinities_correct(self):
        poses = parse_vina_output_sdf(MEEKO_SDF_3_POSES)
        assert poses[0]["affinity"] == -8.5
        assert poses[1]["affinity"] == -7.2
        assert poses[2]["affinity"] == -6.0

    def test_meeko_ranks_sequential(self):
        poses = parse_vina_output_sdf(MEEKO_SDF_3_POSES)
        assert [p["rank"] for p in poses] == [1, 2, 3]

    def test_meeko_rmsd_defaults_to_zero(self):
        """Meeko doesn't export RMSD to SDF; should default to 0.0."""
        poses = parse_vina_output_sdf(MEEKO_SDF_3_POSES)
        for pose in poses:
            assert pose["rmsd_lb"] == 0.0
            assert pose["rmsd_ub"] == 0.0


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Tests: parse_vina_output_sdf — Legacy format
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class TestParseVinaOutputSdfLegacy:
    """Tests para el formato legado con propiedades individuales."""

    def test_parses_2_legacy_poses(self):
        poses = parse_vina_output_sdf(LEGACY_SDF_2_POSES)
        assert len(poses) == 2

    def test_legacy_affinities_correct(self):
        poses = parse_vina_output_sdf(LEGACY_SDF_2_POSES)
        assert poses[0]["affinity"] == -9.3
        assert poses[1]["affinity"] == -8.1

    def test_legacy_rmsd_values(self):
        poses = parse_vina_output_sdf(LEGACY_SDF_2_POSES)
        assert poses[0]["rmsd_lb"] == 0.0
        assert poses[0]["rmsd_ub"] == 0.0
        assert poses[1]["rmsd_lb"] == 1.5
        assert poses[1]["rmsd_ub"] == 3.2


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Tests: parse_vina_output_sdf — Edge cases
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class TestParseVinaOutputSdfEdgeCases:
    """Tests de borde: SDF vacío, sin afinidad, JSON inválido."""

    def test_empty_sdf_returns_empty_list(self):
        poses = parse_vina_output_sdf(EMPTY_SDF)
        assert poses == []

    def test_sdf_without_affinity_returns_empty(self):
        """Mol block sin free_energy en meeko JSON → no genera pose."""
        poses = parse_vina_output_sdf(SDF_NO_AFFINITY)
        assert len(poses) == 0

    def test_invalid_meeko_json_is_handled(self):
        sdf = """\
UNL
     RDKit          3D

  2  1  0  0  0  0  0  0  0  0999 V2000
    1.0000    2.0000    3.0000 C   0  0  0  0  0  0  0  0  0  0  0  0
    1.5000    2.0000    3.0000 O   0  0  0  0  0  0  0  0  0  0  0  0
  1  2  1  0
M  END
> <meeko>
{this is not valid json}

$$$$
"""
        poses = parse_vina_output_sdf(sdf)
        assert len(poses) == 0


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Tests: parse_vina_output_pdbqt
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class TestParseVinaOutputPdbqt:
    """Tests para el parser PDBQT (REMARK VINA RESULT:)."""

    def test_parses_3_pdbqt_poses(self):
        poses = parse_vina_output_pdbqt(PDBQT_3_POSES)
        assert len(poses) == 3

    def test_pdbqt_affinities(self):
        poses = parse_vina_output_pdbqt(PDBQT_3_POSES)
        assert poses[0]["affinity"] == -8.5
        assert poses[1]["affinity"] == -7.2
        assert poses[2]["affinity"] == -6.0

    def test_pdbqt_rmsd_values(self):
        poses = parse_vina_output_pdbqt(PDBQT_3_POSES)
        assert poses[0]["rmsd_lb"] == 0.0
        assert poses[0]["rmsd_ub"] == 0.0
        assert poses[1]["rmsd_lb"] == 1.234
        assert poses[1]["rmsd_ub"] == 2.345
        assert poses[2]["rmsd_lb"] == 3.456
        assert poses[2]["rmsd_ub"] == 5.678

    def test_pdbqt_ranks(self):
        poses = parse_vina_output_pdbqt(PDBQT_3_POSES)
        assert [p["rank"] for p in poses] == [1, 2, 3]

    def test_empty_pdbqt(self):
        poses = parse_vina_output_pdbqt("")
        assert poses == []
