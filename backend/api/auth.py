"""
api/auth.py

Utilidades mínimas de autenticación para el MVP.

En esta fase inicial necesitamos dos cosas:
1. Poder crear un access token para tests y futuros endpoints.
2. Poder validarlo sin depender de librerías externas adicionales.

Implementamos un JWT HS256 mínimo usando solo stdlib para mantener
el backend autocontenido. No pretende reemplazar una capa completa
de autenticación, pero sí proporciona una base correcta y verificable
para el MVP.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
from datetime import UTC, datetime, timedelta
from typing import Any

from core.config import get_settings
from core.exceptions import AuthError, InvalidCredentials, TokenExpired

settings = get_settings()


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode((data + padding).encode("ascii"))


def _json_dumps(payload: dict[str, Any]) -> str:
    return json.dumps(payload, separators=(",", ":"), sort_keys=True)


def _sign(message: bytes) -> str:
    digest = hmac.new(
        settings.secret_key.encode("utf-8"),
        message,
        hashlib.sha256,
    ).digest()
    return _b64url_encode(digest)


def create_access_token(
    subject: str,
    expires_delta: timedelta | None = None,
    additional_claims: dict[str, Any] | None = None,
) -> str:
    """
    Crea un JWT HS256 mínimo para el MVP.

    Args:
        subject: identificador principal del usuario (normalmente user_id)
        expires_delta: override opcional del tiempo de expiración
        additional_claims: claims adicionales si se requieren más adelante
    """
    now = datetime.now(UTC)
    expires = now + (
        expires_delta or timedelta(minutes=settings.jwt_access_token_expire_minutes)
    )

    header = {
        "alg": settings.jwt_algorithm,
        "typ": "JWT",
    }
    payload: dict[str, Any] = {
        "sub": subject,
        "iat": int(now.timestamp()),
        "exp": int(expires.timestamp()),
        "type": "access",
    }

    if additional_claims:
        payload.update(additional_claims)

    encoded_header = _b64url_encode(_json_dumps(header).encode("utf-8"))
    encoded_payload = _b64url_encode(_json_dumps(payload).encode("utf-8"))
    signing_input = f"{encoded_header}.{encoded_payload}".encode("utf-8")
    signature = _sign(signing_input)
    return f"{encoded_header}.{encoded_payload}.{signature}"


def create_refresh_token(
    subject: str,
    expires_delta: timedelta | None = None,
) -> str:
    """
    Crea un JWT de refresco de larga duración.
    """
    now = datetime.now(UTC)
    expires = now + (
        expires_delta or timedelta(days=settings.jwt_refresh_token_expire_days)
    )

    header = {
        "alg": settings.jwt_algorithm,
        "typ": "JWT",
    }
    payload: dict[str, Any] = {
        "sub": subject,
        "iat": int(now.timestamp()),
        "exp": int(expires.timestamp()),
        "type": "refresh",
    }

    encoded_header = _b64url_encode(_json_dumps(header).encode("utf-8"))
    encoded_payload = _b64url_encode(_json_dumps(payload).encode("utf-8"))
    signing_input = f"{encoded_header}.{encoded_payload}".encode("utf-8")
    signature = _sign(signing_input)
    return f"{encoded_header}.{encoded_payload}.{signature}"


def decode_token(token: str) -> dict[str, Any]:
    """
    Valida firma y expiración del token.

    Lanza:
        InvalidCredentials si el token es inválido
        TokenExpired si expiró
    """
    try:
        encoded_header, encoded_payload, provided_signature = token.split(".", 2)
    except ValueError as exc:
        raise InvalidCredentials() from exc

    signing_input = f"{encoded_header}.{encoded_payload}".encode("utf-8")
    expected_signature = _sign(signing_input)

    if not hmac.compare_digest(provided_signature, expected_signature):
        raise InvalidCredentials()

    try:
        payload = json.loads(_b64url_decode(encoded_payload).decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError, ValueError) as exc:
        raise InvalidCredentials() from exc

    exp = payload.get("exp")
    if not isinstance(exp, int):
        raise InvalidCredentials()

    now_ts = int(datetime.now(UTC).timestamp())
    if exp < now_ts:
        raise TokenExpired()

    return payload


def get_subject_from_token(token: str) -> str:
    payload = decode_token(token)
    # Para endpoints generales, solo permitimos tokens de tipo 'access'
    if payload.get("type") != "access":
        raise AuthError(
            message="Token de acceso requerido",
            detail="Se proporcionó un token de un tipo diferente",
        )
    subject = payload.get("sub")
    if not isinstance(subject, str) or not subject:
        raise InvalidCredentials()
    return subject
