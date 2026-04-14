"""
tests/integration/test_history_endpoints.py

Tests de integración HTTP para el router de historial.

Requieren: PostgreSQL (moldesign_test DB activa).

Cobertura:
- GET /history/evaluations: paginación, filtros, ordenamiento, aislamiento entre usuarios
- GET /history/stats: estadísticas correctas, sin datos
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import create_access_token
from api.routers.auth import _hash_password
from core.models import (
    EvaluationResultORM,
    MoleculeORM,
    MoleculeStatus,
    TargetORM,
    UserORM,
)


# ═══════════════════════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

async def _create_user_and_token(db: AsyncSession, email: str = "histuser@example.com"):
    user = UserORM(
        email=email,
        username=email.split("@")[0],
        hashed_password=_hash_password("password123"),
        is_active=True,
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)
    token = create_access_token(subject=str(user.id))
    return user, token


async def _create_target(db: AsyncSession):
    target = TargetORM(
        pdb_id="7E2Y",
        name="5-HT1A serotonin receptor",
        chain="R",
        grid_center_x=103.03, grid_center_y=114.79, grid_center_z=108.36,
        grid_size_x=25.0, grid_size_y=25.0, grid_size_z=25.0,
        is_prepared=True,
    )
    db.add(target)
    await db.flush()
    await db.refresh(target)
    return target


async def _create_molecule(db, user, target, smiles="CCO", name="Etanol",
                           status=MoleculeStatus.EVALUATED, smiles_hash=None):
    mol = MoleculeORM(
        smiles=smiles, name=name, status=status,
        user_id=user.id, target_id=target.id,
        smiles_hash=smiles_hash or ("a" * 64),
    )
    db.add(mol)
    await db.flush()
    await db.refresh(mol)
    return mol


async def _create_evaluation(db, molecule, affinity_kcal=-8.5, total_score=72.3):
    ev = EvaluationResultORM(
        molecule_id=molecule.id,
        affinity_kcal=affinity_kcal, affinity_score=65.0,
        adme_score=80.0, druglikeness_score=75.0,
        total_score=total_score,
        molecular_weight=180.16, log_p=1.19,
        lipinski_pass=True, qed=0.55,
    )
    db.add(ev)
    await db.flush()
    return ev


# ═══════════════════════════════════════════════════════════════════════════════
# GET /history/evaluations
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.integration
class TestListEvaluations:

    @pytest.mark.asyncio
    async def test_requires_auth(self, client: AsyncClient):
        resp = await client.get("/history/evaluations")
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_empty(self, client: AsyncClient, db_session: AsyncSession):
        user, token = await _create_user_and_token(db_session)

        resp = await client.get(
            "/history/evaluations",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["items"] == []
        assert data["total"] == 0
        assert data["has_next"] is False

    @pytest.mark.asyncio
    async def test_with_data(self, client: AsyncClient, db_session: AsyncSession):
        user, token = await _create_user_and_token(db_session)
        target = await _create_target(db_session)
        mol = await _create_molecule(db_session, user, target)
        await _create_evaluation(db_session, mol)

        resp = await client.get(
            "/history/evaluations",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["items"][0]["total_score"] == pytest.approx(72.3, abs=0.1)

    @pytest.mark.asyncio
    async def test_pagination(self, client: AsyncClient, db_session: AsyncSession):
        user, token = await _create_user_and_token(db_session)
        target = await _create_target(db_session)
        for i in range(3):
            mol = await _create_molecule(
                db_session, user, target,
                smiles=f"C{'C' * i}O", name=f"Mol{i}",
                smiles_hash=f"{i:064d}",
            )
            await _create_evaluation(db_session, mol, total_score=50.0 + i)

        resp = await client.get(
            "/history/evaluations?page=1&page_size=2",
            headers={"Authorization": f"Bearer {token}"},
        )
        data = resp.json()
        assert data["total"] == 3
        assert len(data["items"]) == 2
        assert data["has_next"] is True

    @pytest.mark.asyncio
    async def test_filter_by_status(self, client: AsyncClient, db_session: AsyncSession):
        user, token = await _create_user_and_token(db_session)
        target = await _create_target(db_session)
        mol_ok = await _create_molecule(db_session, user, target, smiles_hash="b" * 64)
        await _create_evaluation(db_session, mol_ok)
        await _create_molecule(
            db_session, user, target, smiles="CC", name="Etano",
            status=MoleculeStatus.FAILED, smiles_hash="c" * 64,
        )

        resp = await client.get(
            "/history/evaluations?status=evaluated",
            headers={"Authorization": f"Bearer {token}"},
        )
        data = resp.json()
        assert data["total"] == 1

    @pytest.mark.asyncio
    async def test_isolation_between_users(self, client: AsyncClient, db_session: AsyncSession):
        user1, token1 = await _create_user_and_token(db_session, email="user1@ex.com")
        user2, _ = await _create_user_and_token(db_session, email="user2@ex.com")
        target = await _create_target(db_session)
        await _create_molecule(db_session, user1, target, name="U1Mol", smiles_hash="f" * 64)
        await _create_molecule(db_session, user2, target, name="U2Mol", smiles_hash="0" * 64)

        resp = await client.get(
            "/history/evaluations",
            headers={"Authorization": f"Bearer {token1}"},
        )
        assert resp.json()["total"] == 1
        assert resp.json()["items"][0]["name"] == "U1Mol"


# ═══════════════════════════════════════════════════════════════════════════════
# GET /history/stats
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.integration
class TestStats:

    @pytest.mark.asyncio
    async def test_requires_auth(self, client: AsyncClient):
        resp = await client.get("/history/stats")
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_empty_stats(self, client: AsyncClient, db_session: AsyncSession):
        user, token = await _create_user_and_token(db_session)

        resp = await client.get(
            "/history/stats",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_evaluations"] == 0
        assert data["best_score"] is None

    @pytest.mark.asyncio
    async def test_stats_with_data(self, client: AsyncClient, db_session: AsyncSession):
        user, token = await _create_user_and_token(db_session)
        target = await _create_target(db_session)

        mol1 = await _create_molecule(db_session, user, target, smiles_hash="1" * 64)
        await _create_evaluation(db_session, mol1, total_score=60.0)

        mol2 = await _create_molecule(db_session, user, target, smiles="CCCO", smiles_hash="2" * 64)
        await _create_evaluation(db_session, mol2, total_score=80.0)

        await _create_molecule(
            db_session, user, target, smiles="CC",
            status=MoleculeStatus.FAILED, smiles_hash="3" * 64,
        )

        resp = await client.get(
            "/history/stats",
            headers={"Authorization": f"Bearer {token}"},
        )
        data = resp.json()
        assert data["total_evaluations"] == 3
        assert data["completed_evaluations"] == 2
        assert data["failed_evaluations"] == 1
        assert data["best_score"] == pytest.approx(80.0, abs=0.1)
        assert data["avg_score"] == pytest.approx(70.0, abs=0.1)
        assert data["unique_targets"] == 1
