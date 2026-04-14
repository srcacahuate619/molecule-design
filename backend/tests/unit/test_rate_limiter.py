"""
tests/unit/test_rate_limiter.py

Tests unitarios del rate limiter (api/rate_limiter.py).

Cobertura:
- Token bucket: consume tokens, refill proporcional al tiempo
- Bloqueo tras exceder límite
- Reset manual
- Extracción de IP (client, X-Forwarded-For)
- Cleanup de entradas expiradas
"""

from __future__ import annotations

import time
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from api.rate_limiter import RateLimiter


# ═══════════════════════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

def _make_request(ip: str = "127.0.0.1", forwarded_for: str | None = None) -> MagicMock:
    """Crea un mock de FastAPI Request con IP configurable."""
    req = MagicMock()
    req.client.host = ip
    headers = {}
    if forwarded_for:
        headers["X-Forwarded-For"] = forwarded_for
    req.headers = headers
    return req


# ═══════════════════════════════════════════════════════════════════════════════
# TOKEN BUCKET BÁSICO
# ═══════════════════════════════════════════════════════════════════════════════

class TestRateLimiterBasic:
    """Tests del comportamiento básico del rate limiter."""

    def test_allows_requests_within_limit(self):
        """Permite hasta max_requests en la ventana."""
        limiter = RateLimiter(max_requests=3, window_seconds=60, block_seconds=60)
        req = _make_request()

        # 3 requests deberían pasar
        for _ in range(3):
            limiter.check(req)  # No debe lanzar excepción

    def test_blocks_after_exceeding_limit(self):
        """Bloquea después de exceder max_requests."""
        limiter = RateLimiter(max_requests=2, window_seconds=60, block_seconds=60)
        req = _make_request()

        limiter.check(req)  # OK (1 de 2)
        limiter.check(req)  # OK (2 de 2)

        with pytest.raises(HTTPException) as exc_info:
            limiter.check(req)  # Excede límite

        assert exc_info.value.status_code == 429
        assert "Retry-After" in exc_info.value.headers

    def test_different_ips_independent(self):
        """IPs distintas tienen buckets independientes."""
        limiter = RateLimiter(max_requests=1, window_seconds=60, block_seconds=60)

        req_a = _make_request("10.0.0.1")
        req_b = _make_request("10.0.0.2")

        limiter.check(req_a)  # OK

        with pytest.raises(HTTPException):
            limiter.check(req_a)  # Bloqueada

        limiter.check(req_b)  # OK — IP distinta

    def test_tokens_refill_over_time(self):
        """Los tokens se recargan proporcionalmente al tiempo."""
        limiter = RateLimiter(max_requests=2, window_seconds=10, block_seconds=60)
        req = _make_request()

        # Consume ambos tokens
        limiter.check(req)
        limiter.check(req)

        # Simular paso de tiempo suficiente para recargar 1 token
        # Avanzar 5 segundos = 50% de la ventana = 1 token
        with patch("api.rate_limiter.time") as mock_time:
            # El primer check fue ~ahora, simular 6 segundos después
            now = time.monotonic()
            mock_time.monotonic.return_value = now + 6
            # Reajustar el last_refill del bucket
            entry = limiter._buckets["127.0.0.1"]
            entry.last_refill = now - 6

            limiter.check(req)  # Debería pasar — tokens recargados

    def test_block_duration(self):
        """El bloqueo dura block_seconds."""
        limiter = RateLimiter(max_requests=1, window_seconds=60, block_seconds=120)
        req = _make_request()

        limiter.check(req)

        with pytest.raises(HTTPException) as exc_info:
            limiter.check(req)

        assert "120" in exc_info.value.detail


# ═══════════════════════════════════════════════════════════════════════════════
# IP EXTRACTION
# ═══════════════════════════════════════════════════════════════════════════════

class TestIPExtraction:
    """Tests de extracción de IP del request."""

    def test_uses_client_host(self):
        """Usa request.client.host sin proxy."""
        limiter = RateLimiter(max_requests=10, window_seconds=60, block_seconds=60)
        req = _make_request("192.168.1.100")
        ip = limiter._get_client_ip(req)
        assert ip == "192.168.1.100"

    def test_uses_x_forwarded_for(self):
        """Usa X-Forwarded-For si está presente (primer IP)."""
        limiter = RateLimiter(max_requests=10, window_seconds=60, block_seconds=60)
        req = _make_request("10.0.0.1", forwarded_for="203.0.113.50, 70.41.3.18")
        ip = limiter._get_client_ip(req)
        assert ip == "203.0.113.50"

    def test_handles_no_client(self):
        """Si no hay client info, usa 'unknown'."""
        limiter = RateLimiter(max_requests=10, window_seconds=60, block_seconds=60)
        req = MagicMock()
        req.client = None
        req.headers = {}
        ip = limiter._get_client_ip(req)
        assert ip == "unknown"


# ═══════════════════════════════════════════════════════════════════════════════
# RESET
# ═══════════════════════════════════════════════════════════════════════════════

class TestReset:
    """Tests del mecanismo de reset."""

    def test_reset_all(self):
        """Reset sin IP limpia todos los buckets."""
        limiter = RateLimiter(max_requests=1, window_seconds=60, block_seconds=60)
        limiter.check(_make_request("1.1.1.1"))
        limiter.check(_make_request("2.2.2.2"))

        limiter.reset()

        # Debería poder hacer requests de nuevo
        limiter.check(_make_request("1.1.1.1"))

    def test_reset_specific_ip(self):
        """Reset de IP específica no afecta otras."""
        limiter = RateLimiter(max_requests=1, window_seconds=60, block_seconds=60)

        limiter.check(_make_request("1.1.1.1"))
        limiter.check(_make_request("2.2.2.2"))

        limiter.reset("1.1.1.1")

        # 1.1.1.1 puede hacer requests, 2.2.2.2 ya no
        limiter.check(_make_request("1.1.1.1"))  # OK

        with pytest.raises(HTTPException):
            limiter.check(_make_request("2.2.2.2"))
