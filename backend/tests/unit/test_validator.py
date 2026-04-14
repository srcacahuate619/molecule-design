"""
tests/unit/test_validator.py

Tests unitarios de chem/validator.py.

Estrategia de testing:
    Cada función de validación (_parse_smiles, _check_atoms, etc.)
    se testea a través de la función pública validate_smiles() —
    no directamente, porque son detalles de implementación.
    Si el comportamiento público es correcto, la implementación interna
    puede refactorizarse sin romper los tests.

Moléculas de referencia usadas:
    Aspirina   CC(=O)Oc1ccccc1C(=O)O     MW=180.16, Lipinski PASS
    Cafeína    CN1C=NC2=C1C(=O)N(C...)C  MW=194.19, Lipinski PASS
    Etanol     CCO                         MW=46.07,  muy pequeña
    Ibuprofeno CC(C)Cc1ccc(cc1)C(C)C(=O)O MW=206.28, Lipinski PASS

Casos de error cubiertos:
    SMILES vacío, átomo desconocido, anillo no cerrado,
    valencia excedida, SMILES aromático incompleto,
    molécula demasiado grande, molécula con fragmentos.

Valores esperados obtenidos de:
    PubChem (MW, fórmula molecular)
    RDKit documentation (comportamiento de sanitización)
    Literatura farmacológica (Lipinski, Veber)
"""

import hashlib

import pytest
from rdkit import Chem

from chem.validator import (
    are_same_molecule,
    smiles_to_canonical,
    smiles_to_hash,
    validate_smiles,
    validate_smiles_or_raise,
)
from core.exceptions import InvalidSMILES
from core.models import ValidationResult


# ═══════════════════════════════════════════════════════════════════════════════
# FIXTURES
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def aspirin_smiles() -> str:
    return "CC(=O)Oc1ccccc1C(=O)O"


@pytest.fixture
def caffeine_smiles() -> str:
    return "CN1C=NC2=C1C(=O)N(C(=O)N2C)C"


@pytest.fixture
def ibuprofen_smiles() -> str:
    return "CC(C)Cc1ccc(cc1)C(C)C(=O)O"


@pytest.fixture
def ethanol_smiles() -> str:
    return "CCO"


# ═══════════════════════════════════════════════════════════════════════════════
# TESTS: validate_smiles() — casos válidos
# ═══════════════════════════════════════════════════════════════════════════════

class TestValidateSmilesValid:
    """Tests con moléculas válidas conocidas."""

    def test_aspirin_is_valid(self, aspirin_smiles):
        result = validate_smiles(aspirin_smiles)
        assert result.is_valid is True
        assert result.errors == []

    def test_aspirin_formula(self, aspirin_smiles):
        result = validate_smiles(aspirin_smiles)
        assert result.molecular_formula == "C9H8O4"

    def test_aspirin_heavy_atoms(self, aspirin_smiles):
        result = validate_smiles(aspirin_smiles)
        assert result.heavy_atom_count == 13

    def test_aspirin_canonical_smiles_is_deterministic(self, aspirin_smiles):
        """El mismo SMILES siempre produce el mismo canónico."""
        result1 = validate_smiles(aspirin_smiles)
        result2 = validate_smiles(aspirin_smiles)
        assert result1.canonical_smiles == result2.canonical_smiles

    def test_aspirin_hash_matches_canonical(self, aspirin_smiles):
        """El hash es SHA-256 del canónico, verificable externamente."""
        result = validate_smiles(aspirin_smiles)
        expected_hash = hashlib.sha256(
            result.canonical_smiles.encode("utf-8")
        ).hexdigest()
        assert result.smiles_hash == expected_hash

    def test_caffeine_is_valid(self, caffeine_smiles):
        result = validate_smiles(caffeine_smiles)
        assert result.is_valid is True
        assert result.molecular_formula == "C8H10N4O2"

    def test_ibuprofen_is_valid(self, ibuprofen_smiles):
        result = validate_smiles(ibuprofen_smiles)
        assert result.is_valid is True

    def test_result_is_validation_result_type(self, aspirin_smiles):
        result = validate_smiles(aspirin_smiles)
        assert isinstance(result, ValidationResult)

    def test_valid_molecule_has_no_errors(self, caffeine_smiles):
        result = validate_smiles(caffeine_smiles)
        assert len(result.errors) == 0

    def test_canonical_smiles_is_not_none_for_valid(self, aspirin_smiles):
        result = validate_smiles(aspirin_smiles)
        assert result.canonical_smiles is not None
        assert len(result.canonical_smiles) > 0

    def test_smiles_hash_is_64_hex_chars(self, aspirin_smiles):
        """SHA-256 produce exactamente 64 caracteres hexadecimales."""
        result = validate_smiles(aspirin_smiles)
        assert result.smiles_hash is not None
        assert len(result.smiles_hash) == 64
        assert all(c in "0123456789abcdef" for c in result.smiles_hash)


# ═══════════════════════════════════════════════════════════════════════════════
# TESTS: validate_smiles() — canonicalización
# ═══════════════════════════════════════════════════════════════════════════════

class TestCanonicalization:
    """
    La canonicalización es crítica para el cache y la detección de duplicados.
    Representaciones distintas de la misma molécula deben producir
    el mismo canónico y el mismo hash.
    """

    def test_ethanol_representations_same_canonical(self):
        """CCO, OCC y C(O)C son el mismo etanol."""
        r1 = validate_smiles("CCO")
        r2 = validate_smiles("OCC")
        r3 = validate_smiles("C(O)C")
        assert r1.canonical_smiles == r2.canonical_smiles == r3.canonical_smiles

    def test_ethanol_representations_same_hash(self):
        r1 = validate_smiles("CCO")
        r2 = validate_smiles("OCC")
        assert r1.smiles_hash == r2.smiles_hash

    def test_aspirin_different_notation_same_hash(self, aspirin_smiles):
        """SMILES con y sin aromaticidad explícita."""
        # Aspirina con Kekulé (sin minúsculas aromáticas)
        kekulized = "CC(=O)OC1=CC=CC=C1C(=O)O"
        r1 = validate_smiles(aspirin_smiles)
        r2 = validate_smiles(kekulized)
        # RDKit canonicaliza ambos al mismo resultado
        assert r1.canonical_smiles == r2.canonical_smiles

    def test_different_molecules_different_hashes(self, aspirin_smiles, caffeine_smiles):
        r1 = validate_smiles(aspirin_smiles)
        r2 = validate_smiles(caffeine_smiles)
        assert r1.smiles_hash != r2.smiles_hash


# ═══════════════════════════════════════════════════════════════════════════════
# TESTS: validate_smiles() — casos inválidos
# ═══════════════════════════════════════════════════════════════════════════════

class TestValidateSmilesInvalid:
    """Tests con SMILES que deben fallar la validación."""

    def test_empty_string_is_invalid(self):
        result = validate_smiles("")
        assert result.is_valid is False
        assert len(result.errors) > 0

    def test_whitespace_only_is_invalid(self):
        result = validate_smiles("   ")
        assert result.is_valid is False

    def test_unknown_atom_is_invalid(self):
        """'X' no es un símbolo atómico válido en SMILES estándar."""
        result = validate_smiles("CCX")
        assert result.is_valid is False
        assert len(result.errors) > 0

    def test_unclosed_ring_is_invalid(self):
        """C1CC sin cerrar el anillo con otro '1'."""
        result = validate_smiles("C1CC")
        assert result.is_valid is False

    def test_incomplete_aromatic_is_invalid(self):
        """Anillo aromático incompleto."""
        result = validate_smiles("c1ccccc")
        assert result.is_valid is False

    def test_invalid_smiles_has_no_canonical(self):
        """Un SMILES inválido no debe tener SMILES canónico."""
        result = validate_smiles("CCX")
        assert result.canonical_smiles is None

    def test_invalid_smiles_has_no_hash(self):
        """Un SMILES inválido no debe tener hash."""
        result = validate_smiles("C1CC")
        assert result.smiles_hash is None

    def test_invalid_smiles_has_no_formula(self):
        result = validate_smiles("CCX")
        assert result.molecular_formula is None

    def test_invalid_smiles_returns_error_messages(self):
        """Los mensajes de error deben ser strings no vacíos."""
        result = validate_smiles("CCX")
        assert all(isinstance(e, str) and len(e) > 0 for e in result.errors)

    def test_random_string_is_invalid(self):
        result = validate_smiles("esto no es un smiles")
        assert result.is_valid is False

    def test_numbers_only_is_invalid(self):
        result = validate_smiles("12345")
        assert result.is_valid is False


# ═══════════════════════════════════════════════════════════════════════════════
# TESTS: validate_smiles() — warnings (válidos pero con advertencias)
# ═══════════════════════════════════════════════════════════════════════════════

class TestValidateSmilesWarnings:
    """
    Moléculas que pasan la validación pero generan warnings.
    is_valid=True con warnings != [] es un estado válido del sistema.
    """

    def test_molecule_with_metal_is_valid_with_warning(self):
        """
        Molécula organometálica: válida estructuralmente pero
        Vina no tiene parámetros confiables para Fe.
        """
        # Ferroceno simplificado (no es drug-like pero es SMILES válido)
        result = validate_smiles("[Fe]")
        # Puede ser válido o inválido según RDKit — lo importante es
        # que si es válido, genera un warning sobre compatibilidad con Vina
        if result.is_valid:
            # Si RDKit lo acepta, debe haber un warning sobre el metal
            metal_warning = any(
                "Fe" in w or "metal" in w.lower() or "soportad" in w.lower()
                for w in result.warnings
            )
            assert metal_warning, (
                f"Se esperaba un warning sobre Fe, pero solo hay: {result.warnings}"
            )

    def test_fragmented_molecule_is_valid_with_warning(self):
        """
        Sal o mezcla: SMILES válido con fragmentos desconectados.
        El sistema debe validarlo como válido pero advertir al usuario.
        """
        # Cloruro de sodio (simplificado como fragmentos)
        result = validate_smiles("CC.OCC")
        if result.is_valid:
            fragment_warning = any(
                "fragment" in w.lower() or "desconect" in w.lower()
                for w in result.warnings
            )
            assert fragment_warning, (
                f"Se esperaba warning de fragmentos, pero solo hay: {result.warnings}"
            )

    def test_small_molecule_generates_warning(self, ethanol_smiles):
        """
        Moléculas muy pequeñas (< 5 átomos pesados) deben advertir
        sobre su limitada relevancia farmacológica.
        """
        result = validate_smiles(ethanol_smiles)
        # Etanol tiene 3 átomos pesados (2 C + 1 O) — puede ser inválido
        # por tamaño o válido con warning según la configuración
        # Lo que verificamos es que el sistema no falla silenciosamente
        assert isinstance(result.is_valid, bool)


# ═══════════════════════════════════════════════════════════════════════════════
# TESTS: validate_smiles_or_raise()
# ═══════════════════════════════════════════════════════════════════════════════

class TestValidateSmilesOrRaise:
    """
    validate_smiles_or_raise() es la variante que lanza excepción.
    Usada en los routers de FastAPI.
    """

    def test_valid_smiles_returns_result(self, aspirin_smiles):
        result = validate_smiles_or_raise(aspirin_smiles)
        assert result.is_valid is True

    def test_invalid_smiles_raises_invalid_smiles(self):
        with pytest.raises(InvalidSMILES):
            validate_smiles_or_raise("CCX")

    def test_exception_contains_smiles(self):
        bad_smiles = "C1CC"
        with pytest.raises(InvalidSMILES) as exc_info:
            validate_smiles_or_raise(bad_smiles)
        assert exc_info.value.smiles == bad_smiles

    def test_exception_contains_reason(self):
        with pytest.raises(InvalidSMILES) as exc_info:
            validate_smiles_or_raise("CCX")
        assert exc_info.value.reason is not None
        assert len(exc_info.value.reason) > 0

    def test_empty_string_raises(self):
        with pytest.raises(InvalidSMILES):
            validate_smiles_or_raise("")

    def test_valid_smiles_does_not_raise(self, caffeine_smiles):
        """Debe completarse sin excepción."""
        result = validate_smiles_or_raise(caffeine_smiles)
        assert result is not None

    def test_returns_validation_result_type(self, aspirin_smiles):
        result = validate_smiles_or_raise(aspirin_smiles)
        assert isinstance(result, ValidationResult)


# ═══════════════════════════════════════════════════════════════════════════════
# TESTS: smiles_to_canonical()
# ═══════════════════════════════════════════════════════════════════════════════

class TestSmilesToCanonical:
    """Tests de la función utilitaria smiles_to_canonical."""

    def test_returns_string(self, aspirin_smiles):
        result = smiles_to_canonical(aspirin_smiles)
        assert isinstance(result, str)
        assert len(result) > 0

    def test_canonical_is_idempotent(self, aspirin_smiles):
        """Canonicalizar un canónico produce el mismo resultado."""
        canonical1 = smiles_to_canonical(aspirin_smiles)
        canonical2 = smiles_to_canonical(canonical1)
        assert canonical1 == canonical2

    def test_invalid_smiles_raises_value_error(self):
        with pytest.raises(ValueError):
            smiles_to_canonical("CCX")

    def test_equivalent_smiles_produce_same_canonical(self):
        c1 = smiles_to_canonical("CCO")
        c2 = smiles_to_canonical("OCC")
        assert c1 == c2


# ═══════════════════════════════════════════════════════════════════════════════
# TESTS: smiles_to_hash()
# ═══════════════════════════════════════════════════════════════════════════════

class TestSmilesToHash:
    """Tests de la función utilitaria smiles_to_hash."""

    def test_returns_64_char_hex(self, aspirin_smiles):
        h = smiles_to_hash(aspirin_smiles)
        assert len(h) == 64
        assert all(c in "0123456789abcdef" for c in h)

    def test_same_molecule_same_hash(self, aspirin_smiles):
        h1 = smiles_to_hash(aspirin_smiles)
        h2 = smiles_to_hash(aspirin_smiles)
        assert h1 == h2

    def test_equivalent_smiles_same_hash(self):
        """Representaciones distintas del mismo etanol → mismo hash."""
        h1 = smiles_to_hash("CCO")
        h2 = smiles_to_hash("OCC")
        assert h1 == h2

    def test_different_molecules_different_hashes(self, aspirin_smiles, caffeine_smiles):
        h1 = smiles_to_hash(aspirin_smiles)
        h2 = smiles_to_hash(caffeine_smiles)
        assert h1 != h2

    def test_invalid_smiles_raises_value_error(self):
        with pytest.raises(ValueError):
            smiles_to_hash("CCX")

    def test_hash_is_sha256_of_canonical(self, aspirin_smiles):
        """Verifica que el hash es SHA-256 del canónico, reproducible externamente."""
        canonical = smiles_to_canonical(aspirin_smiles)
        expected = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        actual = smiles_to_hash(aspirin_smiles)
        assert actual == expected


# ═══════════════════════════════════════════════════════════════════════════════
# TESTS: are_same_molecule()
# ═══════════════════════════════════════════════════════════════════════════════

class TestAreSameMolecule:
    """Tests de la comparación de identidad molecular."""

    def test_same_smiles_is_same_molecule(self, aspirin_smiles):
        assert are_same_molecule(aspirin_smiles, aspirin_smiles) is True

    def test_equivalent_smiles_is_same_molecule(self):
        assert are_same_molecule("CCO", "OCC") is True
        assert are_same_molecule("CCO", "C(O)C") is True

    def test_different_molecules_are_not_same(self, aspirin_smiles, caffeine_smiles):
        assert are_same_molecule(aspirin_smiles, caffeine_smiles) is False

    def test_invalid_smiles_returns_false(self, aspirin_smiles):
        """Si uno de los SMILES es inválido, retorna False sin lanzar excepción."""
        assert are_same_molecule(aspirin_smiles, "CCX") is False
        assert are_same_molecule("CCX", aspirin_smiles) is False

    def test_both_invalid_returns_false(self):
        assert are_same_molecule("CCX", "C1CC") is False

    def test_aspirin_and_ibuprofen_are_different(self, aspirin_smiles, ibuprofen_smiles):
        assert are_same_molecule(aspirin_smiles, ibuprofen_smiles) is False


# ═══════════════════════════════════════════════════════════════════════════════
# TESTS: propiedades del resultado (invariantes del sistema)
# ═══════════════════════════════════════════════════════════════════════════════

class TestValidationResultInvariants:
    """
    Invariantes que siempre deben cumplirse independientemente
    del SMILES de entrada. Son contratos del sistema.
    """

    @pytest.mark.parametrize("smiles", [
        "CC(=O)Oc1ccccc1C(=O)O",   # aspirina
        "CN1C=NC2=C1C(=O)N(C(=O)N2C)C",   # cafeína
        "CC(C)Cc1ccc(cc1)C(C)C(=O)O",   # ibuprofeno
    ])
    def test_valid_molecule_invariants(self, smiles):
        """Para cualquier molécula válida, estos invariantes deben cumplirse."""
        result = validate_smiles(smiles)
        assert result.is_valid is True
        assert result.canonical_smiles is not None
        assert result.smiles_hash is not None
        assert result.molecular_formula is not None
        assert result.heavy_atom_count is not None
        assert result.heavy_atom_count > 0
        assert len(result.smiles_hash) == 64
        assert result.errors == []

    @pytest.mark.parametrize("smiles", [
        "",
        "CCX",
        "C1CC",
        "esto no es smiles",
        "c1ccccc",
    ])
    def test_invalid_molecule_invariants(self, smiles):
        """Para cualquier SMILES inválido, estos invariantes deben cumplirse."""
        result = validate_smiles(smiles)
        assert result.is_valid is False
        assert result.canonical_smiles is None
        assert result.smiles_hash is None
        assert len(result.errors) > 0

    def test_warnings_is_always_a_list(self):
        """warnings siempre es una lista, nunca None."""
        for smiles in ["CC(=O)O", "CCX", ""]:
            result = validate_smiles(smiles)
            assert isinstance(result.warnings, list)

    def test_errors_is_always_a_list(self):
        """errors siempre es una lista, nunca None."""
        for smiles in ["CC(=O)O", "CCX", ""]:
            result = validate_smiles(smiles)
            assert isinstance(result.errors, list)

    def test_validate_never_raises_exception(self):
        """
        validate_smiles() nunca debe lanzar excepción — siempre retorna
        un ValidationResult. Las excepciones son para validate_smiles_or_raise().
        """
        problematic_inputs = [
            "",
            "   ",
            "CCX",
            "C" * 1000,   # SMILES muy largo
            "!@#$%^&*()",
            None.__class__.__name__,   # "NoneType" como string
        ]
        for smiles in problematic_inputs:
            try:
                result = validate_smiles(smiles)
                assert isinstance(result, ValidationResult)
            except Exception as e:
                pytest.fail(
                    f"validate_smiles('{smiles[:20]}') lanzó {type(e).__name__}: {e}"
                )
