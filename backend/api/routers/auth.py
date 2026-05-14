"""
api/routers/auth.py

Endpoints de autenticación: registro e inicio de sesión.

Este módulo NO implementa lógica científica — es puramente una capa
de gestión de identidad necesaria para:
- asociar evaluaciones a usuarios reales,
- mantener historial por usuario,
- permitir multi-usuario seguro.

Seguridad implementada:
- Passwords hasheados con SHA-256 + salt (stdlib, sin bcrypt para minimizar deps)
- JWT HS256 con expiración configurable
- No se revela si un email existe o no en login
- Rate limiting debe agregarse en producción
"""

from __future__ import annotations

import hashlib
import os
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import create_access_token, create_refresh_token, decode_token
from api.dependencies import get_current_user
from api.rate_limiter import login_limiter, register_limiter
from core.config import get_settings
from core.database import get_db
from core.models import UserORM
from utils.logger import get_logger

log = get_logger(__name__)

router = APIRouter(prefix="/auth", tags=["Autenticación"])


# ── Helpers de hashing ────────────────────────────────────────────────────────

def _hash_password(password: str) -> str:
    """
    Hash de password con SHA-256 + salt aleatorio.

    Nota: En producción, considerar bcrypt o argon2.
    Para el MVP, SHA-256 + salt es suficiente y no añade dependencias.
    """
    salt = os.urandom(32)
    pwd_hash = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        iterations=100_000,
    )
    return salt.hex() + ":" + pwd_hash.hex()


def _verify_password(password: str, stored_hash: str) -> bool:
    """Verifica un password contra su hash almacenado."""
    try:
        salt_hex, hash_hex = stored_hash.split(":", 1)
        salt = bytes.fromhex(salt_hex)
        expected_hash = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt,
            iterations=100_000,
        )
        return expected_hash.hex() == hash_hex
    except (ValueError, AttributeError):
        return False


# ── Request/Response schemas ──────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    email: EmailStr
    username: str = Field(..., min_length=3, max_length=50, pattern=r"^[a-zA-Z0-9_-]+$")
    password: str = Field(..., min_length=8, max_length=128)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=1, max_length=128)


class AuthResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user_id: str
    username: str
    email: str


class RefreshRequest(BaseModel):
    refresh_token: str


class UserProfile(BaseModel):
    user_id: str
    username: str
    email: str
    is_active: bool
    created_at: str


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post(
    "/register",
    response_model=AuthResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Registrar nuevo usuario",
)
async def register(
    request: RegisterRequest,
    raw_request: Request,
    db: AsyncSession = Depends(get_db),
) -> AuthResponse:
    """Crea un nuevo usuario y devuelve un access token."""

    # Rate limiting: 3 registros/min por IP
    register_limiter.check(raw_request)

    # Verificar email duplicado
    stmt = select(UserORM).where(UserORM.email == request.email)
    result = await db.execute(stmt)
    if result.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ya existe una cuenta con ese email",
        )

    # Verificar username duplicado
    stmt = select(UserORM).where(UserORM.username == request.username)
    result = await db.execute(stmt)
    if result.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ese nombre de usuario ya está en uso",
        )

    # Crear usuario
    user = UserORM(
        email=request.email,
        username=request.username,
        hashed_password=_hash_password(request.password),
        is_active=True,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    log.info("usuario registrado", user_id=str(user.id), username=user.username)

    # Generar tokens
    settings = get_settings()
    access_token = create_access_token(
        subject=str(user.id),
        expires_delta=timedelta(minutes=settings.jwt_access_token_expire_minutes),
    )
    refresh_token = create_refresh_token(subject=str(user.id))

    return AuthResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user_id=str(user.id),
        username=user.username,
        email=user.email,
    )


@router.post(
    "/login",
    response_model=AuthResponse,
    summary="Iniciar sesión",
)
async def login(
    request: LoginRequest,
    raw_request: Request,
    db: AsyncSession = Depends(get_db),
) -> AuthResponse:
    """Autentica al usuario y devuelve un access token."""

    # Rate limiting: 5 intentos/min por IP
    login_limiter.check(raw_request)

    stmt = select(UserORM).where(UserORM.email == request.email)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    # Mensaje genérico para evitar user enumeration
    if user is None or not _verify_password(request.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email o contraseña incorrectos",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cuenta desactivada",
        )

    settings = get_settings()
    access_token = create_access_token(
        subject=str(user.id),
        expires_delta=timedelta(minutes=settings.jwt_access_token_expire_minutes),
    )
    refresh_token = create_refresh_token(subject=str(user.id))

    log.info("usuario autenticado", user_id=str(user.id), username=user.username)

    return AuthResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user_id=str(user.id),
        username=user.username,
        email=user.email,
    )


@router.post(
    "/refresh",
    response_model=AuthResponse,
    summary="Refrescar access token",
)
async def refresh(
    request: RefreshRequest,
    db: AsyncSession = Depends(get_db),
) -> AuthResponse:
    """Valida un refresh token y devuelve un nuevo access token."""
    try:
        payload = decode_token(request.refresh_token)
        if payload.get("type") != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token de refresco inválido",
            )
        subject = payload.get("sub")
        if not subject:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token de refresco inválido",
            )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token de refresco inválido o expirado",
        )

    # Verificar que el usuario existe y está activo
    try:
        user_id = uuid.UUID(subject)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token de refresco inválido",
        )

    stmt = select(UserORM).where(UserORM.id == user_id)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario no encontrado o desactivado",
        )

    settings = get_settings()
    access_token = create_access_token(
        subject=str(user.id),
        expires_delta=timedelta(minutes=settings.jwt_access_token_expire_minutes),
    )
    # También rotamos el refresh token para mayor seguridad
    new_refresh_token = create_refresh_token(subject=str(user.id))

    return AuthResponse(
        access_token=access_token,
        refresh_token=new_refresh_token,
        user_id=str(user.id),
        username=user.username,
        email=user.email,
    )


@router.get(
    "/me",
    response_model=UserProfile,
    summary="Perfil del usuario autenticado",
)
async def get_me(
    current_user: UserORM = Depends(get_current_user),
) -> UserProfile:
    """Devuelve el perfil del usuario autenticado."""
    return UserProfile(
        user_id=str(current_user.id),
        username=current_user.username,
        email=current_user.email,
        is_active=current_user.is_active,
        created_at=current_user.created_at.isoformat() if current_user.created_at else "",
    )
