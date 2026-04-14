"""
tests/conftest.py

Fixtures de pytest compartidas por toda la suite de tests.

Este archivo es el más importante de la carpeta tests/ porque
define la infraestructura que todos los tests usan. pytest lo
descubre y carga automáticamente — no necesitas importarlo.

Hay tres capas de fixtures aquí:

1. Infraestructura (scope="session"):
   Se crean UNA vez para toda la sesión de tests.
   - Engine de DB de test (PostgreSQL separado o SQLite en memoria)
   - Tablas del schema

2. Aislamiento por test (scope="function"):
   Se crean y destruyen en cada test individual.
   - Sesión de DB con rollback automático
   - Cliente HTTP de FastAPI
   - Mocks de Redis y MinIO

3. Datos de prueba (scope="function"):
   Moléculas y targets de referencia con valores conocidos.
   - Aspirina (C9H8O4) — Lipinski compliant, valores bien documentados
   - Cafeína (CN1C=NC2=C1C(=O)N(C(=O)N2C)C) — para comparación
   - Target 5-HT1A (mock) — no hace docking real en tests unitarios

Por qué rollback en lugar de recrear tablas:
   Recrear tablas en cada test es lento (~500ms por test).
   Con rollback, cada test corre dentro de una transacción que
   nunca se hace commit — los cambios desaparecen al hacer rollback.
   Esto es ~10x más rápido y produce el mismo aislamiento.
"""

import os

# ─── Set test environment BEFORE any imports that trigger get_settings() ─────
# This MUST happen before importing core.config or any module that depends on it.
# Without these env vars, Settings() raises ValidationError at import time.
os.environ.setdefault("ENVIRONMENT", "testing")
os.environ.setdefault("SECRET_KEY", "test-secret-key-minimum-32-characters-for-jwt-signing")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://moldesign@localhost:5432/moldesign_test")
os.environ.setdefault("MINIO_ACCESS_KEY", "minioadmin")
os.environ.setdefault("MINIO_SECRET_KEY", "minioadmin123")
os.environ.setdefault("MINIO_ENDPOINT", "localhost:9000")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")

import asyncio
import uuid
from collections.abc import AsyncGenerator
from datetime import datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncConnection,
    AsyncSession,
    AsyncTransaction,
    async_sessionmaker,
    create_async_engine,
)

from core.config import get_settings
from core.models import (
    Base,
    EvaluationResultORM,
    MoleculeORM,
    MoleculeStatus,
    MutationType,
    TargetORM,
    UserORM,
)

settings = get_settings()


# ═════════════════════════════════════════════════════════════════════════════
# CONFIGURACIÓN GLOBAL DE PYTEST
# ═════════════════════════════════════════════════════════════════════════════

def pytest_configure(config: pytest.Config) -> None:
    """
    Registra markers custom para organizar los tests.
    Evita el warning "PytestUnknownMarkWarning" al correr la suite.
    """
    config.addinivalue_line("markers", "unit: tests unitarios sin DB ni servicios externos")
    config.addinivalue_line("markers", "integration: tests que usan DB real o servicios")
    config.addinivalue_line("markers", "slow: tests que tardan más de 5 segundos")
    config.addinivalue_line("markers", "docking: tests que invocan AutoDock Vina real")


# ═════════════════════════════════════════════════════════════════════════════
# EVENT LOOP
# ═════════════════════════════════════════════════════════════════════════════

@pytest.fixture(scope="session")
def event_loop_policy():
    """
    Usa el event loop por defecto de asyncio.
    pytest-asyncio necesita esta fixture para tests async con scope="session".
    """
    return asyncio.DefaultEventLoopPolicy()


# ═════════════════════════════════════════════════════════════════════════════
# BASE DE DATOS DE TEST
# ═════════════════════════════════════════════════════════════════════════════

@pytest_asyncio.fixture(scope="session")
async def test_engine():
    """
    Crea el engine de base de datos para tests.

    Usa una DB de test separada (moldesign_test) para no contaminar
    la DB de desarrollo. La DB de test se crea con las mismas tablas
    que la DB real via Base.metadata.create_all.

    También inyecta este engine en core.database via set_engine()
    para que todo código que use get_engine()/get_session_factory()
    (incluidos endpoints y workers) use la misma DB de test.

    scope="session": el engine se crea una vez y se reutiliza en todos
    los tests. Crear/destruir engines es caro.
    """
    from core.database import set_engine

    # Construir URL de la DB de test
    db_url = str(settings.database_url)
    if "moldesign_test" not in db_url:
        # Reemplaza el nombre de la DB por moldesign_test
        parts = db_url.rsplit("/", 1)
        test_db_url = f"{parts[0]}/moldesign_test"
    else:
        test_db_url = db_url

    engine = create_async_engine(
        test_db_url,
        echo=False,          # silencia SQL en tests para output más limpio
        pool_size=5,
        max_overflow=10,
    )

    # Inyecta el engine de test en core.database para que todo el backend
    # (endpoints, workers, repository) use la misma DB de test.
    set_engine(engine)

    # Crear todas las tablas
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    # Eliminar tablas al final de la sesión
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def db_session(test_engine) -> AsyncGenerator[AsyncSession, None]:
    """
    Proporciona una sesión de DB aislada para cada test.

    Usa el patrón de "nested transaction with savepoint":
    1. Abre una conexión y comienza una transacción externa
    2. Crea un SAVEPOINT (transacción anidada)
    3. El test recibe una sesión ligada al SAVEPOINT
    4. Al terminar el test, hace ROLLBACK al SAVEPOINT
    5. La transacción externa nunca se commitea

    Resultado: cada test ve la DB limpia independientemente de los
    datos insertados por los fixtures anteriores.

    Por qué SAVEPOINT y no solo rollback directo:
    SQLAlchemy async no permite nested transactions reales, pero sí
    SAVEPOINTs, que producen el mismo efecto de aislamiento.
    """
    async with test_engine.connect() as conn:
        await conn.begin()
        await conn.begin_nested()  # SAVEPOINT

        # Session factory ligada a esta conexión específica
        session_factory = async_sessionmaker(
            bind=conn,
            class_=AsyncSession,
            expire_on_commit=False,
            join_transaction_mode="create_savepoint",
        )

        async with session_factory() as session:
            yield session
            # El test terminó — rollback al SAVEPOINT
            await session.rollback()

        # Rollback de la transacción externa
        await conn.rollback()


@pytest_asyncio.fixture(scope="function")
async def db_with_data(db_session: AsyncSession) -> AsyncSession:
    """
    Sesión de DB con datos base ya insertados.

    Incluye un usuario, un target y dos moléculas de referencia.
    Úsala cuando el test necesita datos existentes sin tener que
    crearlos manualmente.
    """
    # Target 5-HT1A (PDB 7E2Y, Xu et al. 2021)
    target = TargetORM(
        id=uuid.UUID("00000000-0000-0000-0000-000000000001"),
        pdb_id="7E2Y",
        name="5-HT1A serotonin receptor",
        chain="R",
        grid_center_x=103.03,
        grid_center_y=114.79,
        grid_center_z=108.36,
        grid_size_x=25.0,
        grid_size_y=25.0,
        grid_size_z=25.0,
        is_prepared=True,
        prepared_file_path="targets/7E2Y/prepared.pdbqt",
    )
    db_session.add(target)

    # Usuario de prueba
    user = UserORM(
        id=uuid.UUID("00000000-0000-0000-0000-000000000002"),
        email="test@moldesign.dev",
        username="testuser",
        hashed_password="$2b$12$fakehash",  # no se usa en tests unitarios
        is_active=True,
    )
    db_session.add(user)
    await db_session.flush()  # persiste sin commit para que las FKs funcionen

    # Molécula aspirina (lead inicial)
    aspirin = MoleculeORM(
        id=uuid.UUID("00000000-0000-0000-0000-000000000010"),
        smiles="CC(=O)Oc1ccccc1C(=O)O",
        name="Aspirina",
        status=MoleculeStatus.EVALUATED,
        user_id=user.id,
        target_id=target.id,
        smiles_hash="a" * 64,   # hash ficticio para tests
    )
    db_session.add(aspirin)
    await db_session.flush()

    yield db_session


# ═════════════════════════════════════════════════════════════════════════════
# CLIENTE HTTP (FastAPI test client)
# ═════════════════════════════════════════════════════════════════════════════

@pytest_asyncio.fixture(scope="function")
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """
    Cliente HTTP async para hacer requests a la API de FastAPI en tests.

    Usa ASGITransport para llamar a la app directamente sin levantar
    un servidor HTTP real — los tests son más rápidos y no requieren
    un puerto disponible.

    La sesión de DB inyectada es la misma que usa el test, por lo que
    los datos insertados en el test son visibles en los endpoints.
    """
    from api.main import app
    from core.database import get_db

    # Sobreescribe la dependency de DB para usar la sesión de test
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers={"Content-Type": "application/json"},
    ) as ac:
        yield ac

    # Limpiar overrides para no afectar otros tests
    app.dependency_overrides.clear()


@pytest_asyncio.fixture(scope="function")
async def authenticated_client(
    client: AsyncClient,
    db_with_data: AsyncSession,
) -> AsyncClient:
    """
    Cliente HTTP con JWT de autenticación incluido en los headers.

    Úsalo para tests de endpoints que requieren autenticación.
    El token corresponde al usuario de prueba creado en db_with_data.
    """
    from api.auth import create_access_token   # se creará en api/main.py

    token = create_access_token(
        subject=str(uuid.UUID("00000000-0000-0000-0000-000000000002"))
    )
    client.headers["Authorization"] = f"Bearer {token}"
    return client


# ═════════════════════════════════════════════════════════════════════════════
# MOCKS DE SERVICIOS EXTERNOS
# ═════════════════════════════════════════════════════════════════════════════

@pytest.fixture(scope="function")
def mock_redis():
    """
    Mock de Redis para tests unitarios.

    Simula get/set/delete/exists con un dict en memoria.
    Los tests unitarios no deben depender de Redis real — son más
    rápidos y no requieren un servidor Redis corriendo.

    Uso:
        def test_something(mock_redis):
            # Redis está mockeado automáticamente
            # cache.get() retorna None por defecto
            # puedes configurar valores: mock_redis.get.return_value = "valor"
    """
    with patch("utils.cache.get_redis") as mock_get_redis:
        redis_mock = AsyncMock()

        # Comportamiento por defecto: cache vacío
        redis_mock.get.return_value = None
        redis_mock.set.return_value = True
        redis_mock.setex.return_value = True
        redis_mock.delete.return_value = 1
        redis_mock.exists.return_value = False
        redis_mock.incr.return_value = 1
        redis_mock.expire.return_value = True
        redis_mock.ping.return_value = True
        redis_mock.publish.return_value = 0
        redis_mock.info.return_value = {"redis_version": "7.0.0"}

        # Pipeline mock
        pipeline_mock = AsyncMock()
        pipeline_mock.__aenter__ = AsyncMock(return_value=pipeline_mock)
        pipeline_mock.__aexit__ = AsyncMock(return_value=None)
        pipeline_mock.execute.return_value = []
        redis_mock.pipeline.return_value = pipeline_mock

        mock_get_redis.return_value = redis_mock
        yield redis_mock


@pytest.fixture(scope="function")
def mock_minio():
    """
    Mock de MinIO para tests unitarios.

    Simula put_object/get_object/stat_object con respuestas predefinidas.
    Los tests unitarios no deben hacer I/O real a MinIO.

    Para tests de integración que necesiten MinIO real, no uses este fixture.
    """
    with patch("utils.file_handlers.get_minio_client") as mock_get_client:
        minio_mock = AsyncMock()

        # bucket_exists retorna True por defecto
        minio_mock.bucket_exists.return_value = True
        minio_mock.make_bucket.return_value = None

        # put_object retorna un objeto con etag
        put_result = MagicMock()
        put_result.etag = "fakeetag123"
        minio_mock.put_object.return_value = put_result

        # get_object retorna bytes vacíos por defecto
        # Para simular contenido real usa: mock_minio.get_object.return_value = ...
        response_mock = AsyncMock()
        response_mock.read.return_value = b""
        response_mock.close.return_value = None
        minio_mock.get_object.return_value = response_mock

        # stat_object lanza S3Error(NoSuchKey) por defecto (objeto no existe)
        from miniopy_async.error import S3Error
        minio_mock.stat_object.side_effect = S3Error(
            "NoSuchKey", "Object does not exist", "", "", "", ""
        )

        minio_mock.remove_object.return_value = None

        mock_get_client.return_value = minio_mock
        yield minio_mock


@pytest.fixture(scope="function")
def mock_vina():
    """
    Mock de AutoDock Vina para tests que no deben invocar el ejecutable real.

    Simula la ejecución de Vina retornando un SDF de poses con valores
    de afinidad conocidos. Útil para testear el pipeline completo
    (queue_handler → vina_service → scoring) sin esperar 30-90 segundos.

    Valores retornados:
        Pose 1: affinity=-8.5 kcal/mol (buena afinidad)
        Pose 2: affinity=-7.2 kcal/mol
        Pose 3: affinity=-6.8 kcal/mol
    """
    fake_sdf_output = """\

     RDKit          3D

  0  0  0  0  0  0  0  0  0  0999 V3000
M  END
> <minimizedAffinity>
-8.5

> <minimizedRMSD_lowerBound>
0.0

> <minimizedRMSD_upperBound>
0.0

$$$$

     RDKit          3D

  0  0  0  0  0  0  0  0  0  0999 V3000
M  END
> <minimizedAffinity>
-7.2

> <minimizedRMSD_lowerBound>
1.8

> <minimizedRMSD_upperBound>
3.4

$$$$

     RDKit          3D

  0  0  0  0  0  0  0  0  0  0999 V3000
M  END
> <minimizedAffinity>
-6.8

> <minimizedRMSD_lowerBound>
2.1

> <minimizedRMSD_upperBound>
4.2

$$$$
"""

    async def fake_run_vina(*args, **kwargs):
        return fake_sdf_output

    with patch(
        "services.docking.vina_service._run_vina_subprocess",
        side_effect=fake_run_vina,
    ):
        yield fake_sdf_output


@pytest.fixture(scope="function")
def mock_claude_api():
    """
    Mock de la API de Claude para tests del servicio de IA.

    Retorna un reporte narrativo de ejemplo sin hacer llamadas
    reales a Anthropic. Úsalo en tests de services/ai/interpreter.py.
    """
    fake_report = (
        "La molécula evaluada muestra una afinidad de unión prometedora "
        "con el receptor 5-HT1A (ΔG = -8.5 kcal/mol), sugiriendo una "
        "interacción estable con el sitio activo. Las propiedades "
        "fisicoquímicas cumplen los criterios de Lipinski, con un logP "
        "favorable de 2.3 que indica buena absorción oral potencial."
    )

    with patch("services.ai.interpreter.anthropic") as mock_anthropic:
        message_mock = MagicMock()
        message_mock.content = [MagicMock(text=fake_report)]

        client_mock = MagicMock()
        client_mock.messages.create = AsyncMock(return_value=message_mock)

        mock_anthropic.AsyncAnthropic.return_value = client_mock
        yield {"client": client_mock, "report": fake_report}


# ═════════════════════════════════════════════════════════════════════════════
# DATOS DE PRUEBA — moléculas de referencia
# ═════════════════════════════════════════════════════════════════════════════

@pytest.fixture(scope="session")
def aspirin_smiles() -> str:
    """
    SMILES de la aspirina (ácido acetilsalicílico).
    Molécula de referencia con propiedades bien documentadas.
    Cumple Lipinski: MW=180.16, logP=1.2, HBD=1, HBA=4.
    """
    return "CC(=O)Oc1ccccc1C(=O)O"


@pytest.fixture(scope="session")
def caffeine_smiles() -> str:
    """
    SMILES de la cafeína.
    Útil para testear moléculas con múltiples anillos y nitrógenos.
    Cumple Lipinski: MW=194.19, logP=-0.07, HBD=0, HBA=3.
    """
    return "CN1C=NC2=C1C(=O)N(C(=O)N2C)C"


@pytest.fixture(scope="session")
def invalid_smiles_cases() -> list[dict[str, str]]:
    """
    Colección de SMILES inválidos con la razón esperada de invalidez.
    Usados en tests de chem/validator.py para verificar que cada tipo
    de error es detectado correctamente.
    """
    return [
        {"smiles": "CCX",        "reason": "átomo desconocido"},
        {"smiles": "C1CC",       "reason": "anillo no cerrado"},
        {"smiles": "",           "reason": "string vacío"},
        {"smiles": "C(C)(C)(C)(C)C",  "reason": "valencia excedida en carbono sp3"},
        {"smiles": "c1ccccc",    "reason": "SMILES aromático incompleto"},
    ]


@pytest.fixture(scope="session")
def known_properties() -> dict[str, dict[str, Any]]:
    """
    Propiedades fisicoquímicas conocidas para moléculas de referencia.

    Valores obtenidos de PubChem y literatura farmacológica.
    Usados para verificar que chem/properties.py calcula correctamente.

    Los valores de RDKit pueden diferir ligeramente de otras fuentes
    debido a diferencias en los algoritmos de cálculo — las tolerancias
    en los tests deben ser ±0.1 para MW y ±0.2 para logP.
    """
    return {
        "CC(=O)Oc1ccccc1C(=O)O": {   # aspirina
            "molecular_weight": 180.16,
            "log_p": 1.19,
            "tpsa": 63.6,
            "hbd": 1,
            "hba": 4,
            "rotatable_bonds": 3,
            "heavy_atom_count": 13,
            "ring_count": 1,
            "qed": 0.55,
            "lipinski_pass": True,
            "veber_pass": True,
        },
        "CN1C=NC2=C1C(=O)N(C(=O)N2C)C": {   # cafeína
            "molecular_weight": 194.19,
            "log_p": -0.07,
            "tpsa": 58.4,
            "hbd": 0,
            "hba": 3,
            "rotatable_bonds": 0,
            "heavy_atom_count": 14,
            "ring_count": 2,
            "qed": 0.49,
            "lipinski_pass": True,
            "veber_pass": True,
        },
    }


@pytest.fixture(scope="session")
def target_data() -> dict[str, Any]:
    """
    Datos del target 5-HT1A para usar en tests sin DB.
    Los valores del grid box corresponden al PDB 7E2Y cadena R.
    Xu et al., Nature 592:469-473 (2021).
    """
    return {
        "pdb_id": "7E2Y",
        "name": "5-HT1A serotonin receptor",
        "chain": "R",
        "grid_center_x": 103.03,
        "grid_center_y": 114.79,
        "grid_center_z": 108.36,
        "grid_size_x": 25.0,
        "grid_size_y": 25.0,
        "grid_size_z": 25.0,
    }


@pytest.fixture(scope="function")
def sample_docking_result() -> dict[str, Any]:
    """
    Resultado de docking de ejemplo con valores realistas.
    Usado para testear scoring/engine.py sin correr Vina real.
    """
    return {
        "best_affinity": -8.5,
        "poses": [
            {"rank": 1, "affinity": -8.5, "rmsd_lb": 0.0, "rmsd_ub": 0.0},
            {"rank": 2, "affinity": -7.2, "rmsd_lb": 1.8, "rmsd_ub": 3.4},
            {"rank": 3, "affinity": -6.8, "rmsd_lb": 2.1, "rmsd_ub": 4.2},
        ],
        "poses_file_path": "poses/aaaa.../7E2Y/poses.sdf",
    }


@pytest.fixture(scope="function")
def sample_properties() -> dict[str, Any]:
    """
    Propiedades fisicoquímicas de ejemplo (basadas en aspirina).
    Usado para testear scoring/normalizer.py y scoring/engine.py.
    """
    return {
        "molecular_weight": 180.16,
        "log_p": 1.19,
        "tpsa": 63.6,
        "hbd": 1,
        "hba": 4,
        "rotatable_bonds": 3,
        "heavy_atom_count": 13,
        "ring_count": 1,
        "qed": 0.55,
        "lipinski_pass": True,
        "veber_pass": True,
    }
