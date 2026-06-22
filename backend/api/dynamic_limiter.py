from slowapi import Limiter
from slowapi.util import get_remote_address
from fastapi import Request


class _DynamicLimitCallable:
    """
    Callable compatible con SlowAPI 0.1.9 para límites dinámicos por tier.

    SlowAPI 0.1.9 llama al callable con `(request)` durante la ejecución real,
    pero también puede intentar llamarlo sin argumentos durante la introspección
    interna. Esta clase maneja ambos casos correctamente.
    """

    def __call__(self, request: Request = None) -> str:
        """
        Retorna el límite de requests basado en el nivel de suscripción del usuario.
        Si no hay request disponible (introspección interna de SlowAPI),
        retorna el límite más conservador como fallback seguro.
        """
        if request is None:
            # Llamada interna de SlowAPI sin request — usar límite más restrictivo
            return "5/minute"

        user = getattr(request.state, "user", None)
        if user:
            tier = getattr(user, "subscription_tier", "free")
            if tier == "premium":
                return "1000/minute"
            # Free tier
            return "10/minute"

        # Unauthenticated fallback
        return "5/minute"


get_dynamic_limit = _DynamicLimitCallable()

limiter = Limiter(key_func=get_remote_address)

