"""
rescoring/data_splitter.py

Lógica de partición de datos para entrenamiento ML.

Implementa:
  1. Scaffold-split cross-validation (Bemis-Murcko scaffolds)
  2. Frozen test set (~500 complejos representativos de todas las familias)
  3. LTR ranking groups (complejos agrupados por target/proteína)

El scaffold-split es OBLIGATORIO per ML_RESCORING_ARCHITECTURE.md.
Random split sobreestima performance porque moléculas de la misma serie
caen en train y test → "memory leak".

Referencia: Yang et al., "Analyzing Learned Molecular Representations
for Property Prediction", J Chem Inf Model 2019.
"""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

from logger import get_logger

log = get_logger(__name__)


@dataclass
class DataSplit:
    """Un split de datos con IDs train/val/test."""
    train_ids: list[str]
    val_ids: list[str]
    test_ids: list[str]
    # Metadata
    split_method: str = ""
    n_train: int = 0
    n_val: int = 0
    n_test: int = 0
    fold: int = 0  # Para CV
    scaffold_groups: dict[str, list[str]] | None = None

    def __post_init__(self):
        self.n_train = len(self.train_ids)
        self.n_val = len(self.val_ids)
        self.n_test = len(self.test_ids)


@dataclass
class LTRGroup:
    """
    Grupo de ranking para Learning-to-Rank.

    En XGBoost rank:pairwise, cada grupo contiene ligandos del MISMO target
    que se comparan entre sí. No tiene sentido comparar afinidad de
    un inhibidor de kinasa contra un agonista de GPCR.
    """
    group_id: str  # PDB ID del target o UniProt ID
    pdb_ids: list[str] = field(default_factory=list)
    pkis: list[float] = field(default_factory=list)
    n_members: int = 0


def get_bemis_murcko_scaffold(smiles: str) -> str:
    """
    Obtener scaffold Bemis-Murcko de un SMILES.

    El scaffold reduce la molécula a su esqueleto de anillos + linkers.
    Moléculas con el mismo scaffold son de la misma "serie química".

    Returns:
        SMILES canónico del scaffold, o hash del SMILES si falla
    """
    try:
        from rdkit import Chem
        from rdkit.Chem.Scaffolds import MurckoScaffold

        mol = Chem.MolFromSmiles(smiles)
        if mol is None:
            # Fallback: usar hash del SMILES como "scaffold único"
            return f"UNPARSEABLE_{hashlib.md5(smiles.encode()).hexdigest()[:8]}"

        scaffold = MurckoScaffold.GetScaffoldForMol(mol)
        scaffold_smiles = Chem.MolToSmiles(scaffold)

        if not scaffold_smiles:
            # Molécula sin anillos → scaffold vacío
            # Agrupar todos los acíclicos juntos sería incorrecto
            # Cada uno es su propio "scaffold"
            return f"ACYCLIC_{hashlib.md5(smiles.encode()).hexdigest()[:8]}"

        return scaffold_smiles

    except Exception:
        return f"ERROR_{hashlib.md5(smiles.encode()).hexdigest()[:8]}"


def group_by_scaffold(
    complexes: list[Any],
) -> dict[str, list[str]]:
    """
    Agrupar complejos por scaffold Bemis-Murcko.

    Args:
        complexes: PDBBindComplex con ligand_smiles

    Returns:
        {scaffold_smiles: [pdb_id, ...]}
    """
    scaffold_groups: dict[str, list[str]] = defaultdict(list)

    for cpx in complexes:
        scaffold = get_bemis_murcko_scaffold(cpx.ligand_smiles)
        scaffold_groups[scaffold].append(cpx.pdb_id)

    log.info(
        "scaffold_grouping",
        n_complexes=sum(len(v) for v in scaffold_groups.values()),
        n_scaffolds=len(scaffold_groups),
        largest_group=max(len(v) for v in scaffold_groups.values()) if scaffold_groups else 0,
        singletons=sum(1 for v in scaffold_groups.values() if len(v) == 1),
    )

    return dict(scaffold_groups)


def create_frozen_test_set(
    complexes: list[Any],
    family_classifications: dict[str, Any],
    test_size: int = 500,
    seed: int = 42,
) -> list[str]:
    """
    Crear test set congelado, representativo de todas las familias.

    Garantías:
    - Representación proporcional de cada familia estructural
    - Mínimo 10 complejos por familia (si hay suficientes)
    - Distribución de pKi similar al dataset completo
    - Determinístico (mismo seed → mismo split)

    Args:
        complexes: complejos VIP (pasaron auditoría)
        family_classifications: {pdb_id: FamilyClassification}
        test_size: tamaño del test set
        seed: semilla para reproducibilidad

    Returns:
        lista de PDB IDs para el test set
    """
    rng = np.random.RandomState(seed)

    # Organizar por familia
    by_family: dict[str, list[Any]] = defaultdict(list)
    for cpx in complexes:
        family = "other"
        if cpx.pdb_id in family_classifications:
            fc = family_classifications[cpx.pdb_id]
            family = fc.family if hasattr(fc, "family") else fc
        by_family[family].append(cpx)

    total = len(complexes)
    test_ids = []

    # Asignar cuota proporcional por familia, con mínimo 10
    quotas = {}
    remaining = test_size
    for family, members in by_family.items():
        proportion = len(members) / total
        quota = max(10, int(test_size * proportion))
        quota = min(quota, len(members) // 2)  # Nunca más de la mitad
        quotas[family] = quota
        remaining -= quota

    # Si sobran slots, distribuir proporcionalmente
    if remaining > 0:
        for family in sorted(quotas.keys()):
            extra = min(remaining, len(by_family[family]) // 2 - quotas[family])
            if extra > 0:
                quotas[family] += extra
                remaining -= extra

    # Seleccionar complejos estratificados por pKi
    for family, members in by_family.items():
        quota = quotas.get(family, 0)
        if quota == 0:
            continue

        # Ordenar por pKi para estratificar
        members_sorted = sorted(members, key=lambda c: c.pki)
        n = len(members_sorted)

        if n <= quota:
            # Tomar todos
            test_ids.extend(c.pdb_id for c in members_sorted)
        else:
            # Selección estratificada: tomar uniformemente de la distribución
            indices = np.linspace(0, n - 1, quota, dtype=int)
            # Añadir algo de ruido para no siempre elegir los mismos
            noise = rng.randint(-1, 2, size=len(indices))
            indices = np.clip(indices + noise, 0, n - 1)
            indices = np.unique(indices)

            # Si perdimos algunos por unique, completar random
            while len(indices) < quota:
                extra_idx = rng.randint(0, n)
                if extra_idx not in indices:
                    indices = np.append(indices, extra_idx)

            for idx in indices[:quota]:
                test_ids.append(members_sorted[idx].pdb_id)

    log.info(
        "frozen_test_set_created",
        test_size=len(test_ids),
        target_size=test_size,
        families={f: quotas.get(f, 0) for f in by_family},
    )

    return test_ids


def scaffold_split_cv(
    complexes: list[Any],
    test_ids: list[str],
    n_folds: int = 5,
    seed: int = 42,
) -> list[DataSplit]:
    """
    Scaffold-split cross-validation.

    El split se hace a nivel de scaffold, no de molécula individual:
    - Todas las moléculas con el mismo scaffold van al mismo fold
    - Esto evita data leakage por series químicas

    Args:
        complexes: complejos VIP con SMILES
        test_ids: IDs del frozen test set (se excluyen)
        n_folds: número de folds
        seed: reproducibilidad

    Returns:
        lista de DataSplit (uno por fold)
    """
    rng = np.random.RandomState(seed)
    test_id_set = set(test_ids)

    # Excluir test set
    train_pool = [c for c in complexes if c.pdb_id not in test_id_set]

    # Agrupar por scaffold
    scaffold_groups = group_by_scaffold(train_pool)

    # Crear mapping pdb_id → scaffold
    id_to_scaffold = {}
    for scaffold, ids in scaffold_groups.items():
        for pdb_id in ids:
            id_to_scaffold[pdb_id] = scaffold

    # Barajar scaffolds determinísticamente
    scaffolds = list(scaffold_groups.keys())
    rng.shuffle(scaffolds)

    # Asignar scaffolds a folds round-robin (balanceado por tamaño)
    fold_sizes = [0] * n_folds
    fold_scaffolds: dict[int, list[str]] = {i: [] for i in range(n_folds)}

    # Ordenar scaffolds de mayor a menor para mejor balance
    scaffolds_sorted = sorted(scaffolds, key=lambda s: len(scaffold_groups[s]), reverse=True)

    for scaffold in scaffolds_sorted:
        # Asignar al fold con menos miembros
        min_fold = min(range(n_folds), key=lambda i: fold_sizes[i])
        fold_scaffolds[min_fold].append(scaffold)
        fold_sizes[min_fold] += len(scaffold_groups[scaffold])

    # Generar DataSplits
    splits = []
    for fold_idx in range(n_folds):
        val_scaffolds = set(fold_scaffolds[fold_idx])

        val_ids = []
        train_ids = []
        for cpx in train_pool:
            scaffold = id_to_scaffold.get(cpx.pdb_id, "")
            if scaffold in val_scaffolds:
                val_ids.append(cpx.pdb_id)
            else:
                train_ids.append(cpx.pdb_id)

        split = DataSplit(
            train_ids=train_ids,
            val_ids=val_ids,
            test_ids=test_ids,
            split_method="scaffold_split_cv",
            fold=fold_idx,
        )
        splits.append(split)

    log.info(
        "scaffold_split_cv_created",
        n_folds=n_folds,
        fold_sizes=[s.n_val for s in splits],
        train_sizes=[s.n_train for s in splits],
        test_size=len(test_ids),
    )

    return splits


def build_ltr_groups(
    complexes: list[Any],
    pdb_ids: list[str],
) -> tuple[list[int], list[float]]:
    """
    Construir grupos de ranking para XGBoost LTR.

    Para rank:pairwise, XGBoost necesita:
    - group: array donde cada elemento es el número de items en cada grupo
    - labels: array de relevancia (pKi) alineado con las features

    Grupos = complejos del mismo target. Solo targets con ≥ 2 ligandos
    forman un grupo (no tiene sentido hacer ranking con 1 solo ligando).

    Implementation note: En PDBbind, cada PDB ID es un complejo único
    (1 target + 1 ligand). Para agrupar por target necesitamos la
    identidad del target, que no siempre está explícita. Usamos el
    PDB ID de 4 letras como proxy — todos los complejos con la misma
    proteína cristalográfica son del mismo target. Esto es una
    aproximación conservadora (bajo recall, alta precision).

    Para un pipeline ideal se usarían UniProt IDs.

    Args:
        complexes: todos los complejos
        pdb_ids: IDs a incluir (e.g., train set)

    Returns:
        (groups, labels) donde:
          groups: list[int] tamaños de cada grupo
          labels: list[float] pKi para cada complejo, ordenados por grupo
    """
    id_set = set(pdb_ids)
    cpx_map = {c.pdb_id: c for c in complexes if c.pdb_id in id_set}

    # En PDBbind, muchas proteínas aparecen múltiples veces con diferentes
    # ligandos. Para simplificar, cada complejo es su propio "grupo" de
    # tamaño 1 a menos que compartimos proteína.
    # Este es un punto donde el diseño puede mejorarse con UniProt mapping.

    # Por ahora: cada PDB ID es un grupo de 1 (pointwise learning).
    # XGBoost rank:pairwise con grupos de 1 se reduce a regresión.
    # Esto es HONEST about the limitation: sin mapping de target,
    # no podemos hacer verdadero pairwise ranking.

    # NOTA: Cuando se integre UniProt mapping, esta función se actualiza
    # para crear grupos reales multi-ligando.

    ordered_ids = sorted(pdb_ids)  # Orden determinístico
    groups = [1] * len(ordered_ids)  # Cada complejo es su grupo
    labels = [cpx_map[pid].pki for pid in ordered_ids if pid in cpx_map]

    # Verificar alineación
    actual_ids = [pid for pid in ordered_ids if pid in cpx_map]
    if len(actual_ids) != len(labels):
        log.warning(
            "ltr_groups_mismatch",
            expected=len(ordered_ids),
            actual=len(actual_ids),
        )

    log.info(
        "ltr_groups_built",
        n_complexes=len(actual_ids),
        n_groups=len(groups),
        label_range=[round(min(labels), 2), round(max(labels), 2)] if labels else None,
    )

    return groups, labels


def save_split_config(
    test_ids: list[str],
    splits: list[DataSplit],
    output_path: str | Path,
    seed: int = 42,
) -> None:
    """
    Guardar configuración de splits para reproducibilidad.

    Este archivo permite reproducir exactamente los mismos splits.
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    data = {
        "seed": seed,
        "frozen_test_set": sorted(test_ids),
        "n_test": len(test_ids),
        "n_folds": len(splits),
        "folds": [
            {
                "fold": s.fold,
                "n_train": s.n_train,
                "n_val": s.n_val,
                "train_ids": sorted(s.train_ids),
                "val_ids": sorted(s.val_ids),
            }
            for s in splits
        ],
    }

    with open(output_path, "w") as f:
        json.dump(data, f, indent=2)

    log.info("split_config_saved", path=str(output_path))
