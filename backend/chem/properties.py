"""
chem/properties.py

Cálculo de propiedades fisicoquímicas con RDKit.

Este módulo asume que la molécula ya fue validada por chem/validator.py.
Nunca llames a estas funciones con un SMILES sin validar primero —
algunos cálculos de RDKit producen resultados silenciosamente incorrectos
en moléculas malformadas en lugar de lanzar excepción.

Propiedades calculadas:

    Básicas (Lipinski):
        MW      Peso molecular (Da)
        logP    Coeficiente de partición octanol/agua (Crippen)
        HBD     H-bond donors (Lipinski)
        HBA     H-bond acceptors (Lipinski)

    Extendidas:
        TPSA    Topological Polar Surface Area (Å²) — absorción oral/BBB
        RotBonds Rotatable bonds — flexibilidad molecular (Veber)
        HeavyAtoms Átomos pesados
        Rings   Número de anillos

    Drug-likeness:
        Lipinski  MW≤500, logP≤5, HBD≤5, HBA≤10
        Veber     RotBonds≤10, TPSA≤140

Referencia científica:
    Lipinski et al. (1997) Adv. Drug Deliv. Rev. 23:3–25
    Veber et al. (2002) J. Med. Chem. 45:2615–2623
    Ertl et al. (2000) J. Med. Chem. 43:3714–3717 (TPSA)
"""

from rdkit import Chem
from rdkit.Chem import Crippen, Descriptors, Lipinski, QED, rdMolDescriptors
from rdkit.Chem.rdchem import Mol

from chem.validator import validate_smiles_or_raise
from core.exceptions import PropertyCalculationError
from core.models import PhysicochemicalProperties, ValidationResult
from utils.logger import get_logger

log = get_logger(__name__)


# ── Reglas de drug-likeness ───────────────────────────────────────────────────

class LipinskiRule:
    """
    Regla de los cinco de Lipinski.

    Predice buena absorción oral si cumple al menos 3 de 4 criterios.
    La regla original permite una violación ("rule of five with one exception").
    Aquí implementamos la versión estricta (0 violaciones) para el MVP.

    Referencia: Lipinski et al. (1997)
    """
    MW_MAX  = 500.0
    LOGP_MAX = 5.0
    HBD_MAX  = 5
    HBA_MAX  = 10

    @classmethod
    def evaluate(cls, mw: float, log_p: float, hbd: int, hba: int) -> tuple[bool, list[str]]:
        """
        Retorna (passes, violations).
        violations es una lista de strings describiendo cada regla violada.
        """
        violations = []
        if mw > cls.MW_MAX:
            violations.append(f"MW={mw:.1f} > {cls.MW_MAX}")
        if log_p > cls.LOGP_MAX:
            violations.append(f"logP={log_p:.2f} > {cls.LOGP_MAX}")
        if hbd > cls.HBD_MAX:
            violations.append(f"HBD={hbd} > {cls.HBD_MAX}")
        if hba > cls.HBA_MAX:
            violations.append(f"HBA={hba} > {cls.HBA_MAX}")
        return len(violations) == 0, violations


class VerberRule:
    """
    Regla de Veber para biodisponibilidad oral.

    Complementa Lipinski con criterios de flexibilidad molecular.
    Referencia: Veber et al. (2002)
    """
    ROT_BONDS_MAX = 10
    TPSA_MAX      = 140.0

    @classmethod
    def evaluate(cls, rot_bonds: int, tpsa: float) -> tuple[bool, list[str]]:
        violations = []
        if rot_bonds > cls.ROT_BONDS_MAX:
            violations.append(f"RotBonds={rot_bonds} > {cls.ROT_BONDS_MAX}")
        if tpsa > cls.TPSA_MAX:
            violations.append(f"TPSA={tpsa:.1f} > {cls.TPSA_MAX}")
        return len(violations) == 0, violations


# ── Cálculos individuales ─────────────────────────────────────────────────────

def _calc_molecular_weight(mol: Mol) -> float:
    """
    Peso molecular promedio (Da).

    Usa pesos atómicos promedio (no monoisotópicos), que es lo estándar
    en farmacología para comparar con valores de literatura.
    """
    return round(Descriptors.MolWt(mol), 2)


def _calc_log_p(mol: Mol) -> float:
    """
    logP calculado con el método de Crippen (contribuciones atómicas).

    El logP de Crippen es el más usado en cheminformatics aunque
    puede diferir ±0.5 del logP experimental. Para screening
    computacional es suficientemente preciso.

    Valores guía:
        logP < 0    muy hidrofílica, posible baja permeabilidad
        0–3         rango óptimo para absorción oral
        3–5         aceptable (Lipinski)
        > 5         posible acumulación en tejido graso, toxicidad
    """
    return round(Crippen.MolLogP(mol), 2)


def _calc_tpsa(mol: Mol) -> float:
    """
    Topological Polar Surface Area (Å²).

    Correlaciona con absorción intestinal y penetración BBB.

    Valores guía:
        TPSA < 60 Å²    buena absorción intestinal
        TPSA < 90 Å²    buena biodisponibilidad oral
        TPSA > 140 Å²   absorción oral pobre (Veber)
        TPSA < 60 Å²    penetración BBB posible (CNS drugs)

    La implementación de RDKit usa el método de Ertl (2000).
    """
    return round(rdMolDescriptors.CalcTPSA(mol), 2)


def _calc_hbd(mol: Mol) -> int:
    """
    H-bond donors según definición de Lipinski.
    Cuenta NH y OH (nitrógenos y oxígenos con hidrógenos unidos).
    """
    return Lipinski.NumHDonors(mol)


def _calc_hba(mol: Mol) -> int:
    """
    H-bond acceptors según definición de Lipinski.
    Cuenta N y O (incluyendo los que ya son donors).

    Nota: la definición de Lipinski para HBA es más amplia que
    la de Ertl — cuenta todos los N y O, no solo los que aceptan
    en la práctica. Usamos Lipinski para consistencia con la regla.
    """
    return Lipinski.NumHAcceptors(mol)


def _calc_rotatable_bonds(mol: Mol) -> int:
    """
    Número de enlaces rotables.

    Excluye: enlaces en anillos, enlaces terminales (CH3, NH2),
    amidas, y enlaces dobles/triples.
    Incluye: enlace simples entre átomos no terminales fuera de anillos.

    Valor alto (> 10) indica molécula muy flexible — posible pérdida
    de entropía conformacional al unirse al receptor, reduciendo
    la afinidad efectiva.
    """
    return rdMolDescriptors.CalcNumRotatableBonds(mol)


def _calc_heavy_atoms(mol: Mol) -> int:
    """Número de átomos no-hidrógeno."""
    return mol.GetNumHeavyAtoms()


def _calc_ring_count(mol: Mol) -> int:
    """
    Número total de anillos (SSSR — Smallest Set of Smallest Rings).

    Moléculas con 0 anillos: raramente drug-like.
    Moléculas con 1–4 anillos: rango típico de fármacos.
    Moléculas con > 6 anillos: complejidad alta, posible baja solubilidad.
    """
    return rdMolDescriptors.CalcNumRings(mol)


def _calc_qed(mol: Mol) -> float:
    """
    Quantitative Estimate of Drug-likeness (QED).

    Score compuesto validado ampliamente que combina 8 propiedades moleculares
    usando funciones de deseabilidad derivadas de fármacos aprobados oralmente.

    Componentes: MW, logP, HBA, HBD, PSA, ROTB, AROM (anillos aromáticos),
    ALERTS (alertas estructurales).

    Rango: 0.0 (menos drug-like) a 1.0 (más drug-like).
    - >0.67: favorable
    - 0.49–0.67: moderado
    - <0.49: desfavorable

    Referencia:
        Bickerton GR, Paolini GV, Besnard J, Muresan S, Hopkins AL.
        "Quantifying the chemical beauty of drugs."
        Nature Chemistry. 2012;4:90-98. DOI: 10.1038/nchem.1243

    Implementado directamente en RDKit desde la versión 2012.06.
    """
    return round(QED.qed(mol), 4)


# ── Función principal ─────────────────────────────────────────────────────────

def calculate_properties(smiles: str) -> PhysicochemicalProperties:
    """
    Calcula todas las propiedades fisicoquímicas de una molécula.

    Args:
        smiles: SMILES de la molécula (no necesita ser canónico).
                Se valida y canonicaliza internamente.

    Retorna:
        PhysicochemicalProperties con todos los valores calculados
        y los flags de drug-likeness.

    Lanza:
        InvalidSMILES si el SMILES no es válido (de validate_smiles_or_raise)
        PropertyCalculationError si RDKit falla calculando una propiedad
        específica en una molécula válida (raro pero posible con átomos exóticos)

    Ejemplo:
        props = calculate_properties("CC(=O)Oc1ccccc1C(=O)O")  # aspirina
        print(props.molecular_weight)   # 180.16
        print(props.lipinski_pass)      # True
    """
    # Paso 1: validar y obtener el mol object canónico
    validation: ValidationResult = validate_smiles_or_raise(smiles)
    mol = Chem.MolFromSmiles(validation.canonical_smiles)

    if mol is None:
        # Esto no debería ocurrir si validate_smiles_or_raise pasó,
        # pero lo manejamos defensivamente
        raise PropertyCalculationError(
            property_name="mol_object",
            smiles=smiles,
            detail="RDKit no pudo reconstruir la molécula desde el SMILES canónico",
        )

    log.debug(
        "calculando propiedades fisicoquímicas",
        canonical_smiles=validation.canonical_smiles,
        formula=validation.molecular_formula,
    )

    # Paso 2: calcular cada propiedad individualmente
    # Capturamos excepciones por propiedad para dar mensajes de error precisos
    try:
        mw = _calc_molecular_weight(mol)
    except Exception as e:
        raise PropertyCalculationError("molecular_weight", smiles, detail=str(e)) from e

    try:
        log_p = _calc_log_p(mol)
    except Exception as e:
        raise PropertyCalculationError("log_p", smiles, detail=str(e)) from e

    try:
        tpsa = _calc_tpsa(mol)
    except Exception as e:
        raise PropertyCalculationError("tpsa", smiles, detail=str(e)) from e

    try:
        hbd = _calc_hbd(mol)
        hba = _calc_hba(mol)
    except Exception as e:
        raise PropertyCalculationError("hbd/hba", smiles, detail=str(e)) from e

    try:
        rot_bonds = _calc_rotatable_bonds(mol)
        heavy_atoms = _calc_heavy_atoms(mol)
        ring_count = _calc_ring_count(mol)
    except Exception as e:
        raise PropertyCalculationError("descriptors", smiles, detail=str(e)) from e

    try:
        qed_score = _calc_qed(mol)
    except Exception as e:
        raise PropertyCalculationError("qed", smiles, detail=str(e)) from e

    # Paso 3: evaluar drug-likeness
    lipinski_pass, lipinski_violations = LipinskiRule.evaluate(mw, log_p, hbd, hba)
    veber_pass, veber_violations = VerberRule.evaluate(rot_bonds, tpsa)

    if lipinski_violations:
        log.info(
            "Lipinski violations detectadas",
            violations=lipinski_violations,
            formula=validation.molecular_formula,
        )

    # Paso 4: construir el resultado
    # El model_validator de PhysicochemicalProperties verifica
    # automáticamente que lipinski_pass es coherente con los valores
    props = PhysicochemicalProperties(
        molecular_weight=mw,
        log_p=log_p,
        tpsa=tpsa,
        hbd=hbd,
        hba=hba,
        rotatable_bonds=rot_bonds,
        heavy_atom_count=heavy_atoms,
        ring_count=ring_count,
        qed=qed_score,
        lipinski_pass=lipinski_pass,
        veber_pass=veber_pass,
    )

    log.info(
        "propiedades calculadas",
        formula=validation.molecular_formula,
        mw=mw,
        log_p=log_p,
        tpsa=tpsa,
        lipinski_pass=lipinski_pass,
        veber_pass=veber_pass,
    )

    return props


def get_lipinski_violations(props: PhysicochemicalProperties) -> list[str]:
    """
    Retorna la lista de violaciones de Lipinski para un conjunto
    de propiedades ya calculadas.

    Usado por scoring/engine.py para generar el improvement_hint
    en ScoreBreakdown — le dice al usuario exactamente qué propiedad
    mejorar en su próxima modificación molecular.

    Ejemplo:
        violations = get_lipinski_violations(props)
        # ["MW=542.3 > 500.0", "logP=5.8 > 5.0"]
        # → hint: "Reduce el peso molecular y el logP"
    """
    _, violations = LipinskiRule.evaluate(
        props.molecular_weight,
        props.log_p,
        props.hbd,
        props.hba,
    )
    return violations


def get_veber_violations(props: PhysicochemicalProperties) -> list[str]:
    """
    Retorna la lista de violaciones de Veber para propiedades ya calculadas.
    """
    _, violations = VerberRule.evaluate(props.rotatable_bonds, props.tpsa)
    return violations


def summarize_adme_profile(props: PhysicochemicalProperties) -> str:
    """
    Genera un resumen textual del perfil ADME para el reporte de IA.

    Este string se incluye en el AIReportRequest que recibe
    services/ai/interpreter.py — le da contexto estructurado
    a Claude para que el reporte narrativo sea científicamente preciso.

    Ejemplo de output:
        "MW=180.2 Da, logP=1.2, TPSA=63.6 Å², HBD=1, HBA=4,
         RotBonds=3. Lipinski: PASS. Veber: PASS.
         Perfil compatible con absorción oral buena."
    """
    lipinski_str = "PASS" if props.lipinski_pass else "FAIL"
    veber_str    = "PASS" if props.veber_pass else "FAIL"

    # Predicción cualitativa de absorción oral
    if props.lipinski_pass and props.veber_pass:
        absorption = "Perfil compatible con buena absorción oral."
    elif props.lipinski_pass and not props.veber_pass:
        absorption = "Absorción oral posible pero limitada por flexibilidad/polaridad."
    else:
        lipinski_violations = get_lipinski_violations(props)
        absorption = (
            f"Absorción oral probablemente pobre. "
            f"Violaciones Lipinski: {', '.join(lipinski_violations)}."
        )

    return (
        f"MW={props.molecular_weight} Da, "
        f"logP={props.log_p}, "
        f"TPSA={props.tpsa} Å², "
        f"HBD={props.hbd}, HBA={props.hba}, "
        f"RotBonds={props.rotatable_bonds}. "
        f"QED={props.qed:.3f}. "
        f"Lipinski: {lipinski_str}. Veber: {veber_str}. "
        f"{absorption}"
    )
