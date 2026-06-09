"""
services/diffpepdock/service.py

Capa de servicio para DiffPepDock con degradación elegante.
DiffPepDock es un modelo generativo por difusión entrenado específicamente para docking proteína-péptido.
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from core.config import get_settings
from utils.logger import get_logger

log = get_logger(__name__)


@dataclass
class DiffPepDockPose:
    """Una pose predicha por DiffPepDock."""
    rank: int
    confidence: float  # Score de confianza del modelo (mayor = mejor)
    ligand_pdb: str   # Coordenadas del péptido en formato PDB
    rmsd: float | None = None


@dataclass
class DiffPepDockResult:
    """Resultado completo de una predicción de DiffPepDock."""
    success: bool
    poses: list[DiffPepDockPose] = field(default_factory=list)
    best_confidence: float | None = None
    method: str = "DiffPepDock"
    execution_time_s: float | None = None
    warnings: list[str] = field(default_factory=list)
    error: str | None = None

    @property
    def scientific_context(self) -> str:
        """Contexto científico del modelo."""
        return (
            "DiffPepDock es un modelo generativo por difusión equivalente en SE(3) optimizado "
            "para predecir el acoplamiento de péptidos flexibles en el sitio activo de la proteína."
        )


class DiffPepDockService:
    """Servicio de DiffPepDock con degradación elegante hacia Vina."""

    def __init__(self):
        self._api_url: str | None = None
        self._available: bool | None = None
        self._load_config()

    def _load_config(self):
        """Carga la URL desde la configuración global."""
        try:
            settings = get_settings()
            self._api_url = settings.diffpepdock_api_url
        except Exception:
            self._api_url = None

    @property
    def is_configured(self) -> bool:
        return self._api_url is not None and len(self._api_url) > 0

    async def check_health(self) -> dict[str, Any]:
        """Comprueba si el servicio está disponible en su endpoint /health."""
        if not self.is_configured:
            return {
                "status": "not_configured",
                "message": "DiffPepDock no está configurado en las variables de entorno."
            }
        try:
            loop = asyncio.get_running_loop()
            result = await loop.run_in_executor(None, self._ping_api)
            self._available = result
            return {
                "status": "healthy" if result else "unhealthy",
                "api_url": self._api_url
            }
        except Exception as e:
            self._available = False
            return {
                "status": "unhealthy",
                "error": str(e)
            }

    def _ping_api(self) -> bool:
        if not self._api_url:
            return False
        try:
            req = Request(f"{self._api_url}/health", method="GET")
            with urlopen(req, timeout=5) as resp:
                return resp.status == 200
        except Exception:
            return False

    async def predict(
        self,
        protein_pdb_path: str,
        peptide_smiles: str,
        num_poses: int = 5,
        grid_center: tuple[float, float, float] | None = None,
        grid_size: tuple[float, float, float] | None = None,
    ) -> DiffPepDockResult:
        """Envia el PDB del receptor y el SMILES del péptido al servicio de DiffPepDock."""
        if not self.is_configured:
            return DiffPepDockResult(
                success=False,
                error="DiffPepDock no está configurado",
                warnings=["Servicio DiffPepDock no configurado. Se usó AutoDock Vina."]
            )

        if self._available is False:
            return DiffPepDockResult(
                success=False,
                error="DiffPepDock no está disponible",
                warnings=["Servicio de DiffPepDock fuera de línea. Se usó AutoDock Vina."]
            )

        try:
            import time
            start = time.monotonic()

            loop = asyncio.get_running_loop()
            result = await loop.run_in_executor(
                None,
                self._call_api,
                protein_pdb_path,
                peptide_smiles,
                num_poses,
                grid_center,
                grid_size,
            )

            elapsed = time.monotonic() - start

            if result is None:
                return DiffPepDockResult(
                    success=False,
                    error="La API de DiffPepDock no retornó respuesta",
                    warnings=["Fallo en la predicción del acoplamiento peptídico."]
                )

            poses = []
            for i, p in enumerate(result.get("poses", [])):
                poses.append(DiffPepDockPose(
                    rank=i + 1,
                    confidence=p.get("confidence", 0.0),
                    ligand_pdb=p.get("peptide_pdb", ""),
                    rmsd=p.get("rmsd"),
                ))

            best_conf = max((p.confidence for p in poses), default=None)

            return DiffPepDockResult(
                success=True,
                poses=poses,
                best_confidence=best_conf,
                execution_time_s=round(elapsed, 2),
            )

        except Exception as e:
            log.warning("DiffPepDock falló", error=str(e))
            return DiffPepDockResult(
                success=False,
                error=str(e),
                warnings=[f"Error en DiffPepDock ({type(e).__name__}). Se usó AutoDock Vina."]
            )

    def _call_api(
        self,
        protein_pdb_path: str,
        peptide_smiles: str,
        num_poses: int,
        grid_center: tuple[float, float, float] | None = None,
        grid_size: tuple[float, float, float] | None = None,
    ) -> dict | None:
        if not self._api_url:
            return None

        protein_content = Path(protein_pdb_path).read_text()
        payload_dict: dict[str, Any] = {
            "protein_pdb": protein_content,
            "peptide_smiles": peptide_smiles,
            "num_poses": num_poses,
        }
        if grid_center is not None:
            payload_dict["grid_center"] = grid_center
        if grid_size is not None:
            payload_dict["grid_size"] = grid_size

        payload = json.dumps(payload_dict).encode("utf-8")

        req = Request(
            f"{self._api_url}/predict",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urlopen(req, timeout=120) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            log.warning("Fallo en la comunicación con DiffPepDock API", error=str(e))
            return None


_diffpepdock_service: DiffPepDockService | None = None


def get_diffpepdock_service() -> DiffPepDockService:
    global _diffpepdock_service
    if _diffpepdock_service is None:
        _diffpepdock_service = DiffPepDockService()
    return _diffpepdock_service
