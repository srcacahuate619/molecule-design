"""
rescoring/feature_extractor.py

Extracción de features 3D de interacción proteína-ligando para ML rescoring.

Estrategia de features (3 grupos):
  A. Descriptores 1D/2D moleculares (pre-calculados por backend con RDKit):
     MW, LogP, TPSA, HBD, HBA, RotBonds, QED
  B. Features de Vina:
     best_score, pose_score_variance, pose_score_range, poses_passing_ratio
  C. Features de interacción 3D (extraídas aquí):
     H-bonds, contactos hidrofóbicos, puentes salinos, π-stacking,
     π-catión, coordinación metálica, contactos cercanos

Librería de extracción 3D: ProLIF + MDAnalysis
  - ProLIF (Protein-Ligand Interaction Fingerprints): detecta interacciones
    no-covalentes usando criterios geométricos basados en distancias y ángulos
    publicados. Ref: Bouysset & Fiorucci, 2021, DOI: 10.1186/s13321-021-00548-6
  - MDAnalysis: cálculo de distancias atómicas para contactos cercanos.

  Nota histórica: Este módulo originalmente usaba ODDT. Se migró a ProLIF porque:
    1. ODDT depende de `six` (deprecated) y no compila con Python >= 3.13
    2. ProLIF usa RDKit nativo (ya instalado) + MDAnalysis
    3. ProLIF está activamente mantenido y publicado en journal peer-reviewed

Degradación elegante:
  Si ProLIF/MDAnalysis no están disponibles, o si un archivo PDB/SDF no se puede
  parsear, las features 3D se reportan como 0.0 con warning explícito en logs.
  Esto NO es un crash silencioso: el reporte de training incluye `n_failed_3d`.

Limitaciones documentadas:
  - Las interacciones dependen de la protonación.  Los PDB de PDBbind no tienen
    hidrógenos optimizados; ProLIF agrega H via RDKit — esto es una aproximación.
  - La detección de π-stacking y π-catión depende de la aromaticidad asignada
    por RDKit, que puede diferir de la realidad cuántica.
  - Los contactos cercanos cuentan átomos de proteína incluyendo H si presentes.
  - MetalAcceptor requiere metales correctamente tipados en el PDB.

Optimización de binding site:
  ProLIF convierte el AtomGroup de MDAnalysis a molécula RDKit internamente.
  Convertir una proteína completa (>3,000 átomos) tarda ~25 s por la inferencia
  de órdenes de enlace.  Seleccionar solo los residuos del binding site
  (dentro de BINDING_SITE_CUTOFF Å del ligando) reduce a ~200-600 átomos y
  acelera la conversión a ~1-3 s, además de eliminar interacciones espúreas
  con regiones distantes de la proteína.
"""

from __future__ import annotations

import os
import tempfile
import warnings
from pathlib import Path
from typing import Any

import numpy as np

from logger import get_logger

log = get_logger(__name__)


# ─────────────────────────────────────────────────────────────
# Constantes públicas — contrato con train_pipeline.py
# ─────────────────────────────────────────────────────────────

INTERACTION_FEATURES: list[str] = [
    "hbond_donor_count",        # H-bonds donde el ligando es donor
    "hbond_acceptor_count",     # H-bonds donde el ligando es acceptor
    "hydrophobic_contacts",     # Contactos hidrofóbicos (C-C, ~4.5 Å)
    "salt_bridges",             # Puentes salinos (carga+ ↔ carga-, ~4.0 Å)
    "pi_stacking",              # π-stacking (face-to-face + edge-to-face)
    "pi_cation",                # Interacciones π-catión
    "metal_coordination",       # Coordinación con iones metálicos
    "close_contacts_4A",        # Átomos de proteína a < 4 Å del ligando
    "close_contacts_6A",        # Átomos de proteína a < 6 Å del ligando
]

# Cutoff en Å para selección de binding site.
# Solo residuos de proteína con algún átomo dentro de este radio respecto
# a cualquier átomo del ligando son pasados a ProLIF.
# 10 Å es estándar en docking (Vina usa ~8 Å para grid).
# close_contacts_6A se calcula aparte sobre the whole protein selection.
BINDING_SITE_CUTOFF: float = 10.0

# Mapeo ProLIF interaction types → nuestras categorías acumulativas.
# ProLIF detecta interacciones individuales por par de residuos.
# Nosotros acumulamos conteos por tipo para obtener un feature vector fijo.
_PROLIF_TYPE_TO_FEATURE: dict[str, str] = {
    "HBDonor":       "hbond_donor_count",
    "HBAcceptor":    "hbond_acceptor_count",
    "Hydrophobic":   "hydrophobic_contacts",
    "Anionic":       "salt_bridges",
    "Cationic":      "salt_bridges",
    "PiStacking":    "pi_stacking",
    "FaceToFace":    "pi_stacking",
    "EdgeToFace":    "pi_stacking",
    "PiCation":      "pi_cation",
    "CationPi":      "pi_cation",
    "MetalAcceptor": "metal_coordination",
}


# ─────────────────────────────────────────────────────────────
# Funciones utilitarias (módulo-level)
# ─────────────────────────────────────────────────────────────

def zero_interaction_features() -> dict[str, float]:
    """
    Retornar dict de features 3D en cero.

    Uso legítimo:
      - Degradación elegante cuando la extracción falla.
      - Cuando skip_structure_checks=True en el pipeline de training.
      - En ablation testing de Group B/C con features vaciadas.
    """
    return {feat: 0.0 for feat in INTERACTION_FEATURES}


def check_prolif_available() -> bool:
    """Verificar que ProLIF y MDAnalysis son importables."""
    try:
        import prolif          # noqa: F401
        import MDAnalysis      # noqa: F401
        return True
    except ImportError:
        return False


# ─────────────────────────────────────────────────────────────
# Clase principal
# ─────────────────────────────────────────────────────────────

class InteractionFeatureExtractor:
    """
    Extrae features de interacción 3D proteína-ligando.

    Dos modos de operación:

    1. **Training** (PDBbind): ``extract_from_files(protein_pdb, ligand_sdf)``
       Lee archivos de estructura cristalográfica.

    2. **Inferencia** (post-docking): ``extract_from_pose(pdbqt, target_pdb)``
       Recibe el output PDBQT de Vina + el PDB del target.

    En ambos casos, el output es un dict con las 9 keys de
    ``INTERACTION_FEATURES``, siempre en el mismo orden.
    """

    def __init__(self) -> None:
        self._prolif_ok = check_prolif_available()
        if not self._prolif_ok:
            log.warning(
                "prolif_not_available",
                msg=(
                    "ProLIF no disponible. Features 3D serán cero. "
                    "Instale con: pip install prolif"
                ),
            )

    @property
    def is_available(self) -> bool:
        """True si ProLIF + MDAnalysis están instalados."""
        return self._prolif_ok

    # ─── Training: extracción desde archivos PDB + SDF ───────

    def extract_from_files(
        self,
        protein_pdb_path: str | Path,
        ligand_sdf_path: str | Path,
    ) -> dict[str, float]:
        """
        Extraer features 3D desde archivos PDB (proteína) + SDF (ligando).

        Usado durante el entrenamiento con complejos co-cristalizados de PDBbind.

        Args:
            protein_pdb_path: path al PDB de la proteína
            ligand_sdf_path: path al SDF del ligando co-cristalizado

        Returns:
            dict con 9 keys (INTERACTION_FEATURES). Valores 0.0 si falla.
        """
        if not self._prolif_ok:
            return zero_interaction_features()

        protein_pdb_path = Path(protein_pdb_path)
        ligand_sdf_path = Path(ligand_sdf_path)

        if not protein_pdb_path.exists():
            log.warning("protein_file_missing", path=str(protein_pdb_path))
            return zero_interaction_features()

        if not ligand_sdf_path.exists():
            log.warning("ligand_file_missing", path=str(ligand_sdf_path))
            return zero_interaction_features()

        try:
            return self._extract_from_pdb_sdf(
                str(protein_pdb_path), str(ligand_sdf_path)
            )
        except Exception as e:
            log.warning(
                "extraction_failed_files",
                error=str(e),
                protein=protein_pdb_path.name,
                ligand=ligand_sdf_path.name,
            )
            return zero_interaction_features()

    # ─── Inferencia: extracción desde PDBQT (pose Vina) ─────

    def extract_from_pose(
        self,
        pose_pdbqt_block: str,
        target_pdb_path: str | Path,
        smiles: str = "",
    ) -> dict[str, float]:
        """
        Extraer features 3D de una pose de docking (output de Vina).

        Usado por el microservicio de rescoring en inferencia.

        Args:
            pose_pdbqt_block: contenido PDBQT completo de una pose
            target_pdb_path: path al PDB del target
            smiles: SMILES del ligando (solo para logging)

        Returns:
            dict con 9 keys (INTERACTION_FEATURES). Valores 0.0 si falla.

        Limitación: PDBQT → MDAnalysis Universe no siempre preserva
        aromaticidad, lo que puede afectar π-stacking.
        """
        if not self._prolif_ok:
            return zero_interaction_features()

        try:
            return self._extract_from_pdbqt(
                pose_pdbqt_block, str(target_pdb_path)
            )
        except Exception as e:
            log.warning(
                "extraction_failed_pose",
                error=str(e),
                smiles=smiles[:50] if smiles else "N/A",
            )
            return zero_interaction_features()

    # ─────────────────────────────────────────────────────────
    # Implementación interna
    # ─────────────────────────────────────────────────────────

    def _extract_from_pdb_sdf(
        self,
        protein_pdb: str,
        ligand_sdf: str,
    ) -> dict[str, float]:
        """
        Pipeline completo de extracción de interacciones desde PDB + SDF.

        Flujo optimizado:
          1. Cargar ligando con RDKit (rápido, robusto)
          2. Obtener coordenadas 3D del ligando
          3. Cargar proteína con MDAnalysis, seleccionar solo "protein"
          4. Seleccionar binding site: residuos con algún átomo < 10 Å
             del ligando (byres para residuos completos)
          5. Convertir binding site a ProLIF Molecule (con fallback de H)
          6. Ejecutar ProLIF Fingerprint sobre binding site + ligando
          7. Mapear conteos a nuestras 9 categorías
          8. Calcular close_contacts separadamente con distancias directas

        Optimización de binding site:
          La conversión MDAnalysis → RDKit (internamente en ProLIF) requiere
          inferencia de bond orders que escala ~O(n²) con átomos de proteína.
          Una proteína de 3,000 átomos tarda ~25s; un binding site de 400
          átomos tarda ~1-3s.  Además, solo las interacciones locales son
          físicamente relevantes.
        """
        import prolif
        import MDAnalysis as mda
        from MDAnalysis.analysis.distances import distance_array

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")

            # 1. Ligando (via RDKit para robustez)
            rdmol = _load_ligand_sdf_rdkit(ligand_sdf)
            if rdmol is None:
                log.warning(
                    "ligand_sdf_unreadable",
                    path=ligand_sdf,
                    msg="RDKit no pudo parsear el SDF",
                )
                return zero_interaction_features()

            # 2. Coordenadas del ligando
            lig_coords = _get_rdmol_coords(rdmol)
            if lig_coords is None or len(lig_coords) == 0:
                log.warning("ligand_no_3d_coords", path=ligand_sdf)
                return zero_interaction_features()

            # 3. Proteína — seleccionar solo aminoácidos
            prot_u = mda.Universe(protein_pdb)
            prot_all = prot_u.select_atoms("protein")

            if len(prot_all) == 0:
                log.warning(
                    "no_protein_atoms_selected",
                    path=protein_pdb,
                    total_atoms=len(prot_u.atoms),
                )
                return zero_interaction_features()

            # 4. Binding site selection (10 Å cutoff, by complete residues)
            binding_site = _select_binding_site(
                prot_all, lig_coords, cutoff=BINDING_SITE_CUTOFF
            )

            if len(binding_site) == 0:
                log.warning(
                    "empty_binding_site",
                    path=protein_pdb,
                    cutoff=BINDING_SITE_CUTOFF,
                    n_protein_atoms=len(prot_all),
                )
                return zero_interaction_features()

            # 5. Convertir binding site a ProLIF Molecule (con fallback H)
            prot_mol = _protein_to_prolif(binding_site)
            if prot_mol is None:
                log.warning(
                    "protein_prolif_conversion_failed",
                    path=protein_pdb,
                    n_atoms=len(binding_site),
                )
                return zero_interaction_features()

            lig_mol = prolif.Molecule(rdmol)

            # 6. ProLIF fingerprint
            fp = prolif.Fingerprint()
            fp.run_from_iterable([lig_mol], prot_mol, progress=False)
            df = fp.to_dataframe()

            # 7. Mapear interacciones
            features = _map_prolif_dataframe(df)

            # 8. Contactos cercanos (usa prot_all, no solo binding site,
            #    para no subestimar close_contacts_6A)
            cc = _compute_close_contacts_mda(prot_all, rdmol)
            features["close_contacts_4A"] = cc[0]
            features["close_contacts_6A"] = cc[1]

        return features

    def _extract_from_pdbqt(
        self,
        pdbqt_block: str,
        target_pdb: str,
    ) -> dict[str, float]:
        """
        Pipeline de extracción desde PDBQT (docking) + PDB (target).

        El PDBQT se escribe en un archivo temporal para que MDAnalysis lo
        pueda parsear como topology. Luego se aplica el mismo pipeline
        binding-site-optimizado que _extract_from_pdb_sdf.
        """
        import prolif
        import MDAnalysis as mda

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")

            # Ligando (PDBQT → archivo temporal → MDAnalysis)
            fd, tmp_path = tempfile.mkstemp(suffix=".pdbqt")
            try:
                with os.fdopen(fd, "w") as f:
                    f.write(pdbqt_block)
                lig_u = mda.Universe(tmp_path)
                lig_coords = lig_u.atoms.positions
            finally:
                if os.path.exists(tmp_path):
                    os.unlink(tmp_path)

            if len(lig_coords) == 0:
                return zero_interaction_features()

            # Proteína — seleccionar aminoácidos + binding site
            prot_u = mda.Universe(target_pdb)
            prot_all = prot_u.select_atoms("protein")

            if len(prot_all) == 0:
                log.warning("no_protein_atoms_selected_inference", path=target_pdb)
                return zero_interaction_features()

            binding_site = _select_binding_site(
                prot_all, lig_coords, cutoff=BINDING_SITE_CUTOFF
            )

            if len(binding_site) == 0:
                return zero_interaction_features()

            prot_mol = _protein_to_prolif(binding_site)
            if prot_mol is None:
                log.warning("protein_prolif_conversion_failed_inference", path=target_pdb)
                return zero_interaction_features()

            lig_mol = prolif.Molecule.from_mda(lig_u)

            # Fingerprint
            fp = prolif.Fingerprint()
            fp.run_from_iterable([lig_mol], prot_mol, progress=False)
            df = fp.to_dataframe()

            features = _map_prolif_dataframe(df)

            # Contactos cercanos
            try:
                cc = _compute_close_contacts_from_universes(prot_all, lig_u)
                features["close_contacts_4A"] = cc[0]
                features["close_contacts_6A"] = cc[1]
            except Exception:
                pass

        return features


# ─────────────────────────────────────────────────────────────
# Funciones helper (privadas al módulo)
# ─────────────────────────────────────────────────────────────

def _load_ligand_sdf_rdkit(sdf_path: str):
    """
    Cargar un ligando desde SDF con RDKit.

    Intenta parsing normal primero. Si falla, reintenta con sanitización
    relajada (sin SANITIZE_PROPERTIES) que tolera SDF de PDBbind con
    átomos marcados como aromáticos fuera de anillo.

    Returns:
        RDKit Mol con coordenadas 3D, o None si no se pudo parsear.
    """
    from rdkit import Chem

    # Intento 1: parsing estándar (preserva H explícitos)
    supplier = Chem.SDMolSupplier(sdf_path, removeHs=False)
    try:
        mol = next(supplier)
        if mol is not None:
            return mol
    except StopIteration:
        pass

    # Intento 2: parsing relajado
    mol = Chem.MolFromMolFile(sdf_path, removeHs=False, sanitize=False)
    if mol is not None:
        try:
            Chem.SanitizeMol(
                mol,
                Chem.SanitizeFlags.SANITIZE_ALL
                ^ Chem.SanitizeFlags.SANITIZE_PROPERTIES,
            )
            return mol
        except Exception:
            return None

    return None


def _get_rdmol_coords(rdmol) -> np.ndarray | None:
    """
    Extraer coordenadas 3D de un RDKit Mol como numpy array.

    Returns:
        ndarray shape (n_atoms, 3) o None si no hay conformer 3D.
    """
    try:
        conf = rdmol.GetConformer()
        return np.array([
            [conf.GetAtomPosition(i).x,
             conf.GetAtomPosition(i).y,
             conf.GetAtomPosition(i).z]
            for i in range(rdmol.GetNumAtoms())
        ])
    except Exception:
        return None


def _select_binding_site(
    protein_atomgroup,
    ligand_coords: np.ndarray,
    cutoff: float = 10.0,
) -> Any:
    """
    Seleccionar residuos del binding site por distancia al ligando.

    Estrategia:
      1. Calcular distancia mínima de cada átomo de proteína a cualquier
         átomo del ligando.
      2. Seleccionar átomos dentro del cutoff.
      3. Expandir a residuos completos (ProLIF necesita residuos enteros
         para detectar interacciones correctamente).

    Args:
        protein_atomgroup: MDAnalysis AtomGroup con "protein" selection
        ligand_coords: ndarray shape (n_lig_atoms, 3) en Å
        cutoff: radio en Å

    Returns:
        MDAnalysis AtomGroup con los residuos del binding site.

    Nota científica:
      10 Å es el cutoff estándar para definir binding site en docking.
      Vina usa ~8 Å para su grid box; 10 Å asegura capturar interacciones
      de segunda esfera y water-mediated contacts (si hubiera aguas).
    """
    from MDAnalysis.analysis.distances import distance_array

    prot_pos = protein_atomgroup.positions

    if len(prot_pos) == 0 or len(ligand_coords) == 0:
        return protein_atomgroup[[]]  # Empty AtomGroup

    # Distancias par-a-par: (n_prot, n_lig)
    dists = distance_array(prot_pos, ligand_coords.astype(np.float32))

    # Para cada átomo de proteína: distancia mínima a cualquier átomo del ligando
    min_dists = dists.min(axis=1)
    close_mask = min_dists < cutoff

    close_atoms = protein_atomgroup[close_mask]

    if len(close_atoms) == 0:
        return close_atoms

    # Expandir a residuos completos
    # (ProLIF necesita backbone + sidechain para detectar interacciones)
    resids = np.unique(close_atoms.resids)
    segids = np.unique(close_atoms.segids)

    # Build selection string for complete residues
    resid_str = " ".join(str(r) for r in resids)
    sel = f"resid {resid_str}"

    # If there are multiple segments, restrict to the relevant ones
    if len(segids) > 0 and not all(s == "" for s in segids):
        segid_str = " ".join(str(s) for s in segids)
        sel = f"({sel}) and segid {segid_str}"

    binding_site = protein_atomgroup.select_atoms(sel)

    log.debug(
        "binding_site_selected",
        n_residues=len(resids),
        n_atoms=len(binding_site),
        n_protein_total=len(protein_atomgroup),
        cutoff=cutoff,
    )

    return binding_site


def _protein_to_prolif(protein_atomgroup):
    """
    Convertir AtomGroup de MDAnalysis a ProLIF Molecule con fallback robusto.

    PDBbind structures frecuentemente tienen hidrógenos con valence inválida
    para RDKit (e.g., aguas mal eliminadas, H bridging, clash steric).
    ProLIF.Molecule.from_mda() requiere sanitización RDKit exitosa.

    Estrategia de 3 intentos:
      1. Con H → mejor precisión para H-bonds.
      2. Sin H → más robusto; ProLIF/RDKit infieren donors/acceptors
         por tipo atómico. Se usa force=True para bypasear el check
         de "no H found".
      3. Si todo falla → None (graceful degradation a zeros)

    Limitación: Sin H explícitos, la dirección exacta de H-bonds es
    estimada por RDKit, no cristalográfica.  Pero los PDB de PDBbind
    rara vez tienen H optimizados, así que la diferencia práctica es mínima.

    Args:
        protein_atomgroup: MDAnalysis AtomGroup (pre-seleccionado)

    Returns:
        prolif.Molecule o None si todos los intentos fallan.
    """
    import prolif

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")

        # Intento 1: con H (mayor precisión para H-bonds)
        try:
            return prolif.Molecule.from_mda(protein_atomgroup)
        except Exception:
            pass

        # Intento 2: sin H, force=True (bypasea el check de explicit H)
        try:
            heavy_atoms = protein_atomgroup.select_atoms("not type H h")
            if len(heavy_atoms) == 0:
                return None
            mol = prolif.Molecule.from_mda(heavy_atoms, force=True)
            log.info(
                "protein_loaded_without_H",
                n_heavy=len(heavy_atoms),
                msg="Fallback exitoso: H removidos por valence issues",
            )
            return mol
        except Exception:
            pass

        # Intento 3: sin H, inferrer=None (skip bond order inference)
        try:
            heavy_atoms = protein_atomgroup.select_atoms("not type H h")
            if len(heavy_atoms) == 0:
                return None
            mol = prolif.Molecule.from_mda(
                heavy_atoms, force=True, inferrer=None
            )
            log.info(
                "protein_loaded_no_inferrer",
                n_heavy=len(heavy_atoms),
                msg="Fallback exitoso: H removidos + sin inferencia de bond orders",
            )
            return mol
        except Exception as e:
            log.warning(
                "protein_prolif_all_attempts_failed",
                error=str(e),
                n_atoms=len(protein_atomgroup),
            )
            return None


def _map_prolif_dataframe(df) -> dict[str, float]:
    """
    Convertir DataFrame de ProLIF a nuestro dict de features.

    ProLIF produce un DataFrame con multi-index de columnas:
      (ligand_residue, protein_residue, interaction_type)

    Cada celda es True/False. Acumulamos conteos por tipo de interacción.
    """
    features = {
        "hbond_donor_count": 0.0,
        "hbond_acceptor_count": 0.0,
        "hydrophobic_contacts": 0.0,
        "salt_bridges": 0.0,
        "pi_stacking": 0.0,
        "pi_cation": 0.0,
        "metal_coordination": 0.0,
        "close_contacts_4A": 0.0,
        "close_contacts_6A": 0.0,
    }

    if df is None or df.empty:
        return features

    for col in df.columns:
        if not df[col].iloc[0]:
            continue
        # Extraer tipo de interacción (último nivel del multi-index)
        interaction_type = col[-1] if isinstance(col, tuple) else str(col)
        our_feature = _PROLIF_TYPE_TO_FEATURE.get(interaction_type)
        if our_feature is not None:
            features[our_feature] += 1.0

    return features


def _compute_close_contacts_mda(
    protein_atomgroup,
    ligand_rdmol,
) -> tuple[float, float]:
    """
    Contar átomos de proteína cercanos al ligando.

    Usa MDAnalysis distance_array (todas las distancias par-a-par).

    close_contacts_4A: indica contactos van der Waals directos.
    close_contacts_6A: captura primera esfera del binding site.

    Args:
        protein_atomgroup: MDAnalysis AtomGroup (pre-seleccionado)
        ligand_rdmol: RDKit Mol del ligando (con coordenadas 3D)

    Returns:
        (n_atoms_within_4A, n_atoms_within_6A)
    """
    import MDAnalysis as mda
    from MDAnalysis.analysis.distances import distance_array

    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            lig_u = mda.Universe(ligand_rdmol)

        prot_pos = protein_atomgroup.positions
        lig_pos = lig_u.atoms.positions

        if len(prot_pos) == 0 or len(lig_pos) == 0:
            return (0.0, 0.0)

        dists = distance_array(prot_pos, lig_pos)

        n_4a = float((dists < 4.0).any(axis=1).sum())
        n_6a = float((dists < 6.0).any(axis=1).sum())
        return (n_4a, n_6a)

    except Exception as e:
        log.warning("close_contacts_computation_failed", error=str(e))
        return (0.0, 0.0)


def _compute_close_contacts_from_universes(
    protein_universe,
    ligand_universe,
) -> tuple[float, float]:
    """
    Calcular contactos cercanos cuando ambas entradas son MDAnalysis Universes.

    Usado para poses PDBQT donde el ligando ya es un Universe.
    """
    from MDAnalysis.analysis.distances import distance_array

    prot_pos = protein_universe.atoms.positions
    lig_pos = ligand_universe.atoms.positions

    if len(prot_pos) == 0 or len(lig_pos) == 0:
        return (0.0, 0.0)

    dists = distance_array(prot_pos, lig_pos)

    n_4a = float((dists < 4.0).any(axis=1).sum())
    n_6a = float((dists < 6.0).any(axis=1).sum())
    return (n_4a, n_6a)
