"""
api/dependencies.py

Dependencias compartidas de FastAPI para autenticación y autorización.

Provee:
- get_current_user: extrae y valida el JWT del header Authorization
- get_current_user_optional: permite requests anónimos (devuelve None)

Estas dependencias se inyectan en los endpoints que requieren autenticación.
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import get_subject_from_token
from core.database import get_db
from core.exceptions import InvalidCredentials, TokenExpired
from core.models import UserORM
from utils.logger import get_logger

log = get_logger(__name__)


def _extract_token(authorization: str | None) -> str:
    """Extrae el token Bearer del header Authorization."""
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Header Authorization requerido",
            headers={"WWW-Authenticate": "Bearer"},
        )
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Formato de token inválido. Usa: Bearer <token>",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return parts[1]


async def get_current_user(
    authorization: Annotated[str | None, Header()] = None,
    db: AsyncSession = Depends(get_db),
) -> UserORM:
    """
    Dependencia que autentica al usuario y lo devuelve.
    Lanza 401 si el token es inválido o el usuario no existe.
    """
    token = _extract_token(authorization)

    try:
        subject = get_subject_from_token(token)
    except (InvalidCredentials, TokenExpired) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=exc.message,
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    try:
        user_id = uuid.UUID(subject)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido: subject no es un UUID válido",
        ) from exc

    stmt = select(UserORM).where(UserORM.id == user_id)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario no encontrado o desactivado",
        )

    return user


async def get_current_user_optional(
    authorization: Annotated[str | None, Header()] = None,
    db: AsyncSession = Depends(get_db),
) -> UserORM | None:
    """
    Como get_current_user pero permite requests anónimos.
    Si no hay token, devuelve None en vez de lanzar error.
    Útil para endpoints que funcionan con o sin autenticación.
    """
    if not authorization:
        return None

    try:
        return await get_current_user(authorization=authorization, db=db)
    except HTTPException:
        return None
