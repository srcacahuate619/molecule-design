"""
chem/conformer.py

Generación de estructuras 3D (conformers) desde SMILES usando RDKit.

El proceso SMILES → 3D tiene tres pasos:

1. SMILES → mol 2D (grafo molecular con hidrógenos implícitos)
2. mol 2D → mol 3D (ETKDG asigna coordenadas xyz a cada átomo)
3. mol 3D → optimización de geometría (MMFF94 minimiza la energía)

Por qué ETKDG y no otros métodos:
    ETKDG (Experimental Torsion Knowledge Distance Geometry) usa
    distribuciones de ángulos diedros de estructuras cristalográficas
    reales (Cambridge Structural Database) para generar conformers
    más realistas que los métodos puramente geométricos.
    Es el método por defecto de RDKit desde 2016 y el más usado
    en pipelines de virtual screening.

Limitaciones conocidas:
    - Macrociclos (anillos > 8 átomos): ETKDG falla frecuentemente.
      Requiere métodos alternativos (RDKit MacroModel, OMEGA).
    - Quiralidad no especificada: RDKit elige arbitrariamente.
      El usuario debe especificar @/@@  en el SMILES si importa.
    - Moléculas muy rígidas (muchos anillos fusionados): puede
      requerir más intentos para encontrar una geometría válida.

El output es un archivo .sdf que se guarda en MinIO y se pasa
a AutoDock Vina para el docking.
"""

import os
import tempfile
from pathlib import Path

from rdkit import Chem
from rdkit.Chem import AllChem, rdMolDescriptors
from rdkit.Chem.rdchem import Mol
from rdkit.Chem.rdForceFieldHelpers import MMFFGetMoleculeProperties, MMFFOptimizeMolecule

from chem.validator import validate_smiles_or_raise
from core.config import get_settings
from core.exceptions import ConformerGenerationError
from core.models import ValidationResult
from utils.file_handlers import StoragePath, upload_text
from utils.logger import get_logger

log = get_logger(__name__)
settings = get_settings()


# ── Parámetros de ETKDG ───────────────────────────────────────────────────────

def _get_etkdg_params(random_seed: int = 42) -> AllChem.EmbedParameters:
    """
    Configura los parámetros del algoritmo ETKDG.

    random_seed: semilla para reproducibilidad. Cambiamos la semilla
    en cada reintento para explorar distintas soluciones geométricas.

    ETKDGv3 es la versión más reciente (RDKit >= 2020.09) e incluye
    mejoras para macrociclos y moléculas con múltiples centros quirales.
    """
    params = AllChem.ETKDGv3()
    params.randomSeed = random_seed
    params.numThreads = 0           # 0 = usar todos los cores disponibles
    params.maxIterations = 1000     # intentos de embedding antes de fallar
    params.pruneRmsThresh = 0.1     # descarta conformers muy similares entre sí
    params.enforceChirality = True  # respeta los centros quirales del SMILES
    params.useSmallRingTorsions = True   # mejor geometría para anillos pequeños
    params.useMacrocycleTorsions = True  # mejor para macrociclos (si aplica)
    return params


# ── Optimización de geometría ─────────────────────────────────────────────────

def _optimize_with_mmff(mol: Mol) -> tuple[Mol, bool]:
    """
    Optimiza la geometría del conformer con el campo de fuerza MMFF94.

    MMFF94 (Merck Molecular Force Field) minimiza la energía potencial
    del conformer ajustando las coordenadas xyz. Produce geometrías más
    realistas que el embedding puro de ETKDG.

    Retorna (mol_optimizado, convergio):
        convergio=True  → minimización exitosa
        convergio=False → minimización parcial (mol aún usable pero
                          la geometría puede ser subóptima)

    Si MMFF94 no tiene parámetros para algún átomo (raro pero posible
    con elementos exóticos), cae a UFF (Universal Force Field) como backup.
    """
    # Intentar MMFF94 primero
    try:
        ff_props = MMFFGetMoleculeProperties(mol, mmffVariant="MMFF94")
        if ff_props is not None:
            result = MMFFOptimizeMolecule(mol, mmffVariant="MMFF94", maxIters=2000)
            converged = (result == 0)   # 0 = convergió, 1 = no convergió, -1 = error
            if result != -1:
                return mol, converged
    except Exception as e:
        log.debug("MMFF94 falló, intentando UFF", error=str(e))

    # Fallback a UFF
    try:
        result = AllChem.UFFOptimizeMolecule(mol, maxIters=2000)
        converged = (result == 0)
        return mol, converged
    except Exception as e:
        log.warning("UFF también falló — usando geometría sin optimizar", error=str(e))
        return mol, False


# ── Detección de macrociclos ──────────────────────────────────────────────────

def _has_macrocycle(mol: Mol) -> bool:
    """
    Detecta si la molécula contiene macrociclos (anillos > 8 átomos).

    ETKDG tiene más dificultades con macrociclos — aumentamos los
    intentos automáticamente si se detecta uno.
    """
    ring_info = mol.GetRingInfo()
    for ring in ring_info.AtomRings():
        if len(ring) > 8:
            return True
    return False


def _get_ring_size_info(mol: Mol) -> str:
    """Resumen de tamaños de anillos para logging."""
    ring_info = mol.GetRingInfo()
    sizes = sorted({len(r) for r in ring_info.AtomRings()})
    return str(sizes) if sizes else "sin anillos"


# ── Función principal ─────────────────────────────────────────────────────────

async def generate_conformer(smiles: str) -> dict:
    """
    Genera una estructura 3D para la molécula y la guarda en MinIO.

    Args:
        smiles: SMILES de la molécula. Se valida internamente.

    Retorna dict con:
        canonical_smiles:  SMILES canónico usado
        smiles_hash:       hash SHA-256 del canónico
        conformer_path:    ruta del .sdf en MinIO
        num_atoms_3d:      número de átomos en la estructura 3D
        optimization_converged: si la minimización MMFF convergió
        had_macrocycle:    si se detectó macrociclo (info para el usuario)

    Lanza:
        InvalidSMILES           → SMILES no válido
        ConformerGenerationError → no se pudo generar estructura 3D
    """
    # Paso 1: validar SMILES
    validation: ValidationResult = validate_smiles_or_raise(smiles)
    canonical = validation.canonical_smiles
    # NOTA: smiles_hash se recalculará DESPUÉS de la protonación (ver abajo)

    log.info(
        "generando conformer 3D",
        formula=validation.molecular_formula,
        heavy_atoms=validation.heavy_atom_count,
        hash_prefix=validation.smiles_hash[:8],
    )

    # Paso 2: Tautomería canónica y protonación fisiológica
    try:
        from rdkit.Chem.MolStandardize import rdMolStandardize
        te = rdMolStandardize.TautomerEnumerator()
        mol_tmp = Chem.MolFromSmiles(canonical)
        if mol_tmp:
            canonical_tautomer = te.Canonicalize(mol_tmp)
            canonical = Chem.MolToSmiles(canonical_tautomer)
            log.debug("Tautómero canónico generado", smiles=canonical)
    except Exception as e:
        log.warning("Error enumerando tautómeros, usando SMILES original", error=str(e))

    try:
        import dimorphite_dl
        # dimorphite_dl devuelve una lista de SMILES protonados
        protonated_list = dimorphite_dl.protonate_smiles(
            canonical, 
            ph_min=7.4, 
            ph_max=7.4, 
            precision=1.0
        )
        if protonated_list:
            canonical = protonated_list[0]
            log.info("SMILES protonado a pH 7.4 con dimorphite-dl", protonated_smiles=canonical)
    except ImportError:
        log.warning("dimorphite_dl no instalado. Usando SMILES neutro (sin corrección de pH).")
    except Exception as e:
        log.warning("Error en dimorphite_dl, usando neutro", error=str(e))

    # [FIX] Recalcular el hash con el SMILES FINAL (post-tautomería + post-protonación).
    # El archivo en MinIO debe guardarse con el mismo hash que vina_service usará para buscarlo.
    # Si no recalculamos aquí, dimorphite puede cambiar el SMILES (ej. protonando un nitrógeno)
    # y el hash original (del SMILES neutro) no coincidirá con la ruta guardada.
    import hashlib as _hashlib
    smiles_hash = _hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    log.debug("hash recalculado post-protonación", hash_prefix=smiles_hash[:8])

    # Los H explícitos son necesarios para que ETKDG coloque
    # correctamente los átomos de hidrógeno en 3D
    mol = Chem.MolFromSmiles(canonical)
    if mol is None:
        raise ConformerGenerationError(
            smiles=smiles,
            attempts=1,
            detail="Fallo al construir RDKit Mol tras protonación."
        )
    mol = Chem.AddHs(mol)

    # Detectar macrociclos para ajustar número de intentos
    has_macro = _has_macrocycle(mol)
    ring_info = _get_ring_size_info(mol)

    if has_macro:
        log.info(
            "macrociclo detectado — aumentando intentos de embedding",
            ring_sizes=ring_info,
        )

    # Número de intentos según complejidad
    max_attempts = settings.conformer_max_attempts
    if has_macro:
        max_attempts = max_attempts * 2   # doble de intentos para macrociclos

    # Paso 3: intentar generar conformer con distintas semillas
    mol_3d = None
    last_error = None

    for attempt in range(max_attempts):
        seed = 42 + (attempt * 137)   # semillas distintas en cada intento
        params = _get_etkdg_params(random_seed=seed)

        try:
            mol_copy = Chem.RWMol(mol)  # copia para no modificar el original
            result = AllChem.EmbedMolecule(mol_copy, params)

            if result == 0:
                # Embedding exitoso
                mol_3d = mol_copy.GetMol()
                log.debug(
                    "embedding exitoso",
                    attempt=attempt + 1,
                    seed=seed,
                )
                break
            elif result == -1:
                last_error = f"EmbedMolecule retornó -1 en intento {attempt + 1} (seed={seed})"
                log.debug("embedding falló", attempt=attempt + 1, seed=seed)

        except Exception as e:
            last_error = str(e)
            log.debug(
                "excepción en embedding",
                attempt=attempt + 1,
                error=str(e),
            )

    if mol_3d is None:
        # MITIGACIÓN NIVEL 2: Bypass progresivo de ETKDG para moléculas rígidas/tensionadas/macrociclos
        log.info("ETKDG estándar falló — iniciando cadena de mitigación de Nivel 2")

        # Mitigación 1: Intentar con useRandomCoords=True
        try:
            log.info("Mitigación 1: Intentando embedding con coordenadas aleatorias (useRandomCoords=True)")
            mol_copy = Chem.RWMol(mol)
            params = _get_etkdg_params(random_seed=42)
            params.useRandomCoords = True
            result = AllChem.EmbedMolecule(mol_copy, params)
            if result == 0:
                mol_3d = mol_copy.GetMol()
                log.info("Mitigación 1 exitosa — conformero generado usando coordenadas aleatorias")
        except Exception as e:
            log.warning("Mitigación 1 falló con excepción", error=str(e))

    if mol_3d is None:
        # Mitigación 2: Fallback 2D -> 3D con perturbación y minimización UFF
        try:
            log.info("Mitigación 2: Intentando fallback 2D -> 3D con perturbación en Z y minimización UFF")
            mol_copy = Chem.RWMol(mol)
            # Generar coordenadas 2D
            AllChem.Compute2DCoords(mol_copy)
            conf = mol_copy.GetConformer(0)
            
            # Perturbar Z para evitar estados perfectamente planos y permitir que el campo de fuerzas actúe en 3D
            import random
            random.seed(42)
            for i in range(mol_copy.GetNumAtoms()):
                pos = conf.GetAtomPosition(i)
                conf.SetAtomPosition(i, (pos.x, pos.y, random.uniform(-0.1, 0.1)))
            conf.Set3D(True)
            
            # Minimizar con UFF para corregir distancias y choques estéricos
            uff_result = AllChem.UFFOptimizeMolecule(mol_copy, maxIters=1000)
            
            mol_3d = mol_copy.GetMol()
            log.info("Mitigación 2 exitosa — conformero 3D generado vía fallback 2D-3D + UFF", uff_result=uff_result)
        except Exception as e:
            log.error("Mitigación 2 falló con excepción", error=str(e))

    if mol_3d is None:
        raise ConformerGenerationError(
            smiles=smiles,
            attempts=max_attempts,
            detail=(
                f"ETKDG estándar y mitigaciones de Nivel 2 fallaron en generar una estructura 3D válida. "
                f"Anillos detectados: {ring_info}. "
                f"Último error de ETKDG: {last_error}."
            ),
        )


    # Paso 4: optimizar geometría con MMFF94
    mol_3d, converged = _optimize_with_mmff(mol_3d)

    if not converged:
        log.warning(
            "optimización MMFF no convergió — geometría subóptima",
            formula=validation.molecular_formula,
        )

    # Paso 5: conservar H explícitos antes de guardar
    # mk_prepare_ligand de Meeko requiere hidrógenos explícitos en la molécula
    # de entrada para parametrizar correctamente el ligando.
    mol_final = mol_3d

    # Paso 6: convertir a SDF y guardar en MinIO
    sdf_content = _mol_to_sdf_string(mol_final, canonical)

    object_path = StoragePath.ligand_conformer(smiles_hash)
    await upload_text(
        text=sdf_content,
        object_name=object_path,
    )

    num_atoms_3d = mol_final.GetNumAtoms()

    log.info(
        "conformer generado y guardado",
        formula=validation.molecular_formula,
        num_atoms_3d=num_atoms_3d,
        converged=converged,
        had_macrocycle=has_macro,
        path=object_path,
        final_hash_prefix=smiles_hash[:8],
    )

    return {
        "canonical_smiles":        canonical,
        "smiles_hash":             smiles_hash,   # hash del SMILES final (post-protonación)
        "conformer_path":          object_path,
        "num_atoms_3d":            num_atoms_3d,
        "optimization_converged":  converged,
        "had_macrocycle":          has_macro,
        "molecular_formula":       validation.molecular_formula,
    }


# ── Serialización SDF ─────────────────────────────────────────────────────────

def _mol_to_sdf_string(mol: Mol, canonical_smiles: str) -> str:
    """
    Convierte un mol 3D a formato SDF como string.

    Incluye el SMILES canónico como propiedad del SDF para que
    el archivo sea trazable — si alguien abre el .sdf directamente
    puede ver de qué molécula proviene.

    El writer de RDKit produce SDF v2000 por defecto, compatible
    con AutoDock Vina y prácticamente cualquier software químico.
    """
    import io as _io
    buffer = _io.StringIO()
    writer = Chem.SDWriter(buffer)

    # Añadir SMILES canónico como propiedad del SDF
    mol.SetProp("SMILES", canonical_smiles)

    writer.write(mol)
    writer.close()

    return buffer.getvalue()


# ── Utilidad para lectura ─────────────────────────────────────────────────────

def sdf_string_to_mol(sdf_content: str) -> Mol | None:
    """
    Parsea un string SDF y retorna el primer mol encontrado.

    Útil en services/docking/vina_service.py para leer el conformer
    descargado de MinIO antes de prepararlo para Vina.

    Retorna None si el SDF está vacío o malformado.
    """
    supplier = Chem.SDMolSupplier()
    supplier.SetData(sdf_content, sanitize=True, removeHs=False)

    for mol in supplier:
        if mol is not None:
            return mol

    return None
