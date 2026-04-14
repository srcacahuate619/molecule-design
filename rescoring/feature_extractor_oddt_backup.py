"""
rescoring/feature_extractor.py

Extracción de features 3D para ML rescoring.

Features extraídas (3 grupos):
  A. Descriptores 1D/2D (pre-calculados por backend): MW, LogP, TPSA, HBD, HBA, RotBonds, QED
  B. Features de Vina: best_score, score_variance, score_range, poses_passing_ratio
  C. Features 3D de interacción (ODDT): contact fingerprints proteína-ligando

Grupo A viene del request (backend los calcula con RDKit en Python 3.14).
Grupo B se calcula en pose_filter + model_manager.
Grupo C se extrae aquí usando ODDT (Python 3.12).

Diseño:
  - Si ODDT está disponible → extraer features 3D completas
  - Si ODDT falla → degradación elegante con features 3D = 0 + warning

Nota: En Fase 1 (sin modelo entrenado), este módulo define la ESTRUCTURA
de las features. Los valores concretos se validarán en Fase 2 cuando
tengamos el dataset de PDBbind.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from logger import get_logger

log = get_logger(__name__)

# Features 3D que se extraerán con ODDT
# Estas son interacciones proteína-ligando basadas en la geometría de la pose
INTERACTION_FEATURES = [
    "hbond_donor_count",        # H-bonds donde el ligando es donor
    "hbond_acceptor_count",     # H-bonds donde el ligando es acceptor
    "hydrophobic_contacts",     # Contactos hidrofóbicos
    "salt_bridges",             # Puentes salinos
    "pi_stacking",              # Pi stacking (face-to-face + edge-to-face)
    "pi_cation",                # Interacciones pi-catión
    "metal_coordination",       # Coordinación con metales (si aplica)
    "close_contacts_4A",        # Átomos de proteína a < 4 Å del ligando
    "close_contacts_6A",        # Átomos de proteína a < 6 Å del ligando
]

# Features de energía de Vina descompuestas (si están disponibles en PDBQT)
VINA_ENERGY_FEATURES = [
    "vina_gauss1",
    "vina_gauss2",
    "vina_repulsion",
    "vina_hydrophobic",
    "vina_hydrogen",
]


class FeatureExtractor:
    """Extractor de features 3D para ML rescoring."""

    def __init__(self):
        self._oddt_available = self._check_oddt()
        if not self._oddt_available:
            log.warning(
                "oddt_not_available",
                msg="ODDT no disponible. Features 3D serán cero. Esto es aceptable en Fase 1.",
            )

    def extract_3d_features(
        self,
        pose,
        smiles: str,
        target_pdb_path: str,
    ) -> dict[str, float]:
        """
        Extraer features 3D de una pose.

        Args:
            pose: PoseData con pdbqt_block y vina_score
            smiles: SMILES canónico
            target_pdb_path: path al PDB de la proteína

        Returns:
            dict[str, float] con features 3D
        """
        features: dict[str, float] = {}

        # Feature del score de Vina de la pose
        features["vina_best_score"] = pose.vina_score

        if self._oddt_available:
            try:
                interaction_features = self._extract_oddt_features(
                    pose.pdbqt_block,
                    target_pdb_path
                )
                features.update(interaction_features)
            except Exception as e:
                log.error("oddt_extraction_error", error=str(e), smiles=smiles[:50])
                # Degradación elegante: features 3D = 0
                features.update(self._zero_features())
        else:
            features.update(self._zero_features())

        return features

    def extract_3d_features_from_files(
        self,
        protein_path: str,
        ligand_path: str,
    ) -> dict[str, float]:
        """
        Extraer features 3D desde archivos PDB/SDF (para training con PDBbind).

        A diferencia de extract_3d_features() que recibe un PoseData con PDBQT
        de docking, este método lee directamente los archivos estructurales de
        PDBbind (proteína PDB + ligando SDF/MOL2).

        Args:
            protein_path: path al archivo PDB de la proteína
            ligand_path: path al archivo SDF/MOL2 del ligando co-cristalizado

        Returns:
            dict[str, float] con features 3D (INTERACTION_FEATURES), o None si falla

        Limitación documentada: la extracción depende de que ODDT pueda parsear
        ambos archivos correctamente. Formatos corruptos o no estándar producirán
        features en cero (degradación elegante, no crash silencioso).
        """
        if not self._oddt_available:
            return self._zero_features()

        try:
            return self._extract_oddt_features_from_files(protein_path, ligand_path)
        except Exception as e:
            log.warning(
                "oddt_file_extraction_error",
                error=str(e),
                protein=protein_path,
                ligand=ligand_path,
            )
            return self._zero_features()

    def _extract_oddt_features_from_files(
        self,
        protein_path: str,
        ligand_path: str,
    ) -> dict[str, float]:
        """
        Extraer interaction fingerprints desde archivos PDB/SDF con ODDT.

        Lee la proteína desde PDB y el ligando desde SDF/MOL2,
        computa interacciones 3D idénticas a las del pipeline de inferencia.
        """
        import oddt
        from oddt import interactions

        features: dict[str, float] = {}

        # Parsear proteína
        protein = next(oddt.toolkit.readfile("pdb", protein_path))
        protein.protein = True

        # Parsear ligando (SDF o MOL2)
        ligand_ext = str(ligand_path).rsplit(".", 1)[-1].lower()
        fmt = "sdf" if ligand_ext in ("sdf", "mol") else ligand_ext
        ligand = next(oddt.toolkit.readfile(fmt, str(ligand_path)))

        # Extraer interacciones (misma lógica que _extract_oddt_features)
        hbond_d = interactions.hbond_acceptor_donor(protein, ligand)
        features["hbond_donor_count"] = float(len(hbond_d[0])) if hbond_d[0] is not None else 0.0

        hbond_a = interactions.hbond_acceptor_donor(ligand, protein)
        features["hbond_acceptor_count"] = float(len(hbond_a[0])) if hbond_a[0] is not None else 0.0

        hydro = interactions.hydrophobic_contacts(protein, ligand)
        features["hydrophobic_contacts"] = float(len(hydro[0])) if hydro[0] is not None else 0.0

        salt = interactions.salt_bridges(protein, ligand)
        features["salt_bridges"] = float(len(salt[0])) if salt[0] is not None else 0.0

        pi_stack = interactions.pi_stacking(protein, ligand)
        features["pi_stacking"] = float(len(pi_stack[0])) if pi_stack[0] is not None else 0.0

        pi_cat = interactions.pi_cation(protein, ligand)
        features["pi_cation"] = float(len(pi_cat[0])) if pi_cat[0] is not None else 0.0

        features["metal_coordination"] = 0.0

        features["close_contacts_4A"] = float(
            self._count_close_contacts(protein, ligand, cutoff=4.0)
        )
        features["close_contacts_6A"] = float(
            self._count_close_contacts(protein, ligand, cutoff=6.0)
        )

        return features

    def _extract_oddt_features(
        self,
        pdbqt_block: str,
        target_pdb_path: str,
    ) -> dict[str, float]:
        """
        Extraer interaction fingerprints usando ODDT.

        ODDT calcula interacciones proteína-ligando basadas en
        distancias y ángulos entre átomos.

        Nota: Esta implementación se completará en Fase 2 cuando tengamos
        el pipeline de datos completo. Por ahora define la interfaz.
        """
        import oddt
        from oddt import interactions

        features: dict[str, float] = {}

        try:
            # Parsear proteína
            protein = next(oddt.toolkit.readstring("pdb", open(target_pdb_path).read()))
            protein.protein = True

            # Parsear ligando desde PDBQT
            ligand = next(oddt.toolkit.readstring("pdbqt", pdbqt_block))

            # Extraer interacciones
            # H-bonds (ligando como donor)
            hbond_d = interactions.hbond_acceptor_donor(protein, ligand)
            features["hbond_donor_count"] = float(len(hbond_d[0])) if hbond_d[0] is not None else 0.0

            # H-bonds (ligando como acceptor)
            hbond_a = interactions.hbond_acceptor_donor(ligand, protein)
            features["hbond_acceptor_count"] = float(len(hbond_a[0])) if hbond_a[0] is not None else 0.0

            # Contactos hidrofóbicos
            hydro = interactions.hydrophobic_contacts(protein, ligand)
            features["hydrophobic_contacts"] = float(len(hydro[0])) if hydro[0] is not None else 0.0

            # Puentes salinos
            salt = interactions.salt_bridges(protein, ligand)
            features["salt_bridges"] = float(len(salt[0])) if salt[0] is not None else 0.0

            # Pi stacking
            pi_stack = interactions.pi_stacking(protein, ligand)
            features["pi_stacking"] = float(len(pi_stack[0])) if pi_stack[0] is not None else 0.0

            # Pi-catión
            pi_cat = interactions.pi_cation(protein, ligand)
            features["pi_cation"] = float(len(pi_cat[0])) if pi_cat[0] is not None else 0.0

            # Metal coordination (placeholder — depende del target)
            features["metal_coordination"] = 0.0

            # Contactos cercanos por distancia
            features["close_contacts_4A"] = float(
                self._count_close_contacts(protein, ligand, cutoff=4.0)
            )
            features["close_contacts_6A"] = float(
                self._count_close_contacts(protein, ligand, cutoff=6.0)
            )

        except Exception as e:
            log.warning("oddt_partial_failure", error=str(e))
            features = self._zero_features()

        return features

    def _count_close_contacts(self, protein, ligand, cutoff: float) -> int:
        """Contar átomos de proteína a distancia < cutoff del ligando."""
        try:
            import oddt
            from oddt.spatial import distance

            dists = distance(protein.atoms.coords, ligand.atoms.coords)
            return int((dists < cutoff).any(axis=1).sum())
        except Exception:
            return 0

    def _zero_features(self) -> dict[str, float]:
        """Features 3D en cero (degradación elegante)."""
        features = {}
        for feat in INTERACTION_FEATURES:
            features[feat] = 0.0
        return features

    def _check_oddt(self) -> bool:
        """Verificar disponibilidad de ODDT."""
        try:
            import oddt  # noqa: F401
            return True
        except ImportError:
            return False

    def get_feature_names(self) -> list[str]:
        """Lista completa de features extraídas (para documentación y orden)."""
        return (
            # 1D/2D (vienen del request)
            ["mw", "logp", "tpsa", "hbd", "hba", "rotatable_bonds", "qed"]
            # Vina
            + ["vina_best_score"]
            # 3D interactions
            + list(INTERACTION_FEATURES)
            # Pose variance
            + ["pose_score_variance", "pose_score_range", "poses_passing_ratio"]
        )
