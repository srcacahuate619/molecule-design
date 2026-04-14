"""
tests/unit/test_conformer.py

Tests unitarios de chem/conformer.py.

Estrategia de testing:
    Las funciones internas se testean directamente porque son lógica
    científica con contratos claros (ETKDG params, macrocycle detection,
    SDF serialization).  La función pública generate_conformer() se
    testea con mocks de MinIO porque el almacenamiento es un detalle
    de infraestructura, no de química.

Moléculas de referencia:
    Aspirina   CC(=O)Oc1ccccc1C(=O)O     — sin macrociclos, anillos 5,6
    Benceno    c1ccccc1                    — anillo 6
    Ciclodecano C1CCCCCCCCC1              — macrociclo (10 átomos)
    Eritromicina lactona macrocíclica      — macrociclo (14 átomos)
    Etanol     CCO                         — sin anillos

Valores de referencia:
    Determinismo verificado con seed=42 + ETKDG v3.
    Round-trip SDF: mol → sdf_string → mol debe conservar número
    de átomos y propiedad SMILES embebida.
"""

import pytest
from rdkit import Chem
from rdkit.Chem import AllChem

from chem.conformer import (
    _get_etkdg_params,
    _get_ring_size_info,
    _has_macrocycle,
    _mol_to_sdf_string,
    _optimize_with_mmff,
    sdf_string_to_mol,
)


# ═══════════════════════════════════════════════════════════════════════════════
# FIXTURES
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def aspirin_smiles() -> str:
    return "CC(=O)Oc1ccccc1C(=O)O"


@pytest.fixture
def benzene_smiles() -> str:
    return "c1ccccc1"


@pytest.fixture
def ethanol_smiles() -> str:
    return "CCO"


@pytest.fixture
def cyclodecane_smiles() -> str:
    """Macrociclo sencillo: anillo de 10 carbonos."""
    return "C1CCCCCCCCC1"


@pytest.fixture
def erythromycin_lactone_smiles() -> str:
    """Macrolida — anillo de 14 miembros (macrociclo real)."""
    return "O=C1OC(CC)C(O)C(C)C(OC2CC(C)(OC)C(O)C(C)O2)C(C)CC(C)C(OC2OC(C)CC(N(C)C)C2O)C(C)C(O)C1(C)O"


def _mol_with_hs(smiles: str):
    """Crea mol con hidrógenos explícitos = input real de ETKDG."""
    mol = Chem.MolFromSmiles(smiles)
    assert mol is not None, f"RDKit no pudo parsear {smiles}"
    return Chem.AddHs(mol)


def _embed_mol(mol):
    """Embed rápido para tests que necesitan coordenadas 3D."""
    params = _get_etkdg_params(random_seed=42)
    result = AllChem.EmbedMolecule(mol, params)
    assert result == 0, "Embedding falló en test helper"
    return mol


# ═══════════════════════════════════════════════════════════════════════════════
# _get_etkdg_params
# ═══════════════════════════════════════════════════════════════════════════════

class TestGetETKDGParams:
    """Verifica configuración correcta de ETKDG v3."""

    def test_default_seed_is_42(self):
        params = _get_etkdg_params()
        assert params.randomSeed == 42

    def test_custom_seed(self):
        params = _get_etkdg_params(random_seed=137)
        assert params.randomSeed == 137

    def test_chirality_enforced(self):
        params = _get_etkdg_params()
        assert params.enforceChirality is True

    def test_macrocycle_torsions_enabled(self):
        params = _get_etkdg_params()
        assert params.useMacrocycleTorsions is True

    def test_small_ring_torsions_enabled(self):
        params = _get_etkdg_params()
        assert params.useSmallRingTorsions is True

    def test_max_iterations_sufficient(self):
        params = _get_etkdg_params()
        assert params.maxIterations >= 500


# ═══════════════════════════════════════════════════════════════════════════════
# _has_macrocycle
# ═══════════════════════════════════════════════════════════════════════════════

class TestHasMacrocycle:
    """Detecta correctamente anillos > 8 átomos."""

    def test_benzene_no_macrocycle(self, benzene_smiles):
        mol = Chem.MolFromSmiles(benzene_smiles)
        assert _has_macrocycle(mol) is False

    def test_aspirin_no_macrocycle(self, aspirin_smiles):
        mol = Chem.MolFromSmiles(aspirin_smiles)
        assert _has_macrocycle(mol) is False

    def test_ethanol_no_macrocycle(self, ethanol_smiles):
        mol = Chem.MolFromSmiles(ethanol_smiles)
        assert _has_macrocycle(mol) is False

    def test_cyclodecane_is_macrocycle(self, cyclodecane_smiles):
        mol = Chem.MolFromSmiles(cyclodecane_smiles)
        assert _has_macrocycle(mol) is True

    def test_cyclooctane_is_not_macrocycle(self):
        """Anillo de exactamente 8 átomos: NO es macrociclo (threshold >8)."""
        mol = Chem.MolFromSmiles("C1CCCCCCC1")
        assert _has_macrocycle(mol) is False

    def test_cyclononane_is_macrocycle(self):
        """Anillo de 9 átomos: SÍ es macrociclo (9 > 8)."""
        mol = Chem.MolFromSmiles("C1CCCCCCCC1")
        assert _has_macrocycle(mol) is True

    def test_erythromycin_lactone_is_macrocycle(self, erythromycin_lactone_smiles):
        mol = Chem.MolFromSmiles(erythromycin_lactone_smiles)
        assert mol is not None
        assert _has_macrocycle(mol) is True


# ═══════════════════════════════════════════════════════════════════════════════
# _get_ring_size_info
# ═══════════════════════════════════════════════════════════════════════════════

class TestGetRingSizeInfo:

    def test_ethanol_no_rings(self, ethanol_smiles):
        mol = Chem.MolFromSmiles(ethanol_smiles)
        assert _get_ring_size_info(mol) == "sin anillos"

    def test_benzene_single_six_ring(self, benzene_smiles):
        mol = Chem.MolFromSmiles(benzene_smiles)
        assert "6" in _get_ring_size_info(mol)

    def test_aspirin_contains_six_ring(self, aspirin_smiles):
        mol = Chem.MolFromSmiles(aspirin_smiles)
        info = _get_ring_size_info(mol)
        assert "6" in info

    def test_naphthalene_fused_rings(self):
        mol = Chem.MolFromSmiles("c1ccc2ccccc2c1")
        info = _get_ring_size_info(mol)
        assert "6" in info


# ═══════════════════════════════════════════════════════════════════════════════
# _optimize_with_mmff
# ═══════════════════════════════════════════════════════════════════════════════

class TestOptimizeWithMMFF:
    """MMFF94 optimization produce geometrías realistas."""

    def test_aspirin_converges(self, aspirin_smiles):
        mol = _mol_with_hs(aspirin_smiles)
        mol = _embed_mol(mol)
        optimized, converged = _optimize_with_mmff(mol)
        assert converged is True
        assert optimized.GetNumConformers() == 1

    def test_ethanol_converges(self, ethanol_smiles):
        mol = _mol_with_hs(ethanol_smiles)
        mol = _embed_mol(mol)
        optimized, converged = _optimize_with_mmff(mol)
        assert converged is True

    def test_benzene_converges(self, benzene_smiles):
        mol = _mol_with_hs(benzene_smiles)
        mol = _embed_mol(mol)
        optimized, converged = _optimize_with_mmff(mol)
        assert converged is True

    def test_optimized_mol_has_3d_coords(self, aspirin_smiles):
        mol = _mol_with_hs(aspirin_smiles)
        mol = _embed_mol(mol)
        optimized, _ = _optimize_with_mmff(mol)
        conf = optimized.GetConformer()
        # Verificar que al menos un átomo tiene coordenada z != 0
        has_z = any(
            abs(conf.GetAtomPosition(i).z) > 0.01
            for i in range(optimized.GetNumAtoms())
        )
        assert has_z, "Estructura 3D debe tener coordenadas z no triviales"


# ═══════════════════════════════════════════════════════════════════════════════
# _mol_to_sdf_string
# ═══════════════════════════════════════════════════════════════════════════════

class TestMolToSdfString:
    """Serialización mol → SDF string."""

    def test_output_contains_sdf_terminator(self, aspirin_smiles):
        mol = _mol_with_hs(aspirin_smiles)
        mol = _embed_mol(mol)
        sdf = _mol_to_sdf_string(mol, aspirin_smiles)
        assert "$$$$" in sdf, "SDF debe terminar con $$$$"

    def test_output_contains_smiles_property(self, aspirin_smiles):
        mol = _mol_with_hs(aspirin_smiles)
        mol = _embed_mol(mol)
        canonical = Chem.MolToSmiles(Chem.MolFromSmiles(aspirin_smiles))
        sdf = _mol_to_sdf_string(mol, canonical)
        assert canonical in sdf, "SDF debe contener el SMILES canónico embebido"

    def test_output_is_string_not_bytes(self, aspirin_smiles):
        mol = _mol_with_hs(aspirin_smiles)
        mol = _embed_mol(mol)
        sdf = _mol_to_sdf_string(mol, aspirin_smiles)
        assert isinstance(sdf, str)

    def test_output_not_empty(self, ethanol_smiles):
        mol = _mol_with_hs(ethanol_smiles)
        mol = _embed_mol(mol)
        sdf = _mol_to_sdf_string(mol, ethanol_smiles)
        assert len(sdf) > 100, "SDF debe tener contenido sustancial"


# ═══════════════════════════════════════════════════════════════════════════════
# sdf_string_to_mol (round-trip)
# ═══════════════════════════════════════════════════════════════════════════════

class TestSdfStringToMol:
    """Parseo SDF string → mol y round-trip."""

    def test_round_trip_preserves_atom_count(self, aspirin_smiles):
        """mol → sdf → mol conserva número de átomos."""
        mol = _mol_with_hs(aspirin_smiles)
        mol = _embed_mol(mol)
        original_atoms = mol.GetNumAtoms()

        sdf = _mol_to_sdf_string(mol, aspirin_smiles)
        recovered = sdf_string_to_mol(sdf)

        assert recovered is not None
        assert recovered.GetNumAtoms() == original_atoms

    def test_round_trip_preserves_smiles_property(self, aspirin_smiles):
        canonical = Chem.MolToSmiles(Chem.MolFromSmiles(aspirin_smiles))
        mol = _mol_with_hs(aspirin_smiles)
        mol = _embed_mol(mol)

        sdf = _mol_to_sdf_string(mol, canonical)
        recovered = sdf_string_to_mol(sdf)

        assert recovered is not None
        assert recovered.GetProp("SMILES") == canonical

    def test_round_trip_preserves_3d_coordinates(self, aspirin_smiles):
        """Las coordenadas 3D sobreviven el round-trip."""
        mol = _mol_with_hs(aspirin_smiles)
        mol = _embed_mol(mol)
        mol, _ = _optimize_with_mmff(mol)

        conf_orig = mol.GetConformer()
        pos_orig = conf_orig.GetAtomPosition(0)

        sdf = _mol_to_sdf_string(mol, aspirin_smiles)
        recovered = sdf_string_to_mol(sdf)
        conf_rec = recovered.GetConformer()
        pos_rec = conf_rec.GetAtomPosition(0)

        # Coordenadas deben ser idénticas (mismo SDF)
        assert abs(pos_orig.x - pos_rec.x) < 0.001
        assert abs(pos_orig.y - pos_rec.y) < 0.001
        assert abs(pos_orig.z - pos_rec.z) < 0.001

    def test_invalid_sdf_returns_none(self):
        assert sdf_string_to_mol("esto no es un SDF válido") is None

    def test_empty_string_returns_none(self):
        assert sdf_string_to_mol("") is None


# ═══════════════════════════════════════════════════════════════════════════════
# ETKDG determinismo con seed fija
# ═══════════════════════════════════════════════════════════════════════════════

class TestETKDGDeterminism:
    """Con la misma seed, ETKDG debe producir el mismo conformer."""

    def test_same_seed_same_coordinates(self, aspirin_smiles):
        """Dos embeddings con seed=42 producen coordenadas idénticas."""
        mol1 = _mol_with_hs(aspirin_smiles)
        mol2 = _mol_with_hs(aspirin_smiles)

        params = _get_etkdg_params(random_seed=42)

        AllChem.EmbedMolecule(mol1, params)
        AllChem.EmbedMolecule(mol2, params)

        conf1 = mol1.GetConformer()
        conf2 = mol2.GetConformer()

        for i in range(mol1.GetNumAtoms()):
            p1 = conf1.GetAtomPosition(i)
            p2 = conf2.GetAtomPosition(i)
            assert abs(p1.x - p2.x) < 1e-6
            assert abs(p1.y - p2.y) < 1e-6
            assert abs(p1.z - p2.z) < 1e-6

    def test_different_seed_different_coordinates(self, aspirin_smiles):
        """Seeds distintas producen conformers distintos."""
        mol1 = _mol_with_hs(aspirin_smiles)
        mol2 = _mol_with_hs(aspirin_smiles)

        AllChem.EmbedMolecule(mol1, _get_etkdg_params(random_seed=42))
        AllChem.EmbedMolecule(mol2, _get_etkdg_params(random_seed=999))

        conf1 = mol1.GetConformer()
        conf2 = mol2.GetConformer()

        # Al menos un átomo debe tener coordenadas distintas
        any_diff = any(
            abs(conf1.GetAtomPosition(i).x - conf2.GetAtomPosition(i).x) > 0.01
            for i in range(mol1.GetNumAtoms())
        )
        assert any_diff, "Seeds distintas deben producir geometrías distintas"


# ═══════════════════════════════════════════════════════════════════════════════
# generate_conformer (mocked storage)
# ═══════════════════════════════════════════════════════════════════════════════

class TestGenerateConformer:
    """Tests de la función pública con storage mockeado."""

    @pytest.mark.asyncio
    async def test_aspirin_returns_valid_result(self, aspirin_smiles):
        from unittest.mock import AsyncMock, patch

        with patch("chem.conformer.upload_text", new_callable=AsyncMock) as mock_upload:
            from chem.conformer import generate_conformer

            result = await generate_conformer(aspirin_smiles)

            assert result["canonical_smiles"] is not None
            assert result["smiles_hash"] is not None
            assert result["conformer_path"].endswith(".sdf")
            assert result["num_atoms_3d"] > 0
            assert isinstance(result["optimization_converged"], bool)
            assert isinstance(result["had_macrocycle"], bool)
            assert result["had_macrocycle"] is False
            mock_upload.assert_called_once()

    @pytest.mark.asyncio
    async def test_invalid_smiles_raises(self):
        from unittest.mock import AsyncMock, patch

        from core.exceptions import InvalidSMILES

        with patch("chem.conformer.upload_text", new_callable=AsyncMock):
            from chem.conformer import generate_conformer

            with pytest.raises(InvalidSMILES):
                await generate_conformer("INVALID_SMILES_XXX")

    @pytest.mark.asyncio
    async def test_caffeine_returns_valid_result(self):
        """Cafeína: molécula drug-like con anillos fusionados."""
        from unittest.mock import AsyncMock, patch

        caffeine = "CN1C=NC2=C1C(=O)N(C(=O)N2C)C"

        with patch("chem.conformer.upload_text", new_callable=AsyncMock):
            from chem.conformer import generate_conformer

            result = await generate_conformer(caffeine)

            assert result["num_atoms_3d"] > 0
            assert result["molecular_formula"] is not None

    @pytest.mark.asyncio
    async def test_sdf_uploaded_to_minio_contains_molecule(self, aspirin_smiles):
        """Verifica que el string SDF subido a MinIO es parseable."""
        from unittest.mock import AsyncMock, patch

        uploaded_content = None

        async def capture_upload(text, object_name):
            nonlocal uploaded_content
            uploaded_content = text

        with patch("chem.conformer.upload_text", side_effect=capture_upload):
            from chem.conformer import generate_conformer

            await generate_conformer(aspirin_smiles)

        assert uploaded_content is not None
        recovered = sdf_string_to_mol(uploaded_content)
        assert recovered is not None
        assert recovered.GetNumConformers() == 1
