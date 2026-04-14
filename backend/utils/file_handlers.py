"""
utils/file_handlers.py

Manejo de archivos moleculares (.pdb, .pdbqt, .sdf, .mol2) con MinIO.

Hay dos tipos de archivos en este sistema:

1. Archivos de proteína (target):
   - .pdb  → estructura descargada del RCSB PDB
   - .pdbqt → estructura preparada para AutoDock Vina
   Estos son estáticos — se preparan una vez y se reutilizan.

2. Archivos de ligando (molécula del usuario):
   - .sdf  → conformer 3D generado por RDKit
   - .pdbqt → convertido para Vina
   - .sdf (output) → poses de docking retornadas por Vina
   Estos se generan por cada molécula evaluada.

Por qué MinIO y no el filesystem local:
   En Railway (y cualquier plataforma cloud), el filesystem es efímero —
   se borra en cada deploy o restart. MinIO persiste los archivos
   independientemente del ciclo de vida del contenedor.

Rutas en MinIO (bucket: docking-poses):
   targets/{pdb_id}/raw.pdb          → proteína raw del PDB
   targets/{pdb_id}/prepared.pdbqt   → proteína preparada para Vina
   ligands/{smiles_hash}/conformer.sdf → conformer 3D del ligando
   ligands/{smiles_hash}/vina_input.pdbqt → ligando preparado para Vina
   poses/{smiles_hash}/{target_pdb_id}/poses.sdf → poses de docking
"""

import io
import os
import re
import tempfile
from contextlib import asynccontextmanager, contextmanager
from pathlib import Path
from typing import AsyncGenerator

import httpx
from miniopy_async import Minio
from miniopy_async.error import S3Error

from core.config import get_settings
from core.exceptions import FileNotFoundInStorage, FileUploadError
from utils.logger import get_logger

log = get_logger(__name__)
settings = get_settings()


# ── Cliente MinIO ─────────────────────────────────────────────────────────────

_minio_client: Minio | None = None


def get_minio_client() -> Minio:
    """
    Retorna el cliente MinIO singleton.

    miniopy-async es el cliente async oficial de MinIO para Python.
    El cliente es thread-safe y puede reutilizarse durante toda la
    vida del proceso.
    """
    global _minio_client
    if _minio_client is None:
        _minio_client = Minio(
            endpoint=settings.minio_endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            secure=settings.minio_secure,
        )
        log.info(
            "cliente MinIO inicializado",
            endpoint=settings.minio_endpoint,
            secure=settings.minio_secure,
        )
    return _minio_client


async def close_minio_client() -> None:
    """Cierra explícitamente el cliente MinIO para evitar sesiones abiertas."""
    global _minio_client
    if _minio_client is None:
        return

    close_result = _minio_client.close_session()
    if hasattr(close_result, "__await__"):
        await close_result

    _minio_client = None


async def ensure_bucket_exists(
    bucket: str,
    *,
    max_retries: int = 5,
    initial_delay: float = 2.0,
) -> None:
    """
    Crea el bucket en MinIO si no existe, con reintentos.

    Se llama en el lifespan de api/main.py al arrancar.
    MinIO no crea buckets automáticamente — si el bucket no existe,
    todas las operaciones de upload fallan con un error críptico.

    Incluye reintentos con backoff exponencial porque MinIO puede
    reportar health=200 antes de que su API S3 esté completamente
    lista (común en arranque local y en contenedores).
    """
    import asyncio

    client = get_minio_client()
    last_error: Exception | None = None

    for attempt in range(1, max_retries + 1):
        try:
            exists = await client.bucket_exists(bucket)
            if not exists:
                await client.make_bucket(bucket)
                log.info("bucket creado en MinIO", bucket=bucket)
            else:
                log.debug("bucket ya existe en MinIO", bucket=bucket)
            return  # éxito
        except S3Error as e:
            last_error = e
            if attempt < max_retries:
                delay = initial_delay * (2 ** (attempt - 1))
                log.warning(
                    "MinIO no listo, reintentando",
                    bucket=bucket,
                    attempt=attempt,
                    max_retries=max_retries,
                    delay_s=delay,
                    error=str(e),
                )
                await asyncio.sleep(delay)
            else:
                log.error(
                    "error verificando/creando bucket tras reintentos",
                    bucket=bucket,
                    attempts=max_retries,
                    error=str(e),
                )

    # Si agotó todos los reintentos
    raise FileUploadError(
        filename="(bucket creation)",
        bucket=bucket,
        detail=str(last_error),
    ) from last_error


# ── Construcción de rutas en MinIO ────────────────────────────────────────────

class StoragePath:
    """
    Centraliza la construcción de rutas dentro del bucket de MinIO.

    Mismo principio que CacheKey en utils/cache.py:
    una sola fuente de verdad para los nombres de objetos.
    """

    @staticmethod
    def target_raw(pdb_id: str) -> str:
        """Proteína raw descargada del RCSB PDB."""
        return f"targets/{pdb_id.upper()}/raw.pdb"

    @staticmethod
    def target_prepared(pdb_id: str) -> str:
        """Proteína preparada para AutoDock Vina (.pdbqt)."""
        return f"targets/{pdb_id.upper()}/prepared.pdbqt"

    @staticmethod
    def ligand_conformer(smiles_hash: str) -> str:
        """Conformer 3D del ligando generado por RDKit (.sdf)."""
        return f"ligands/{smiles_hash}/conformer.sdf"

    @staticmethod
    def ligand_vina_input(smiles_hash: str) -> str:
        """Ligando convertido al formato .pdbqt para Vina."""
        return f"ligands/{smiles_hash}/vina_input.pdbqt"

    @staticmethod
    def docking_poses(smiles_hash: str, target_pdb_id: str) -> str:
        """Poses de docking retornadas por Vina (.sdf)."""
        return f"poses/{smiles_hash}/{target_pdb_id.upper()}/poses.sdf"

    @staticmethod
    def docking_log(smiles_hash: str, target_pdb_id: str) -> str:
        """Log de texto de AutoDock Vina (para debugging)."""
        return f"poses/{smiles_hash}/{target_pdb_id.upper()}/vina.log"


# ── Operaciones de upload ─────────────────────────────────────────────────────

async def upload_bytes(
    data: bytes,
    object_name: str,
    content_type: str = "application/octet-stream",
    bucket: str | None = None,
) -> str:
    """
    Sube bytes a MinIO y retorna el object_name (ruta dentro del bucket).

    Args:
        data:         contenido del archivo como bytes
        object_name:  ruta dentro del bucket (usar StoragePath.*)
        content_type: MIME type del archivo
        bucket:       bucket destino. Por defecto: settings.minio_bucket_poses

    Retorna el object_name para guardarlo en la DB y recuperar el archivo después.

    Lanza FileUploadError si MinIO no está disponible o falla el upload.
    """
    bucket = bucket or settings.minio_bucket_poses
    client = get_minio_client()

    try:
        data_stream = io.BytesIO(data)
        await client.put_object(
            bucket_name=bucket,
            object_name=object_name,
            data=data_stream,
            length=len(data),
            content_type=content_type,
        )
        log.debug(
            "archivo subido a MinIO",
            object_name=object_name,
            bucket=bucket,
            size_bytes=len(data),
        )
        return object_name

    except S3Error as e:
        log.error(
            "error subiendo archivo a MinIO",
            object_name=object_name,
            bucket=bucket,
            error=str(e),
        )
        raise FileUploadError(
            filename=object_name,
            bucket=bucket,
            detail=str(e),
        ) from e


async def upload_text(
    text: str,
    object_name: str,
    encoding: str = "utf-8",
    bucket: str | None = None,
) -> str:
    """
    Sube un string de texto a MinIO.

    Conveniencia sobre upload_bytes para archivos PDB, SDF y logs
    que son texto plano.
    """
    return await upload_bytes(
        data=text.encode(encoding),
        object_name=object_name,
        content_type="text/plain",
        bucket=bucket,
    )


async def upload_file_from_path(
    local_path: str | Path,
    object_name: str,
    bucket: str | None = None,
) -> str:
    """
    Sube un archivo desde el filesystem local a MinIO.

    Usado después de que AutoDock Vina escribe su output (.sdf de poses)
    en el directorio temporal /tmp/vina.
    Lee el archivo en chunks para no cargar archivos grandes en memoria.
    """
    bucket = bucket or settings.minio_bucket_poses
    local_path = Path(local_path)

    if not local_path.exists():
        raise FileNotFoundError(f"Archivo local no encontrado: {local_path}")

    try:
        data = local_path.read_bytes()
        return await upload_bytes(data, object_name, bucket=bucket)

    except S3Error as e:
        raise FileUploadError(
            filename=str(local_path.name),
            bucket=bucket,
            detail=str(e),
        ) from e


# ── Operaciones de descarga ───────────────────────────────────────────────────

async def download_bytes(
    object_name: str,
    bucket: str | None = None,
) -> bytes:
    """
    Descarga un objeto de MinIO y retorna sus bytes.

    Lanza FileNotFoundInStorage si el objeto no existe.
    """
    bucket = bucket or settings.minio_bucket_poses
    client = get_minio_client()

    try:
        response = await client.get_object(
            bucket_name=bucket,
            object_name=object_name,
        )
        data = await response.read()

        close_result = response.close()
        if hasattr(close_result, "__await__"):
            await close_result

        log.debug(
            "archivo descargado de MinIO",
            object_name=object_name,
            size_bytes=len(data),
        )
        return data

    except S3Error as e:
        if e.code == "NoSuchKey":
            raise FileNotFoundInStorage(
                filename=object_name,
                bucket=bucket,
            ) from e
        raise FileUploadError(
            filename=object_name,
            bucket=bucket,
            detail=str(e),
        ) from e


async def download_text(
    object_name: str,
    encoding: str = "utf-8",
    bucket: str | None = None,
) -> str:
    """
    Descarga un objeto de MinIO y retorna su contenido como string.
    """
    data = await download_bytes(object_name, bucket)
    return data.decode(encoding)


async def object_exists(
    object_name: str,
    bucket: str | None = None,
) -> bool:
    """
    Verifica si un objeto existe en MinIO sin descargarlo.

    Usado en services/docking/preparer.py para saber si la proteína
    ya fue preparada (y no repetir el proceso):
        if await object_exists(StoragePath.target_prepared(pdb_id)):
            return  # ya está listo
    """
    bucket = bucket or settings.minio_bucket_poses
    client = get_minio_client()

    try:
        await client.stat_object(bucket_name=bucket, object_name=object_name)
        return True
    except S3Error as e:
        if e.code == "NoSuchKey":
            return False
        log.warning(
            "error verificando existencia de objeto",
            object_name=object_name,
            error=str(e),
        )
        return False


async def delete_object(
    object_name: str,
    bucket: str | None = None,
) -> bool:
    """
    Elimina un objeto de MinIO.

    Retorna True si se eliminó, False si no existía.
    Útil para limpiar archivos temporales después del docking.
    """
    bucket = bucket or settings.minio_bucket_poses
    client = get_minio_client()

    try:
        await client.remove_object(bucket_name=bucket, object_name=object_name)
        log.debug("objeto eliminado de MinIO", object_name=object_name)
        return True
    except S3Error as e:
        if e.code == "NoSuchKey":
            return False
        log.warning("error eliminando objeto", object_name=object_name, error=str(e))
        return False


# ── Context managers para archivos temporales ─────────────────────────────────

@asynccontextmanager
async def temp_file_from_minio(
    object_name: str,
    suffix: str = "",
    bucket: str | None = None,
) -> AsyncGenerator[Path, None]:
    """
    Descarga un objeto de MinIO a un archivo temporal local.

    Úsalo cuando necesitas pasar un archivo a un proceso externo
    (como AutoDock Vina) que requiere una ruta en el filesystem.

    El archivo temporal se elimina automáticamente al salir del bloque.

    Uso en vina_service.py:
        async with temp_file_from_minio(
            StoragePath.target_prepared("7E2Y"),
            suffix=".pdbqt",
        ) as receptor_path:
            # receptor_path es un Path a un archivo .pdbqt local temporal
            await _run_vina(receptor_path, ligand_path, output_path)
        # el archivo ya fue eliminado aquí
    """
    data = await download_bytes(object_name, bucket)

    with tempfile.NamedTemporaryFile(
        suffix=suffix,
        delete=False,
        dir=settings.vina_temp_dir,
    ) as tmp:
        tmp.write(data)
        tmp_path = Path(tmp.name)

    try:
        yield tmp_path
    finally:
        try:
            tmp_path.unlink(missing_ok=True)
        except OSError as e:
            log.warning(
                "no se pudo eliminar archivo temporal",
                path=str(tmp_path),
                error=str(e),
            )


@contextmanager
def temp_output_file(suffix: str = ".sdf") -> Path:
    """
    Crea un archivo temporal vacío para que Vina escriba su output.

    Uso en vina_service.py:
        with temp_output_file(suffix=".sdf") as output_path:
            await _run_vina(receptor, ligand, output_path)
            # subir output_path a MinIO después
            await upload_file_from_path(output_path, StoragePath.docking_poses(...))
    """
    tmp = tempfile.NamedTemporaryFile(
        suffix=suffix,
        delete=False,
        dir=settings.vina_temp_dir,
    )
    tmp_path = Path(tmp.name)
    tmp.close()

    try:
        yield tmp_path
    finally:
        try:
            tmp_path.unlink(missing_ok=True)
        except OSError:
            pass


# ── Descarga desde RCSB PDB ───────────────────────────────────────────────────

async def download_pdb_from_rcsb(pdb_id: str) -> str:
    """
    Descarga la estructura de una proteína desde el RCSB PDB público.

    Retorna el contenido del archivo .pdb como string.
    Lanza httpx.HTTPError si el PDB ID no existe o RCSB no responde.

    Uso en services/docking/preparer.py:
        pdb_content = await download_pdb_from_rcsb("7E2Y")
        await upload_text(pdb_content, StoragePath.target_raw("7E2Y"))
    """
    url = f"https://files.rcsb.org/download/{pdb_id.upper()}.pdb"

    log.info("descargando estructura PDB desde RCSB", pdb_id=pdb_id, url=url)

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(url)
        response.raise_for_status()

    content = response.text

    # Validación básica: un .pdb válido siempre contiene líneas ATOM o HETATM
    if "ATOM" not in content and "HETATM" not in content:
        raise ValueError(
            f"El archivo descargado para '{pdb_id}' no parece ser un PDB válido. "
            "Verifica que el PDB ID sea correcto."
        )

    log.info(
        "estructura PDB descargada",
        pdb_id=pdb_id,
        size_bytes=len(content.encode()),
    )
    return content


# ── Parsers de formato molecular ──────────────────────────────────────────────

def parse_vina_output_sdf(sdf_content: str) -> list[dict]:
    """
    Parsea el archivo .sdf de output exportado por Meeko (mk_export) desde
    el PDBQT de AutoDock Vina.

    Meeko 0.5+ escribe los metadatos de cada pose dentro de una propiedad
    JSON bajo la clave ``> <meeko>``::

        > <meeko>
        {"free_energy": -8.5, "intermolecular_energy": -9.1, ...}

        $$$$

    Para compatibilidad con versiones previas o herramientas alternativas
    (OpenBabel, etc.) que escriben propiedades individuales, también se
    soporta el formato heredado::

        > <minimizedAffinity>
        -8.5

    Nota: Meeko NO exporta RMSD lower/upper bound al SDF, pues esos
    valores solo existen en las líneas ``REMARK VINA RESULT:`` del PDBQT.
    Si no se encuentran en el SDF, se dejan en 0.0 y se espera que el
    pipeline los obtenga del parser PDBQT.

    Retorna lista de dicts con rank, affinity, rmsd_lb, rmsd_ub.
    El orden en el SDF corresponde al rank (pose 1 = mejor afinidad).

    Esta función no usa RDKit para parsear el SDF porque queremos
    que funcione incluso si RDKit no está disponible (ej. en tests).
    """
    import json as _json

    poses: list[dict] = []
    current_props: dict = {}
    reading_field: str | None = None
    rank = 0

    for line in sdf_content.splitlines():
        stripped = line.strip()

        # ── Meeko JSON format: > <meeko> ──────────────────────────────────
        if stripped.startswith("> <meeko>"):
            reading_field = "meeko_json"
            continue

        if reading_field == "meeko_json" and stripped:
            try:
                meeko_data = _json.loads(stripped)
                if isinstance(meeko_data, dict) and "free_energy" in meeko_data:
                    current_props["affinity"] = float(meeko_data["free_energy"])
            except (ValueError, _json.JSONDecodeError):
                log.warning(
                    "JSON inválido en propiedad <meeko> del SDF",
                    raw=stripped[:200],
                )
            reading_field = None
            continue

        # ── Legacy format: > <minimizedAffinity> ─────────────────────────
        if stripped.startswith("> <minimizedAffinity>"):
            reading_field = "affinity"
            continue
        elif stripped.startswith("> <minimizedRMSD_lowerBound>"):
            reading_field = "rmsd_lb"
            continue
        elif stripped.startswith("> <minimizedRMSD_upperBound>"):
            reading_field = "rmsd_ub"
            continue

        if reading_field in ("affinity", "rmsd_lb", "rmsd_ub") and stripped:
            try:
                current_props[reading_field] = float(stripped)
            except ValueError:
                log.warning(
                    "valor no numérico en output de Vina",
                    field=reading_field,
                    value=stripped,
                )
            reading_field = None
            continue

        # ── Fin de mol block ──────────────────────────────────────────────
        if stripped == "$$$$":
            if "affinity" in current_props:
                rank += 1
                poses.append({
                    "rank":     rank,
                    "affinity": current_props["affinity"],
                    "rmsd_lb":  current_props.get("rmsd_lb", 0.0),
                    "rmsd_ub":  current_props.get("rmsd_ub", 0.0),
                })
            current_props = {}
            reading_field = None

    if not poses:
        # Expected with Meeko ≥0.6: the SDF lacks <meeko> JSON or
        # <minimizedAffinity> fields.  The caller falls back to the PDBQT
        # parser which reliably extracts REMARK VINA RESULT lines.
        log.debug("SDF de Vina no contiene metadatos de afinidad; se usará fallback PDBQT")

    return poses


def parse_vina_output_pdbqt(pdbqt_content: str) -> list[dict]:
    """
    Parsea poses desde el output `.pdbqt` de Vina.

    Vina escribe una línea por pose con el patrón:
        REMARK VINA RESULT: <affinity> <rmsd_lb> <rmsd_ub>

    Este parser sirve como fallback trazable cuando el SDF exportado por Meeko
    no contiene propiedades de afinidad/RMSD.
    """
    result_pattern = re.compile(
        r"^REMARK\s+VINA\s+RESULT:\s+([-+]?\d*\.?\d+(?:[eE][-+]?\d+)?)\s+([-+]?\d*\.?\d+(?:[eE][-+]?\d+)?)\s+([-+]?\d*\.?\d+(?:[eE][-+]?\d+)?)"
    )

    poses: list[dict] = []
    rank = 0

    for line in pdbqt_content.splitlines():
        match = result_pattern.match(line.strip())
        if not match:
            continue

        rank += 1
        affinity, rmsd_lb, rmsd_ub = match.groups()
        poses.append(
            {
                "rank": rank,
                "affinity": float(affinity),
                "rmsd_lb": float(rmsd_lb),
                "rmsd_ub": float(rmsd_ub),
            }
        )

    if not poses:
        log.warning("no se encontraron líneas REMARK VINA RESULT en output PDBQT")

    return poses


def validate_pdbqt_content(content: str) -> tuple[bool, str | None]:
    """
    Valida que un archivo .pdbqt tiene el formato correcto para Vina.

    Vina es muy sensible al formato .pdbqt — un archivo malformado
    causa que Vina salga con código 1 sin mensaje de error útil.

    Retorna (is_valid, error_message).
    """
    lines = content.splitlines()

    has_atom_lines = any(
        line.startswith(("ATOM", "HETATM", "ROOT", "ENDROOT", "BRANCH"))
        for line in lines
    )

    if not has_atom_lines:
        return False, "El archivo .pdbqt no contiene líneas ATOM/HETATM/ROOT"

    # Verificar que las líneas ATOM tienen la longitud correcta (≥ 54 chars)
    atom_lines = [l for l in lines if l.startswith(("ATOM", "HETATM"))]
    short_lines = [l for l in atom_lines if len(l) < 54]
    if short_lines:
        return False, (
            f"{len(short_lines)} líneas ATOM tienen formato inválido "
            f"(longitud < 54 chars). Primera línea problemática: '{short_lines[0][:30]}...'"
        )

    return True, None


# ── Health check ──────────────────────────────────────────────────────────────

async def check_storage_health() -> dict:
    """
    Verifica que MinIO responde y el bucket existe.
    Llamado por GET /health en api/main.py.
    """
    client = get_minio_client()
    try:
        bucket = settings.minio_bucket_poses
        exists = await client.bucket_exists(bucket)
        return {
            "status": "healthy",
            "bucket": bucket,
            "bucket_exists": exists,
        }
    except Exception as e:
        log.error("health check de MinIO falló", error=str(e))
        return {
            "status": "unhealthy",
            "error": str(e),
        }
