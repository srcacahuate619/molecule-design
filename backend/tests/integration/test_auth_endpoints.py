"""
tests/integration/test_auth_endpoints.py

Tests de integración HTTP para el router de autenticación.

Requieren: PostgreSQL (moldesign_test DB activa).

Cobertura:
- POST /auth/register: registro exitoso, duplicados, validación
- POST /auth/login: login exitoso, errores de credenciales, usuario inactivo
- GET /auth/me: con/sin token, token inválido, usuario inactivo
"""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import create_access_token
from api.routers.auth import _hash_password
from core.models import UserORM


# ═══════════════════════════════════════════════════════════════════════════════
# POST /auth/register
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.integration
class TestRegister:
    """Tests HTTP del endpoint de registro."""

    @pytest.mark.asyncio
    async def test_register_success(self, client: AsyncClient):
        resp = await client.post("/auth/register", json={
            "email": "newuser@example.com",
            "username": "newuser",
            "password": "securepassword123",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert data["username"] == "newuser"
        assert data["email"] == "newuser@example.com"
        assert data["user_id"]

    @pytest.mark.asyncio
    async def test_register_duplicate_email(self, client: AsyncClient, db_session: AsyncSession):
        user = UserORM(
            email="existing@example.com",
            username="existinguser",
            hashed_password=_hash_password("password123"),
            is_active=True,
        )
        db_session.add(user)
        await db_session.flush()

        resp = await client.post("/auth/register", json={
            "email": "existing@example.com",
            "username": "differentuser",
            "password": "securepassword123",
        })
        assert resp.status_code == 409

    @pytest.mark.asyncio
    async def test_register_duplicate_username(self, client: AsyncClient, db_session: AsyncSession):
        user = UserORM(
            email="first@example.com",
            username="takenname",
            hashed_password=_hash_password("password123"),
            is_active=True,
        )
        db_session.add(user)
        await db_session.flush()

        resp = await client.post("/auth/register", json={
            "email": "different@example.com",
            "username": "takenname",
            "password": "securepassword123",
        })
        assert resp.status_code == 409

    @pytest.mark.asyncio
    async def test_register_short_password(self, client: AsyncClient):
        resp = await client.post("/auth/register", json={
            "email": "user@example.com",
            "username": "validuser",
            "password": "short",
        })
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_register_invalid_email(self, client: AsyncClient):
        resp = await client.post("/auth/register", json={
            "email": "notanemail",
            "username": "validuser",
            "password": "securepassword123",
        })
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_register_short_username(self, client: AsyncClient):
        resp = await client.post("/auth/register", json={
            "email": "user@example.com",
            "username": "ab",
            "password": "securepassword123",
        })
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_register_invalid_username_chars(self, client: AsyncClient):
        resp = await client.post("/auth/register", json={
            "email": "user@example.com",
            "username": "user name!",
            "password": "securepassword123",
        })
        assert resp.status_code == 422


# ═══════════════════════════════════════════════════════════════════════════════
# POST /auth/login
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.integration
class TestLogin:
    """Tests HTTP del endpoint de login."""

    @pytest.mark.asyncio
    async def test_login_success(self, client: AsyncClient, db_session: AsyncSession):
        password = "mypassword123"
        user = UserORM(
            email="loginuser@example.com",
            username="loginuser",
            hashed_password=_hash_password(password),
            is_active=True,
        )
        db_session.add(user)
        await db_session.flush()

        resp = await client.post("/auth/login", json={
            "email": "loginuser@example.com",
            "password": password,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert data["username"] == "loginuser"

    @pytest.mark.asyncio
    async def test_login_wrong_password(self, client: AsyncClient, db_session: AsyncSession):
        user = UserORM(
            email="wrongpwd@example.com",
            username="wrongpwd",
            hashed_password=_hash_password("realpassword"),
            is_active=True,
        )
        db_session.add(user)
        await db_session.flush()

        resp = await client.post("/auth/login", json={
            "email": "wrongpwd@example.com",
            "password": "wrongpassword",
        })
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_login_nonexistent_email(self, client: AsyncClient):
        resp = await client.post("/auth/login", json={
            "email": "nobody@example.com",
            "password": "anypassword",
        })
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_login_inactive_user(self, client: AsyncClient, db_session: AsyncSession):
        password = "mypassword123"
        user = UserORM(
            email="inactive@example.com",
            username="inactiveuser",
            hashed_password=_hash_password(password),
            is_active=False,
        )
        db_session.add(user)
        await db_session.flush()

        resp = await client.post("/auth/login", json={
            "email": "inactive@example.com",
            "password": password,
        })
        assert resp.status_code == 403


# ═══════════════════════════════════════════════════════════════════════════════
# GET /auth/me
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.integration
class TestGetMe:
    """Tests HTTP del endpoint de perfil."""

    @pytest.mark.asyncio
    async def test_get_me_authenticated(self, client: AsyncClient, db_session: AsyncSession):
        user = UserORM(
            email="profile@example.com",
            username="profileuser",
            hashed_password=_hash_password("password123"),
            is_active=True,
        )
        db_session.add(user)
        await db_session.flush()
        await db_session.refresh(user)

        token = create_access_token(subject=str(user.id))
        resp = await client.get(
            "/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["username"] == "profileuser"
        assert data["email"] == "profile@example.com"
        assert data["is_active"] is True

    @pytest.mark.asyncio
    async def test_get_me_no_token(self, client: AsyncClient):
        resp = await client.get("/auth/me")
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_get_me_invalid_token(self, client: AsyncClient):
        resp = await client.get(
            "/auth/me",
            headers={"Authorization": "Bearer invalid.token.here"},
        )
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_get_me_inactive_user(self, client: AsyncClient, db_session: AsyncSession):
        user = UserORM(
            email="deactivated@example.com",
            username="deactivated",
            hashed_password=_hash_password("password123"),
            is_active=False,
        )
        db_session.add(user)
        await db_session.flush()
        await db_session.refresh(user)

        token = create_access_token(subject=str(user.id))
        resp = await client.get(
            "/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        # API returns 401 (not 403) for inactive users — security best practice:
        # don't leak whether user exists but is deactivated vs. not found.
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_get_me_nonexistent_user(self, client: AsyncClient):
        fake_user_id = str(uuid.uuid4())
        token = create_access_token(subject=fake_user_id)
        resp = await client.get(
            "/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 401
