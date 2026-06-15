from functools import lru_cache
import tempfile
from pathlib import Path
from typing import Literal

from pydantic import Field, PostgresDsn, RedisDsn, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Configuración global del sistema.

    Pydantic Settings lee automáticamente desde variables de entorno
    y desde el archivo .env. El orden de prioridad es:
    1. Variables de entorno del sistema (más alta)
    2. Archivo .env
    3. Valores por defecto definidos aquí (más baja)

    Esto significa que en Docker, las variables del compose.yml
    sobreescriben las del .env, que es exactamente lo que queremos.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,      # DATABASE_URL == database_url
        extra="ignore",            # Ignora variables en .env que no estén aquí
    )

    # ── Aplicación ──────────────────────────────────────────────────────────

    environment: Literal["development", "production", "testing"] = "development"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    secret_key: str = Field(
        ...,
        min_length=32,
        description="Clave para firmar JWT. Genera con: openssl rand -hex 32",
    )
    supabase_jwt_secret: str | None = Field(
        default=None,
        description="Secret key de Supabase para validar los tokens JWT entrantes. Obligatorio si se usa Supabase Auth.",
    )

    # ── Base de datos ────────────────────────────────────────────────────────

    database_url: PostgresDsn = Field(
        ...,
        description="URL de la base de datos PostgreSQL. "
                    "Ejemplo: postgresql+asyncpg://user:pass@localhost:5432/db",
    )
    db_pool_size: int = Field(default=10, ge=1, le=50)
    db_max_overflow: int = Field(default=20, ge=0, le=100)
    db_pool_timeout: int = Field(default=30, ge=5)     # segundos
    db_echo_sql: bool = False   # True en dev para ver queries en consola

    # ── Redis ────────────────────────────────────────────────────────────────

    redis_url: RedisDsn = Field(
        default="redis://localhost:6379/0",
        description="URL de conexión a Redis.",
    )
    # TTL del cache de docking: 24 horas.
    # Una molécula ya evaluada no se vuelve a dockar si nadie la modificó.
    redis_docking_cache_ttl: int = Field(default=86400, ge=60)
    # TTL del cache de propiedades: 1 hora.
    # Las propiedades fisicoquímicas son deterministas — mismo SMILES, mismo resultado.
    redis_properties_cache_ttl: int = Field(default=3600, ge=60)

    # ── MinIO / S3 ───────────────────────────────────────────────────────────

    minio_endpoint: str = "localhost:9005"
    minio_access_key: str = Field(..., min_length=3)
    minio_secret_key: str = Field(..., min_length=8)
    minio_bucket_poses: str = "docking-poses"
    minio_secure: bool = False   # True en producción (HTTPS)

    # ── Celery ───────────────────────────────────────────────────────────────

    # Celery usa Redis como broker (cola de tareas) y como backend (resultados).
    # Usamos db=1 para broker y db=2 para resultados, separados del cache (db=0).
    @property
    def celery_broker_url(self) -> str:
        base = str(self.redis_url).rsplit("/", 1)[0]
        return f"{base}/1"

    @property
    def celery_result_backend(self) -> str:
        base = str(self.redis_url).rsplit("/", 1)[0]
        return f"{base}/2"

    celery_task_soft_time_limit: int = Field(default=300, ge=30)   # 5 min
    celery_task_time_limit: int = Field(default=360, ge=60)        # 6 min hard limit

    # ── Docking (AutoDock Vina) ──────────────────────────────────────────────

    vina_executable_path: str = "vina"
    meeko_prepare_receptor_path: str = "mk_prepare_receptor.py"
    meeko_prepare_ligand_path: str = "mk_prepare_ligand"
    meeko_export_path: str = "mk_export"
    meeko_default_altloc: str = "A"
    vina_exhaustiveness: int = Field(default=32, ge=1, le=128)
    # Exhaustiveness controla la profundidad de búsqueda conformacional.
    # 8 = balance razonable velocidad/calidad para uso interactivo del MVP.
    # Para calibración y benchmarking, usar vina_calibration_exhaustiveness.
    # Referencia: Trott & Olson (2010) J Comput Chem 31:455-461.
    vina_calibration_exhaustiveness: int = Field(default=32, ge=8, le=64)
    # Exhaustiveness alta para scripts de calibración/benchmark.
    # exhaustiveness=32 reduce significativamente la varianza del score
    # a costa de ~4x más tiempo de cómputo.
    vina_num_poses: int = Field(default=5, ge=1, le=20)
    vina_seed: int = Field(default=42, ge=0)
    vina_cpu: int = Field(default=1, ge=1)
    docking_max_consistency_error_pct: float = Field(default=1.0, ge=0.0, le=100.0)
    docking_allow_stdout_fallback: bool = False
    vina_temp_dir: str = Field(default_factory=lambda: str((Path(tempfile.gettempdir()) / "vina").resolve()))

    # Target fijo del MVP: receptor 5-HT1A (PDB: 7E2Y)
    #   Estructura cryo-EM del complejo 5-HT1A–Gi con serotonina co-cristalizada.
    #   Xu et al., Nature 592:469-473 (2021). DOI: 10.1038/s41586-021-03376-8
    # Cuando agregues multi-target, estos valores vendrán de la DB.
    default_target_pdb_id: str = "7E2Y"
    default_target_chain: str = "R"

    # Grid box del sitio activo de 5-HT1A (coordenadas en Angstroms).
    # Centroide geométrico de la serotonina co-cristalizada (SRO) en 7E2Y cadena R.
    # Calculado con scripts/extract_grid_from_ligand.py --pdb-id 7E2Y --ligand-id SRO --chain R
    # Metodología: Morris et al. (2009) J Comput Chem 30:2785-2791
    # Si cambias el target, DEBES recalcular estos valores con el script.
    vina_center_x: float = 103.03
    vina_center_y: float = 114.79
    vina_center_z: float = 108.36
    # Grid de 25×25×25 Å para acomodar moléculas drug-like (MW 300-500)
    # más grandes que el ligando co-cristalizado (serotonina, MW=176).
    # Referencia: Feinstein & Brylinski (2015) J Mol Graph Model 62:43-47.
    # Un grid demasiado pequeño penaliza moléculas más grandes que el co-cristalizado.
    vina_size_x: float = 25.0
    vina_size_y: float = 25.0
    vina_size_z: float = 25.0

    # ── DiffDock (alternativa generativa de docking) ─────────────────────────

    diffdock_api_url: str | None = Field(
        default=None,
        description="URL de un servidor DiffDock externo (ej. http://diffdock:5000). "
                    "Si no se configura, el sistema usa solo AutoDock Vina. "
                    "DiffDock es opcional y su ausencia nunca bloquea el pipeline.",
    )

    diffpepdock_api_url: str | None = Field(
        default=None,
        description="URL del servidor DiffPepDock para docking de péptidos (Nivel 3).",
    )

    colabfold_api_url: str | None = Field(
        default=None,
        description="URL del servidor ColabFold/AlphaFold-Multimer para docking de péptidos (Nivel 3).",
    )

    peptide_refinement_enabled: bool = Field(
        default=True,
        description="Flag para activar/desactivar la minimización y refinamiento post-docking en Nivel 3."
    )

    diffpepdock_prior_weight: float = Field(
        default=0.7,
        ge=0.0,
        le=1.0,
        description="Fuerza del sesgo del sitio activo en DiffPepDock (1.0 = enfocado, 0.0 = ciego)."
    )


    # ── RDKit / Química ──────────────────────────────────────────────────────

    # Límites de validación molecular.
    # Moléculas fuera de estos rangos se rechazan antes de calcular nada.
    strict_science_mode: bool = True
    strict_single_fragment_only: bool = True
    max_total_formal_charge_abs: int = Field(default=2, ge=0, le=10)
    max_atom_formal_charge_abs: int = Field(default=2, ge=0, le=6)
    mol_max_heavy_atoms: int = Field(default=80, ge=10, le=200)
    mol_max_molecular_weight: float = Field(default=800.0, ge=100.0)
    mol_min_molecular_weight: float = Field(default=100.0, ge=50.0)

    # Número de intentos de generación de confórmero 3D con ETKDG.
    # Si falla, reintenta con random seeds distintos antes de lanzar error.
    conformer_max_attempts: int = Field(default=3, ge=1, le=10)

    # ── Scoring ──────────────────────────────────────────────────────────────
    
    rescoring_url: str = Field(
        default="http://rescoring:8001",
        description="URL del microservicio de ML Rescoring."
    )

    # Pesos del score compuesto. Deben sumar 1.0.
    # Justificación: afinidad es la métrica más directamente relevante
    # para el objetivo del juego (encontrar buenos ligandos).
    score_weight_affinity: float = Field(default=0.45, ge=0.0, le=1.0)
    score_weight_adme: float = Field(default=0.30, ge=0.0, le=1.0)
    score_weight_druglikeness: float = Field(default=0.25, ge=0.0, le=1.0)

    @field_validator("score_weight_druglikeness")
    @classmethod
    def weights_must_sum_to_one(cls, druglikeness: float, info) -> float:
        """Valida que los tres pesos del score sumen exactamente 1.0."""
        data = info.data
        affinity = data.get("score_weight_affinity", 0)
        adme = data.get("score_weight_adme", 0)
        total = round(affinity + adme + druglikeness, 10)
        if abs(total - 1.0) > 1e-9:
            raise ValueError(
                f"Los pesos del score deben sumar 1.0, "
                f"pero suman {total:.4f} "
                f"(affinity={affinity}, adme={adme}, druglikeness={druglikeness})"
            )
        return druglikeness

    # ── IA / Gemini API ────────────────────────────────────────────────────────
    
    gemini_api_key: str | None = Field(
        default=None,
        description="Requerida para reportes científicos de IA. "
                    "Sin esta clave, el servicio de reportes no estará disponible.",
    )
    gemini_model: str = "gemini-2.5-flash"
    gemini_max_tokens: int = Field(default=2000, ge=100, le=4096)

    # Ollama Local LLM
    ollama_base_url: str = Field(
        default="http://192.168.100.12:11434",
        description="URL de la API de Ollama corriendo en el host."
    )
    ollama_model: str = Field(
        default="gemma3:1b",
        description="Modelo local para Ollama."
    )

    # ── Anthropic API ──────────────────────────────────────────────────────────
    anthropic_api_key: str | None = Field(
        default=None,
        description="Clave de Anthropic para generar reportes IA usando Claude.",
    )
    anthropic_model: str = "claude-haiku-4-5-20251001"

    # ── Local AI (LM Studio) ────────────────────────────────────────────────
    lmstudio_url: str = "http://localhost:1234"
    lmstudio_model: str = "local-model"

    # ── Autenticación ────────────────────────────────────────────────────────

    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = Field(default=60, ge=5)
    jwt_refresh_token_expire_days: int = Field(default=7, ge=1)
    
    # ── Rate Limiting ────────────────────────────────────────────────────────
    anonymous_rate_limit: int = Field(
        default=2, 
        description="Límite de evaluaciones gratuitas permitidas para usuarios anónimos por IP."
    )

    # ── CORS ─────────────────────────────────────────────────────────────────

    # En desarrollo, permite cualquier origen.
    # En producción, reemplaza con el dominio real de tu frontend.
    cors_origins: list[str] = [
        "http://localhost:3000",
        "http://localhost:3001",
        "http://localhost:5173",
        "http://192.168.1.64:3000",
        "http://192.168.1.64:3001",
        "https://molecule-design.vercel.app"
    ]

    # ── Solana Blockchain ────────────────────────────────────────────────────

    solana_rpc_url: str = Field(
        default="https://api.devnet.solana.com",
        description="URL del RPC de Solana. Usa devnet para desarrollo.",
    )
    solana_private_key: str | None = Field(
        default=None,
        description="Private key hexadecimal de la wallet de Solana para firmar transacciones.",
    )

    # ── Propiedades derivadas ────────────────────────────────────────────────

    @property
    def is_development(self) -> bool:
        return self.environment == "development"

    @property
    def is_production(self) -> bool:
        return self.environment == "production"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """
    Retorna la instancia singleton de Settings.

    @lru_cache garantiza que el archivo .env se lee una sola vez
    en toda la vida del proceso. Esto es importante porque leer
    variables de entorno en cada request sería lento e inconsistente.

    Uso en FastAPI con inyección de dependencias:

        from core.config import get_settings
        from fastapi import Depends

        def my_endpoint(settings: Settings = Depends(get_settings)):
            ...

    O directamente en módulos que no son endpoints:

        from core.config import get_settings
        settings = get_settings()
    """
    return Settings()
