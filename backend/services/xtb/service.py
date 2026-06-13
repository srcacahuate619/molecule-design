"""
services/xtb/service.py

Capa de servicio para GFN2-xTB.
Procesa conformadores 3D para generar cargas parciales cuánticas (CM5/Mulliken)
que alimentarán a AutoDock 4 para moléculas organometálicas.
"""

from __future__ import annotations

import asyncio
import os
import shutil
import tempfile
from pathlib import Path
from dataclasses import dataclass

from utils.logger import get_logger

log = get_logger(__name__)

@dataclass
class XTBResult:
    success: bool
    charges: list[float] | None = None
    error: str | None = None
    execution_time_s: float | None = None

class XTBService:
    def __init__(self):
        self._xtb_cmd = shutil.which("xtb") or "/opt/conda/bin/xtb"

    @property
    def is_configured(self) -> bool:
        return self._xtb_cmd is not None

    async def generate_partial_charges(self, sdf_content: str, smiles_hash: str) -> XTBResult:
        """
        Calcula cargas GFN2-xTB para el SDF provisto.
        """
        if not self.is_configured:
            return XTBResult(success=False, error="Binario 'xtb' no encontrado en el sistema.")

        import time
        start_time = time.monotonic()

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            input_sdf = tmp_path / f"{smiles_hash}.sdf"
            input_sdf.write_text(sdf_content, encoding="utf-8")

            # Ejecutamos xtb con SP (Single Point) para extraer cargas.
            command = [
                self._xtb_cmd,
                str(input_sdf.name),
                "--sp",     # Single point energy & properties
                "--gfn", "2"
            ]

            process = await asyncio.create_subprocess_exec(
                *command,
                cwd=str(tmp_path),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await process.communicate()

            if process.returncode != 0:
                log.warning("Fallo en xtb", error=stderr.decode() or stdout.decode())
                return XTBResult(success=False, error="xtb falló al procesar la molécula")

            # XTB genera un archivo llamado 'charges' en el directorio de trabajo
            charges_file = tmp_path / "charges"
            if not charges_file.exists():
                return XTBResult(success=False, error="xtb no generó el archivo de cargas")

            # Leer cargas
            charges_text = charges_file.read_text(encoding="utf-8")
            charges = [float(line.strip()) for line in charges_text.splitlines() if line.strip()]

            return XTBResult(
                success=True,
                charges=charges,
                execution_time_s=round(time.monotonic() - start_time, 2)
            )

_xtb_service: XTBService | None = None

def get_xtb_service() -> XTBService:
    global _xtb_service
    if _xtb_service is None:
        _xtb_service = XTBService()
    return _xtb_service
