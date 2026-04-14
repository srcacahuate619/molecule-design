"""
chem/router.py

FastAPI router que expone el servicio químico como endpoints HTTP.

Tres endpoints principales:

    POST /chem/validate
        Valida un SMILES y retorna propiedades básicas.
        Rápido (~10ms). Llamado en tiempo real desde el editor Ketcher
        mientras el usuario escribe/modifica la molécula.

    POST /chem/properties
        Calcula todas las propiedades fisicoquímicas de una molécula válida.
        Rápido (~50ms). Llamado después de que el usuario confirma una molécula.

    POST /chem/conformer
        Genera la estructura 3D y la guarda en MinIO.
        Moderado (~500ms-3s según complejidad). Llamado antes del docking.
        Retorna la ruta del archivo en MinIO, no el archivo en sí.

Relación con el resto del pipeline:
    El frontend llama a estos endpoints en secuencia antes de enviar
    el job de docking a la cola de Celery. El docking (chem/router.py
    no lo maneja — eso es services/docking/queue_handler.py) necesita
    que el conformer ya exista en MinIO.

Decisión de diseño: validación en el router vs. en el servicio.
    Los routers validan el formato del request (Pydantic automático).
    Los servicios validan la semántica científica (SMILES, valencia).
    Esta separación significa que un SMILES llega al servicio químico
    siempre como string bien formado, pero puede ser inválido
    científicamente — y eso lo detecta chem/validator.py.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from chem.conformer import generate_conformer
from chem.properties import calculate_properties, summarize_adme_profile
from chem.validator import validate_smiles, validate_smiles_or_raise
from core.database import get_db
from core.exceptions import (
    ConformerGenerationError,
    InvalidSMILES,
    MolDesignError,
    PropertyCalculationError,
)
from core.models import (
    PhysicochemicalProperties,
    ValidationResult,
)
from utils.cache import CacheClient, CacheKey, get_cache
from utils.logger import bind_context, get_logger

log = get_logger(__name__)

router = APIRouter(
    prefix="/chem",
    tags=["Química computacional"],
)


# ── Schemas de request/response ───────────────────────────────────────────────

class ValidateRequest(BaseModel):
    smiles: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="SMILES de la molécula a validar",
        examples=["CC(=O)Oc1ccccc1C(=O)O"],
    )


class PropertiesRequest(BaseModel):
    smiles: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="SMILES de la molécula. Se valida internamente.",
        examples=["CN1C=NC2=C1C(=O)N(C(=O)N2C)C"],
    )


class ConformerRequest(BaseModel):
    smiles: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="SMILES de la molécula. Se valida y canonicaliza internamente.",
    )
    force_regenerate: bool = Field(
        default=False,
        description=(
            "Si True, regenera el conformer aunque ya exista en MinIO. "
            "Útil cuando el usuario quiere explorar otra conformación."
        ),
    )


class ConformerResponse(BaseModel):
    canonical_smiles:       str
    smiles_hash:            str
    conformer_path:         str
    num_atoms_3d:           int
    optimization_converged: bool
    had_macrocycle:         bool
    molecular_formula:      str
    from_cache:             bool = False


class PropertiesResponse(BaseModel):
    """
    Respuesta del endpoint de propiedades.
    Incluye las propiedades calculadas y un resumen ADME para la UI.
    """
    properties:   PhysicochemicalProperties
    adme_summary: str
    smiles_hash:  str
    from_cache:   bool = False


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post(
    "/validate",
    response_model=ValidationResult,
    summary="Valida un SMILES",
    description=(
        "Valida la estructura química de un SMILES usando RDKit. "
        "Retorna el SMILES canónico, hash SHA-256, fórmula molecular "
        "y listas de errores/warnings. Llamado en tiempo real desde Ketcher."
    ),
    status_code=status.HTTP_200_OK,
)
async def validate_endpoint(
    request: ValidateRequest,
) -> ValidationResult:
    """
    Endpoint de validación rápida.

    No usa cache porque la validación es determinista y ~10ms —
    el costo de consultar Redis sería comparable al de recalcular.

    No requiere autenticación — la validación es una operación de lectura
    sin efectos secundarios. Un usuario no autenticado puede verificar
    si su SMILES es válido antes de crear una cuenta.

    Retorna siempre HTTP 200 con is_valid=True o is_valid=False.
    Los errores de validación científica no son HTTP 4xx — son información
    estructurada que el frontend usa para mostrar feedback al usuario.
    """
    bind_context(endpoint="validate", smiles_preview=request.smiles[:20])

    result = validate_smiles(request.smiles)

    log.info(
        "validación completada",
        is_valid=result.is_valid,
        formula=result.molecular_formula,
        errors=len(result.errors),
        warnings=len(result.warnings),
    )

    return result


@router.post(
    "/properties",
    response_model=PropertiesResponse,
    summary="Calcula propiedades fisicoquímicas",
    description=(
        "Calcula MW, logP, TPSA, HBD/HBA, enlaces rotables, anillos "
        "y evalúa las reglas de Lipinski y Veber. "
        "Incluye un resumen narrativo del perfil ADME para la UI."
    ),
    status_code=status.HTTP_200_OK,
)
async def properties_endpoint(
    request: PropertiesRequest,
    cache: CacheClient = Depends(get_cache),
) -> PropertiesResponse:
    """
    Calcula propiedades fisicoquímicas con cache.

    Las propiedades son deterministas: el mismo SMILES siempre produce
    el mismo resultado. El cache (TTL 1h) evita recalcular si el usuario
    envía la misma molécula varias veces durante una sesión.

    El cache key usa el hash SHA-256 del SMILES canónico, no el SMILES
    raw del usuario — distintas representaciones de la misma molécula
    comparten el mismo cache entry.

    Lanza HTTP 422 si el SMILES es inválido (via InvalidSMILES).
    """
    bind_context(endpoint="properties", smiles_preview=request.smiles[:20])

    # Paso 1: validar primero para obtener el hash (necesario para el cache key)
    # validate_smiles_or_raise lanza InvalidSMILES → HTTP 422 si es inválido
    validation = validate_smiles_or_raise(request.smiles)
    smiles_hash = validation.smiles_hash

    # Paso 2: verificar cache
    cache_key = CacheKey.properties(smiles_hash)
    cached = await cache.get(cache_key)
    if cached is not None:
        log.debug("propiedades desde cache", hash_prefix=smiles_hash[:8])
        return PropertiesResponse(
            properties=PhysicochemicalProperties(**cached["properties"]),
            adme_summary=cached["adme_summary"],
            smiles_hash=smiles_hash,
            from_cache=True,
        )

    # Paso 3: calcular propiedades
    props = calculate_properties(request.smiles)
    adme_summary = summarize_adme_profile(props)

    # Paso 4: guardar en cache
    await cache.set(
        cache_key,
        {
            "properties":   props.model_dump(),
            "adme_summary": adme_summary,
        },
        ttl=3600,   # 1 hora
    )

    log.info(
        "propiedades calculadas",
        formula=validation.molecular_formula,
        mw=props.molecular_weight,
        lipinski=props.lipinski_pass,
        hash_prefix=smiles_hash[:8],
    )

    return PropertiesResponse(
        properties=props,
        adme_summary=adme_summary,
        smiles_hash=smiles_hash,
        from_cache=False,
    )


@router.post(
    "/conformer",
    response_model=ConformerResponse,
    summary="Genera estructura 3D",
    description=(
        "Genera un conformer 3D usando ETKDGv3 y optimiza con MMFF94. "
        "El archivo .sdf se guarda en MinIO. "
        "Retorna la ruta del archivo, no el archivo en sí. "
        "El frontend usa esta ruta para el visor Mol*."
    ),
    status_code=status.HTTP_201_CREATED,
)
async def conformer_endpoint(
    request: ConformerRequest,
    cache: CacheClient = Depends(get_cache),
) -> ConformerResponse:
    """
    Genera estructura 3D con cache basado en existencia del archivo en MinIO.

    El conformer se genera una sola vez por molécula y se reutiliza.
    force_regenerate=True permite al usuario explorar una conformación
    alternativa (útil si ETKDG generó una geometría subóptima).

    Lanza HTTP 422 si el SMILES es inválido.
    Lanza HTTP 422 si la generación 3D falla (ConformerGenerationError).
    Lanza HTTP 500 si hay un error inesperado en RDKit.
    """
    bind_context(endpoint="conformer", smiles_preview=request.smiles[:20])

    # Verificar si ya existe en MinIO (a menos que se pida regenerar)
    if not request.force_regenerate:
        validation = validate_smiles_or_raise(request.smiles)
        smiles_hash = validation.smiles_hash

        from utils.file_handlers import StoragePath, object_exists
        existing_path = StoragePath.ligand_conformer(smiles_hash)

        if await object_exists(existing_path):
            log.debug(
                "conformer existente en MinIO",
                hash_prefix=smiles_hash[:8],
                path=existing_path,
            )
            # Retornamos los metadatos del conformer cacheado
            # Los datos completos están en MinIO — no necesitamos
            # descargar el archivo para responder al frontend
            return ConformerResponse(
                canonical_smiles=validation.canonical_smiles,
                smiles_hash=smiles_hash,
                conformer_path=existing_path,
                num_atoms_3d=validation.heavy_atom_count or 0,
                optimization_converged=True,
                had_macrocycle=False,
                molecular_formula=validation.molecular_formula or "",
                from_cache=True,
            )

    # Generar nuevo conformer
    result = await generate_conformer(request.smiles)

    log.info(
        "conformer generado",
        formula=result["molecular_formula"],
        atoms=result["num_atoms_3d"],
        converged=result["optimization_converged"],
        macrocycle=result["had_macrocycle"],
        path=result["conformer_path"],
    )

    return ConformerResponse(
        canonical_smiles=result["canonical_smiles"],
        smiles_hash=result["smiles_hash"],
        conformer_path=result["conformer_path"],
        num_atoms_3d=result["num_atoms_3d"],
        optimization_converged=result["optimization_converged"],
        had_macrocycle=result["had_macrocycle"],
        molecular_formula=result["molecular_formula"],
        from_cache=False,
    )


# ── Endpoint de salud del servicio ────────────────────────────────────────────

@router.get(
    "/health",
    summary="Estado del servicio químico",
    description="Verifica que RDKit está disponible y funcionando.",
    status_code=status.HTTP_200_OK,
    include_in_schema=False,   # no aparece en /docs — es para monitoreo interno
)
async def chem_health() -> dict:
    """
    Verifica RDKit con una molécula de prueba simple (aspirina).
    Si RDKit no está disponible, este endpoint falla y el health check
    general de la API marca el servicio como no saludable.
    """
    from rdkit import Chem
    from rdkit import __version__ as rdkit_version

    # Prueba funcional mínima
    test_mol = Chem.MolFromSmiles("CC(=O)Oc1ccccc1C(=O)O")
    rdkit_ok = test_mol is not None

    return {
        "service":      "chem",
        "status":       "healthy" if rdkit_ok else "degraded",
        "rdkit_version": rdkit_version,
        "test_molecule": "aspirina (C9H8O4)",
        "test_passed":   rdkit_ok,
    }
