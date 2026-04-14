"""
utils/cache.py

Wrapper de Redis con métodos tipados para dos usos distintos:

1. Cache de resultados — evita recalcular cosas caras:
   - Poses de docking: un mismo SMILES contra el mismo target
     no se vuelve a dockar si ya existe en cache.
   - Propiedades fisicoquímicas: deterministas, mismo SMILES
     siempre da el mismo resultado.

2. Pub/Sub de progreso — el worker de Celery publica el progreso
   del docking y el frontend hace polling para mostrarlo.

Por qué un wrapper y no usar redis directamente:
   - Centraliza la serialización/deserialización JSON
   - Centraliza el manejo de errores de conexión
   - Facilita el mocking en tests (una sola clase que mockear)
   - Añade logging estructurado a todas las operaciones

Bases de Redis usadas (definidas en config.py):
   db=0  cache general (propiedades, poses)
   db=1  Celery broker (cola de tareas)
   db=2  Celery result backend (resultados de tasks)

Este módulo solo usa db=0. Celery gestiona db=1 y db=2 internamente.
"""

import json
import uuid
from datetime import datetime
from typing import Any, TypeVar

from redis.asyncio import Redis, ConnectionPool
from redis.asyncio.client import Pipeline
from redis.exceptions import ConnectionError as RedisConnectionError
from redis.exceptions import RedisError, TimeoutError as RedisTimeoutError

from core.config import get_settings
from core.exceptions import MolDesignError
from utils.logger import get_logger

log = get_logger(__name__)
settings = get_settings()

T = TypeVar("T")


# ── Excepciones de cache ──────────────────────────────────────────────────────

class CacheError(MolDesignError):
    """
    Error de operación en Redis.
    No es crítico — el sistema debe degradarse limpiamente si el
    cache no está disponible, recalculando el valor en lugar de fallar.
    """
    http_code = 500


class CacheConnectionError(CacheError):
    """Redis no está disponible."""
    http_code = 503


# ── Serialización ─────────────────────────────────────────────────────────────

def _serialize(value: Any) -> str:
    """
    Serializa cualquier valor Python a JSON string para guardar en Redis.
    Maneja tipos que json.dumps no soporta nativamente.
    """
    def default(obj: Any) -> Any:
        if isinstance(obj, uuid.UUID):
            return str(obj)
        if isinstance(obj, datetime):
            return obj.isoformat()
        if hasattr(obj, "model_dump"):
            # Pydantic v2 model
            return obj.model_dump()
        raise TypeError(f"Tipo no serializable: {type(obj).__name__}")

    return json.dumps(value, default=default, ensure_ascii=False)


def _deserialize(raw: str | bytes) -> Any:
    """Deserializa JSON string de Redis a Python."""
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8")
    return json.loads(raw)


# ── Pool de conexiones ────────────────────────────────────────────────────────

_pool: ConnectionPool | None = None


def _get_pool() -> ConnectionPool:
    """
    Retorna el pool de conexiones a Redis, creándolo si no existe.

    Un pool de conexiones evita abrir/cerrar una conexión TCP en
    cada operación. Con max_connections=20, el pool mantiene hasta
    20 conexiones reutilizables.

    Se llama la primera vez que se usa el cache — lazy initialization.
    """
    global _pool
    if _pool is None:
        _pool = ConnectionPool.from_url(
            str(settings.redis_url),
            max_connections=20,
            decode_responses=False,  # recibimos bytes, decodificamos nosotros
            socket_connect_timeout=5,
            socket_timeout=5,
            retry_on_timeout=True,
        )
        log.info("pool de conexiones Redis creado", url=str(settings.redis_url))
    return _pool


def get_redis() -> Redis:
    """
    Retorna un cliente Redis usando el pool compartido.

    No crea una nueva conexión — toma una del pool.
    No es necesario cerrarla manualmente; el pool la recicla.
    """
    return Redis(connection_pool=_get_pool())


async def close_redis_pool() -> None:
    """
    Cierra el pool de conexiones Redis limpiamente.
    Llamado en el shutdown de api/main.py junto con close_engine().
    """
    global _pool
    if _pool is not None:
        await _pool.aclose()
        _pool = None
        log.info("pool de conexiones Redis cerrado")


# ── Construcción de cache keys ────────────────────────────────────────────────

class CacheKey:
    """
    Centraliza la construcción de todas las cache keys del sistema.

    Usar strings hardcodeados dispersos en el código garantiza
    colisiones de keys y bugs difíciles de encontrar. Esta clase
    es la única fuente de verdad para los nombres de keys.

    Formato: {namespace}:{identificador}
    Ejemplo: "docking:abc123def456" donde "abc123..." es el smiles_hash
    """

    @staticmethod
    def docking(smiles_hash: str, target_pdb_id: str) -> str:
        """
        Cache de resultado de docking.
        Key única por (molécula, target) — la misma molécula puede
        tener resultados distintos contra targets distintos.
        """
        return f"docking:{smiles_hash}:{target_pdb_id}"

    @staticmethod
    def properties(smiles_hash: str) -> str:
        """
        Cache de propiedades fisicoquímicas.
        Solo depende del SMILES — las propiedades son independientes del target.
        """
        return f"props:{smiles_hash}"

    @staticmethod
    def job_progress(task_id: str) -> str:
        """
        Progreso de un job de docking en curso.
        Publicado por el Celery worker, leído por el endpoint de polling.
        """
        return f"progress:{task_id}"

    @staticmethod
    def molecule_score(smiles_hash: str, target_pdb_id: str) -> str:
        """Cache del score final calculado."""
        return f"score:{smiles_hash}:{target_pdb_id}"

    @staticmethod
    def rate_limit(user_id: str, endpoint: str) -> str:
        """Contador de rate limiting por usuario y endpoint."""
        return f"ratelimit:{user_id}:{endpoint}"

    @staticmethod
    def session(session_id: str) -> str:
        """Datos de sesión de usuario."""
        return f"session:{session_id}"


# ── Cache client ──────────────────────────────────────────────────────────────

class CacheClient:
    """
    Cliente de cache con operaciones tipadas y manejo de errores.

    Uso básico:
        cache = CacheClient()

        # Guardar resultado de docking
        await cache.set(
            CacheKey.docking(smiles_hash, "7E2Y"),
            docking_result.model_dump(),
            ttl=settings.redis_docking_cache_ttl,
        )

        # Leer resultado (retorna None si no existe o expiró)
        raw = await cache.get(CacheKey.docking(smiles_hash, "7E2Y"))
        if raw is not None:
            result = DockingResult(**raw)

    Degradación limpia:
        Si Redis no está disponible, get() retorna None (como si no
        hubiera cache) y set() loguea el error sin lanzar excepción.
        El sistema recalcula el valor en lugar de fallar.
    """

    def __init__(self) -> None:
        self._redis = get_redis()

    async def get(self, key: str) -> Any | None:
        """
        Obtiene un valor del cache.

        Retorna None si:
        - La key no existe
        - La key expiró (TTL llegó a 0)
        - Redis no está disponible (degradación limpia)

        Nunca lanza excepción — el caller decide qué hacer si es None.
        """
        try:
            raw = await self._redis.get(key)
            if raw is None:
                log.debug("cache miss", key=key)
                return None

            value = _deserialize(raw)
            log.debug("cache hit", key=key)
            return value

        except (RedisConnectionError, RedisTimeoutError) as e:
            log.warning(
                "Redis no disponible en get — degradando a no-cache",
                key=key,
                error=str(e),
            )
            return None

        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            log.error(
                "valor corrupto en cache — eliminando key",
                key=key,
                error=str(e),
            )
            # Elimina el valor corrupto para no bloquear futuras lecturas
            await self.delete(key)
            return None

    async def set(
        self,
        key: str,
        value: Any,
        ttl: int | None = None,
    ) -> bool:
        """
        Guarda un valor en el cache.

        Args:
            key:   cache key (usar CacheKey.*)
            value: cualquier valor serializable a JSON
            ttl:   tiempo de vida en segundos. None = no expira (evitar en prod)

        Retorna True si se guardó, False si Redis no estaba disponible.
        No lanza excepción — el sistema funciona sin cache.
        """
        try:
            serialized = _serialize(value)
            if ttl is not None:
                await self._redis.setex(key, ttl, serialized)
            else:
                await self._redis.set(key, serialized)

            log.debug("valor guardado en cache", key=key, ttl=ttl)
            return True

        except (RedisConnectionError, RedisTimeoutError) as e:
            log.warning(
                "Redis no disponible en set — continuando sin cache",
                key=key,
                error=str(e),
            )
            return False

        except (TypeError, ValueError) as e:
            log.error(
                "valor no serializable para cache",
                key=key,
                error=str(e),
                value_type=type(value).__name__,
            )
            return False

    async def delete(self, key: str) -> bool:
        """
        Elimina una key del cache.

        Útil cuando una molécula se re-evalúa y hay que invalidar
        el resultado anterior.
        """
        try:
            deleted = await self._redis.delete(key)
            log.debug("key eliminada del cache", key=key, existed=bool(deleted))
            return bool(deleted)

        except (RedisConnectionError, RedisTimeoutError) as e:
            log.warning("Redis no disponible en delete", key=key, error=str(e))
            return False

    async def exists(self, key: str) -> bool:
        """Verifica si una key existe en cache sin traer su valor."""
        try:
            return bool(await self._redis.exists(key))
        except (RedisConnectionError, RedisTimeoutError):
            return False

    async def set_many(
        self,
        items: dict[str, Any],
        ttl: int | None = None,
    ) -> bool:
        """
        Guarda múltiples valores en una sola operación atómica (pipeline).

        Más eficiente que llamar set() en un loop cuando tienes
        varias cosas que guardar al mismo tiempo (ej. propiedades +
        score al terminar la evaluación completa).
        """
        try:
            pipe: Pipeline = self._redis.pipeline()
            for key, value in items.items():
                serialized = _serialize(value)
                if ttl is not None:
                    pipe.setex(key, ttl, serialized)
                else:
                    pipe.set(key, serialized)
            await pipe.execute()

            log.debug("múltiples valores guardados en cache", count=len(items))
            return True

        except (RedisConnectionError, RedisTimeoutError) as e:
            log.warning(
                "Redis no disponible en set_many",
                count=len(items),
                error=str(e),
            )
            return False

    async def increment(self, key: str, amount: int = 1, ttl: int | None = None) -> int:
        """
        Incrementa un contador atómicamente.

        Usado para rate limiting: cada request incrementa el contador
        y se verifica si superó el límite.

        Retorna el valor después del incremento, o 0 si Redis no está disponible.
        """
        try:
            value = await self._redis.incr(key, amount)
            # Setea TTL solo en la primera llamada (cuando value == amount)
            # para no reiniciar el TTL en cada request
            if value == amount and ttl is not None:
                await self._redis.expire(key, ttl)
            return value

        except (RedisConnectionError, RedisTimeoutError) as e:
            log.warning("Redis no disponible en increment", key=key, error=str(e))
            return 0

    async def publish(self, channel: str, message: Any) -> int:
        """
        Publica un mensaje en un canal Pub/Sub de Redis.

        Usado por el worker de Celery para publicar el progreso
        del docking en tiempo real.

        El frontend puede suscribirse al canal o hacer polling
        con get() sobre la key de progreso.

        Retorna el número de suscriptores que recibieron el mensaje.
        """
        try:
            serialized = _serialize(message)
            subscribers = await self._redis.publish(channel, serialized)
            log.debug(
                "mensaje publicado en canal",
                channel=channel,
                subscribers=subscribers,
            )
            return subscribers

        except (RedisConnectionError, RedisTimeoutError) as e:
            log.warning(
                "Redis no disponible en publish",
                channel=channel,
                error=str(e),
            )
            return 0

    # ── Operaciones específicas del dominio ───────────────────────────────────

    async def get_docking_result(
        self,
        smiles_hash: str,
        target_pdb_id: str,
    ) -> dict[str, Any] | None:
        """
        Busca un resultado de docking en cache.

        Usado en services/docking/vina_service.py antes de correr Vina:
            cached = await cache.get_docking_result(smiles_hash, "7E2Y")
            if cached:
                return DockingResult(**cached)
            # Si no hay cache, corre Vina...
        """
        return await self.get(CacheKey.docking(smiles_hash, target_pdb_id))

    async def set_docking_result(
        self,
        smiles_hash: str,
        target_pdb_id: str,
        result: dict[str, Any],
    ) -> bool:
        """
        Guarda un resultado de docking en cache con el TTL configurado.

        TTL por defecto: 24 horas (redis_docking_cache_ttl en config.py).
        """
        return await self.set(
            CacheKey.docking(smiles_hash, target_pdb_id),
            result,
            ttl=settings.redis_docking_cache_ttl,
        )

    async def set_job_progress(
        self,
        task_id: str,
        progress: int,
        status: str,
        detail: str | None = None,
    ) -> bool:
        """
        Publica el progreso de un job de docking.

        Llamado por el Celery worker durante la ejecución de Vina.
        El endpoint GET /docking/status/{task_id} lee esta key.

        progress: 0-100
        status:   "preparing" | "running_vina" | "parsing" | "scoring" | "done" | "failed"

        Timestamps (started_at, finished_at) se registran automáticamente
        para trazabilidad real — nunca se fabrican al momento de polling.
        """
        from datetime import UTC, datetime

        # Lee el estado previo para preservar started_at
        existing = await self.get(CacheKey.job_progress(task_id))
        started_at = (existing or {}).get("started_at")
        if started_at is None and progress > 0:
            started_at = datetime.now(UTC).isoformat()

        finished_at = (existing or {}).get("finished_at")
        if finished_at is None and status in {"done", "failed"}:
            finished_at = datetime.now(UTC).isoformat()

        payload = {
            "task_id":     task_id,
            "progress":    max(0, min(100, progress)),
            "status":      status,
            "detail":      detail,
            "started_at":  started_at,
            "finished_at": finished_at,
        }
        # TTL de 1 hora — si el job no termina en 1h algo salió muy mal
        return await self.set(
            CacheKey.job_progress(task_id),
            payload,
            ttl=3600,
        )

    async def get_job_progress(self, task_id: str) -> dict[str, Any] | None:
        """Lee el progreso de un job de docking para el endpoint de polling."""
        return await self.get(CacheKey.job_progress(task_id))

    async def check_rate_limit(
        self,
        user_id: str,
        endpoint: str,
        limit: int,
        window_seconds: int,
    ) -> tuple[bool, int]:
        """
        Verifica y actualiza el rate limit de un usuario.

        Retorna (allowed, current_count):
            allowed=True  si el usuario no superó el límite
            allowed=False si debe ser bloqueado

        Uso en api/middleware.py:
            allowed, count = await cache.check_rate_limit(
                user_id=user.id,
                endpoint="/docking/submit",
                limit=10,           # máximo 10 dockings
                window_seconds=3600 # por hora
            )
            if not allowed:
                raise HTTPException(429, "Rate limit superado")
        """
        key = CacheKey.rate_limit(user_id, endpoint)
        count = await self.increment(key, ttl=window_seconds)
        allowed = count <= limit

        if not allowed:
            log.warning(
                "rate limit superado",
                user_id=user_id,
                endpoint=endpoint,
                count=count,
                limit=limit,
            )

        return allowed, count


# ── Health check ──────────────────────────────────────────────────────────────

async def check_redis_health() -> dict[str, Any]:
    """
    Verifica que Redis responde correctamente.
    Llamado por GET /health en api/main.py.
    """
    try:
        redis = get_redis()
        await redis.ping()
        info = await redis.info("server")
        return {
            "status":        "healthy",
            "redis_version": info.get("redis_version", "unknown"),
        }
    except (RedisConnectionError, RedisTimeoutError, RedisError) as e:
        log.error("health check de Redis falló", error=str(e))
        raise CacheConnectionError(
            "No se puede conectar a Redis. "
            "Verifica que el servicio esté corriendo y REDIS_URL sea correcta."
        ) from e


# ── Instancia singleton ───────────────────────────────────────────────────────

# Instancia global para usar en módulos que no tienen inyección de dependencias
# (workers de Celery, scripts de utilidad).
#
# En endpoints de FastAPI, usa la dependency:
#     async def my_endpoint(cache: CacheClient = Depends(get_cache)):
#
# En workers de Celery o módulos de servicio, importa directamente:
#     from utils.cache import cache
#     await cache.set_job_progress(task_id, 50, "running_vina")

cache = CacheClient()


async def get_cache() -> CacheClient:
    """
    Dependency de FastAPI para inyectar el cache en endpoints.

    Uso:
        from utils.cache import get_cache, CacheClient
        from fastapi import Depends

        @router.get("/docking/status/{task_id}")
        async def get_status(
            task_id: str,
            cache: CacheClient = Depends(get_cache),
        ):
            progress = await cache.get_job_progress(task_id)
            ...
    """
    return cache
