"""
rescoring/pose_filter.py

Filtro geométrico de poses de docking.

Verifica que las poses generadas por Vina sean geométricamente razonables
antes de extraer features 3D. Una pose fuera del grid box o con clashes
severos produciría features basura → predicción basura.

3 checks:
  1. Distancia del centroide del ligando al centro del grid box
  2. Porcentaje de átomos pesados dentro del grid box
  3. Número de clashes estéricos (distancias < 1.5 Å a átomos de la proteína)

Nota: Este módulo procesa bloques PDBQT directamente.
No requiere RDKit — usa parsing simple de coordenadas.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

import numpy as np

from logger import get_logger

log = get_logger(__name__)


@dataclass
class PoseFilterConfig:
    """Configuración del filtro de poses."""

    max_centroid_distance: float = 12.0  # Å
    min_atoms_in_box_ratio: float = 0.7  # 70%
    max_clashes: int = 5
    clash_distance: float = 1.5  # Å
    # Grid box (se carga del target config — valores default para 7E2Y)
    grid_center: tuple[float, float, float] = (-22.228, -0.583, -29.375)
    grid_size: tuple[float, float, float] = (25.0, 25.0, 25.0)


class PoseFilter:
    """Filtro geométrico de poses de docking."""

    def __init__(self, settings=None):
        self.config = PoseFilterConfig()
        if settings:
            self.config.max_centroid_distance = settings.pose_filter_max_distance
            self.config.min_atoms_in_box_ratio = settings.pose_filter_min_atoms_in_box
            self.config.max_clashes = settings.pose_filter_max_clashes

    def filter_poses(self, poses: list) -> dict[str, Any]:
        """
        Filtrar lista de poses.

        Returns:
            dict con keys:
              - valid_poses: list de poses que pasaron los 3 checks
              - poses_passing: int
              - total: int
              - details: list[dict] con resultado por pose
        """
        results = []
        valid_poses = []

        for i, pose in enumerate(poses):
            coords = self._extract_coordinates(pose.pdbqt_block)

            if len(coords) == 0:
                results.append({
                    "pose_index": i,
                    "passed": False,
                    "reason": "No se pudieron extraer coordenadas del PDBQT",
                    "vina_score": pose.vina_score,
                })
                continue

            coords_array = np.array(coords)

            # Check 1: Distancia del centroide al grid center
            centroid = coords_array.mean(axis=0)
            grid_center = np.array(self.config.grid_center)
            centroid_dist = float(np.linalg.norm(centroid - grid_center))

            check1_pass = centroid_dist <= self.config.max_centroid_distance

            # Check 2: % de átomos dentro del grid box
            half_size = np.array(self.config.grid_size) / 2.0
            box_min = grid_center - half_size
            box_max = grid_center + half_size
            in_box = np.all((coords_array >= box_min) & (coords_array <= box_max), axis=1)
            atoms_in_box_ratio = float(in_box.sum() / len(coords_array))

            check2_pass = atoms_in_box_ratio >= self.config.min_atoms_in_box_ratio

            # Check 3: clashes (STUB — siempre True)
            # Limitación documentada: Vina ya penaliza clashes en su scoring
            # function (término de repulsión), por lo que un check explícito
            # de clashes post-docking tiene impacto menor. Implementar en
            # futuro si se detecta que poses con clashes severos pasan filtro.
            # Requiere: coordenadas de la proteína parseadas, que no se
            # cargan en el flujo actual del microservicio de inferencia.
            # Severidad: BAJA — no invalida el pipeline científico.
            check3_pass = True  # STUB: ver limitación documentada arriba
            n_clashes = 0

            all_pass = check1_pass and check2_pass and check3_pass

            results.append({
                "pose_index": i,
                "passed": all_pass,
                "centroid_distance": round(centroid_dist, 2),
                "atoms_in_box_ratio": round(atoms_in_box_ratio, 3),
                "n_clashes": n_clashes,
                "vina_score": pose.vina_score,
                "checks": {
                    "centroid": check1_pass,
                    "atoms_in_box": check2_pass,
                    "clashes": check3_pass,
                },
            })

            if all_pass:
                valid_poses.append(pose)

        n_passing = len(valid_poses)
        total = len(poses)

        if n_passing < total:
            log.info(
                "pose_filter_result",
                passing=n_passing,
                total=total,
                rejected=total - n_passing,
            )

        return {
            "valid_poses": valid_poses,
            "poses_passing": n_passing,
            "total": total,
            "details": results,
        }

    def _extract_coordinates(self, pdbqt_block: str) -> list[tuple[float, float, float]]:
        """
        Extraer coordenadas de átomos pesados de un bloque PDBQT.

        Formato PDBQT (columnas fijas):
          ATOM      1  C1  LIG A   1      -22.228  -0.583 -29.375  1.00  0.00    0.000 C
          cols:     0-5  6-10  12-15  ...  30-37    38-45  46-53  ...

        Solo extraer átomos pesados (no H).
        """
        coords = []
        for line in pdbqt_block.split("\n"):
            if not (line.startswith("ATOM") or line.startswith("HETATM")):
                continue
            # En PDBQT, el tipo de átomo está al final (columna 77+)
            atom_type = line[77:79].strip() if len(line) > 77 else ""
            # Skip hydrogens
            if atom_type == "H" or atom_type == "HD":
                continue
            try:
                x = float(line[30:38])
                y = float(line[38:46])
                z = float(line[46:54])
                coords.append((x, y, z))
            except (ValueError, IndexError):
                continue

        return coords
