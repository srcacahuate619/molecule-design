"""
core/database.py

Conexión async a PostgreSQL con SQLAlchemy 2.0.

Hay tres cosas que viven aquí:

1. Engine async — el pool de conexiones a PostgreSQL
2. Session factory — crea sesiones de DB para cada request/task
3. Dependency de FastAPI — inyecta una sesión en cada endpoint

Por qué async:
    FastAPI es async. Si usas SQLAlchemy síncrono, cada query bloquea
    el event loop completo — ningún otro request puede procesarse
    mientras esperas a PostgreSQL. Con asyncpg + SQLAlchemy async,
    el event loop sigue procesando requests mientras la query corre.

Por qué un pool de conexiones:
    Abrir una conexión TCP a PostgreSQL tarda ~50ms. Con un pool,
    esas conexiones se reutilizan. El pool_size=10 significa que
    tienes 10 conexiones siempre abiertas y listas.
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

from sqlalchemy import event, text
from sqlalchemy.exc import OperationalError, SQLAlchemyError
from sqlalchemy.ext.asyncio import (
    AsyncConnection,
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from core.config import get_settings
from core.exceptions import DatabaseConnectionError, DatabaseQueryError
from core.models import Base
from utils.logger import get_logger

log = get_logger(__name__)
# NOTE: settings se accede via get_settings() de forma lazy dentro de las
# funciones, no a nivel de módulo, para permitir importar este módulo sin
# que todas las variables de entorno estén presentes (critical para tests).


# ── Engine ────────────────────────────────────────────────────────────────────

def _create_engine() -> AsyncEngine:
    """
    Crea el engine async de SQLAlchemy.

    Se llama UNA sola vez al arrancar la app (en el lifespan de main.py).
    El engine no es una conexión — es el gestor del pool de conexiones.

    pool_size=10:       conexiones siempre abiertas
    max_overflow=20:    conexiones extras permitidas bajo carga alta
    pool_timeout=30:    segundos de espera si todas las conexiones están ocupadas
    pool_pre_ping=True: verifica que la conexión sigue viva antes de usarla.
                        Evita el error "connection was closed" después de que
                        PostgreSQL reinicia o cierra conexiones idle.
    """
    settings = get_settings()
    engine = create_async_engine(
        str(settings.database_url),
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
        pool_timeout=settings.db_pool_timeout,
        pool_pre_ping=True,
        echo=settings.db_echo_sql,
        # json_serializer personalizado para manejar UUID y datetime en JSONB
        json_serializer=_json_serializer,
        json_deserializer=_json_deserializer,
    )

    # Log cuando se crean/cierran conexiones del pool (solo en desarrollo)
    if settings.is_development:
        @event.listens_for(engine.sync_engine, "connect")
        def on_connect(dbapi_connection: Any, connection_record: Any) -> None:
            log.debug("nueva conexión abierta en el pool")

        @event.listens_for(engine.sync_engine, "checkout")
        def on_checkout(dbapi_connection: Any, connection_record: Any, connection_proxy: Any) -> None:
            log.debug("conexión tomada del pool")

    log.info(
        "engine de base de datos creado",
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
        echo=settings.db_echo_sql,
    )
    return engine


def _json_serializer(obj: Any) -> str:
    """
    Serializa objetos Python a JSON para columnas JSONB de PostgreSQL.
    El serializer por defecto de SQLAlchemy no maneja UUID ni datetime.
    """
    import json
    import uuid
    from datetime import datetime

    def default(o: Any) -> Any:
        if isinstance(o, uuid.UUID):
            return str(o)
        if isinstance(o, datetime):
            return o.isoformat()
        raise TypeError(f"Tipo no serializable: {type(o)}")

    return json.dumps(obj, default=default)


def _json_deserializer(s: str) -> Any:
    """Deserializa JSON de PostgreSQL a Python. El default es suficiente."""
    import json
    return json.loads(s)


# ── Engine (lazy singleton) ───────────────────────────────────────────────────
#
# IMPORTANTE: el engine NO se crea al importar el módulo.
# Se crea la primera vez que se llama a get_engine(). Esto permite:
# 1. Importar core.database en tests sin conectar a PostgreSQL.
# 2. Overridear settings/env vars antes de que el engine exista.
# 3. Evitar efectos secundarios al importar cualquier módulo del backend.

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker | None = None


def get_engine() -> AsyncEngine:
    """Retorna el engine singleton, creándolo en la primera llamada."""
    global _engine
    if _engine is None:
        _engine = _create_engine()
    return _engine


def get_session_factory() -> async_sessionmaker:
    """Retorna el session factory singleton, creándolo en la primera llamada."""
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(
            bind=get_engine(),
            class_=AsyncSession,
            expire_on_commit=False,
            autocommit=False,
            autoflush=False,
        )
    return _session_factory


def set_engine(engine: AsyncEngine) -> None:
    """
    Permite inyectar un engine externo (para tests).
    Debe llamarse ANTES de que cualquier código use get_engine().
    """
    global _engine, _session_factory
    _engine = engine
    _session_factory = async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )


# ── Dependency de FastAPI ─────────────────────────────────────────────────────

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency de FastAPI que inyecta una sesión de DB en cada endpoint.

    Uso en un endpoint:
        from core.database import get_db
        from sqlalchemy.ext.asyncio import AsyncSession
        from fastapi import Depends

        @router.post("/molecules")
        async def create_molecule(
            data: MoleculeCreate,
            db: AsyncSession = Depends(get_db),
        ):
            # 'db' es una sesión activa, única para este request
            ...

    El bloque try/except/finally garantiza que:
    - Si el endpoint termina bien → commit automático
    - Si lanza una excepción → rollback automático
    - En cualquier caso → la sesión se cierra y la conexión vuelve al pool

    NUNCA hagas commit manualmente en un endpoint si usas esta dependency.
    El commit lo gestiona esta función.
    """
    async with get_session_factory()() as session:
        try:
            yield session
            await session.commit()
        except SQLAlchemyError as e:
            await session.rollback()
            log.error(
                "error de base de datos en request",
                error=str(e),
                error_type=type(e).__name__,
            )
            raise DatabaseQueryError(
                f"Error ejecutando operación en la base de datos: {type(e).__name__}"
            ) from e
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


# ── Context manager para uso fuera de FastAPI ─────────────────────────────────

@asynccontextmanager
async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Context manager para obtener una sesión de DB fuera del contexto
    de un endpoint de FastAPI (Celery workers, scripts, tests).

    Uso en un worker de Celery:
        from core.database import get_db_session

        async def run_docking_task(molecule_id: str):
            async with get_db_session() as db:
                molecule = await db.get(MoleculeORM, molecule_id)
                ...
                # commit automático al salir del bloque 'async with'

    A diferencia de get_db(), aquí el commit es explícito al final
    del bloque en lugar de ser manejado por FastAPI.
    """
    async with get_session_factory()() as session:
        try:
            yield session
            await session.commit()
        except SQLAlchemyError as e:
            await session.rollback()
            log.error(
                "error de base de datos en sesión manual",
                error=str(e),
                error_type=type(e).__name__,
            )
            raise DatabaseQueryError(
                f"Error en sesión de base de datos: {type(e).__name__}"
            ) from e
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


# ── Health check ──────────────────────────────────────────────────────────────

async def check_database_health() -> dict[str, Any]:
    """
    Verifica que la conexión a PostgreSQL funciona.
    Llamado por el endpoint GET /health de la API.

    Retorna un dict con el estado y la versión de PostgreSQL.
    Si falla, lanza DatabaseConnectionError.
    """
    try:
        async with get_engine().connect() as conn:
            result = await conn.execute(text("SELECT version(), current_database()"))
            row = result.fetchone()
            pg_version, db_name = row[0], row[1]

        log.debug("health check de DB exitoso", db_name=db_name)
        return {
            "status": "healthy",
            "database": db_name,
            "postgresql_version": pg_version.split(" ")[1],  # ej. "16.2"
        }

    except OperationalError as e:
        log.error("health check de DB falló", error=str(e))
        raise DatabaseConnectionError(
            "No se puede conectar a PostgreSQL. "
            "Verifica que el servicio esté corriendo y DATABASE_URL sea correcta."
        ) from e


# ── Inicialización de tablas ──────────────────────────────────────────────────

async def create_all_tables() -> None:
    """
    Crea todas las tablas definidas en core/models.py si no existen.

    SOLO para desarrollo y testing. En producción, las tablas se
    crean con las migraciones SQL en db/migrations/.

    Llamado en el lifespan de main.py cuando environment == "development":
        if settings.is_development:
            await create_all_tables()
    """
    async with get_engine().begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    log.info("tablas creadas o verificadas en la base de datos")


async def drop_all_tables() -> None:
    """
    Elimina todas las tablas. SOLO para tests.

    En conftest.py:
        @pytest.fixture(autouse=True)
        async def reset_db():
            await create_all_tables()
            yield
            await drop_all_tables()
    """
    async with get_engine().begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    log.warning("todas las tablas eliminadas de la base de datos")


# ── Cierre limpio del engine ──────────────────────────────────────────────────

async def close_engine() -> None:
    """
    Cierra el pool de conexiones limpiamente al apagar la app.

    Llamado en el lifespan de main.py al hacer shutdown:
        @asynccontextmanager
        async def lifespan(app: FastAPI):
            yield
            await close_engine()   # ← aquí

    Sin esto, las conexiones del pool quedan abiertas en PostgreSQL
    hasta que el timeout del servidor las cierra (puede tardar minutos).
    """
    if _engine is not None:
        await _engine.dispose()
        log.info("pool de conexiones cerrado limpiamente")
