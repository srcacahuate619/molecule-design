"""
tests/unit/test_auth_router.py

Tests unitarios de los helpers de autenticación (api/routers/auth.py).

Cobertura:
- _hash_password: formato, sal aleatoria
- _verify_password: verificación correcta, incorrecta, hash malformado

Los tests HTTP del router están en tests/integration/test_auth_endpoints.py
porque requieren DB (savepoint isolation via `client` fixture).
"""

from __future__ import annotations

import pytest

from api.routers.auth import _hash_password, _verify_password


# ═══════════════════════════════════════════════════════════════════════════════
# HELPERS DE HASHING
# ═══════════════════════════════════════════════════════════════════════════════

class TestPasswordHashing:
    """Tests del mecanismo de hashing de passwords."""

    def test_hash_password_returns_salt_colon_hash(self):
        """El formato del hash es 'salt_hex:hash_hex'."""
        hashed = _hash_password("mypassword")
        parts = hashed.split(":")
        assert len(parts) == 2
        # salt = 32 bytes = 64 hex chars
        assert len(parts[0]) == 64
        # SHA-256 hash = 32 bytes = 64 hex chars
        assert len(parts[1]) == 64

    def test_hash_password_different_salts(self):
        """Dos invocaciones para el mismo password producen hashes distintos."""
        h1 = _hash_password("mypassword")
        h2 = _hash_password("mypassword")
        assert h1 != h2

    def test_verify_password_correct(self):
        """_verify_password retorna True para el password correcto."""
        hashed = _hash_password("correcthorse")
        assert _verify_password("correcthorse", hashed) is True

    def test_verify_password_incorrect(self):
        """_verify_password retorna False para un password incorrecto."""
        hashed = _hash_password("correcthorse")
        assert _verify_password("wrongpassword", hashed) is False

    def test_verify_password_malformed_hash(self):
        """_verify_password retorna False para un hash malformado (sin colon)."""
        assert _verify_password("mypassword", "nocolon") is False

    def test_verify_password_invalid_hex(self):
        """_verify_password retorna False para hex inválido."""
        assert _verify_password("mypassword", "gg:hh") is False
