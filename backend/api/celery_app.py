"""
api/celery_app.py

Configuración mínima de Celery para el MVP.

El worker del docker-compose espera este módulo en:
    celery -A api.celery_app worker

Aunque las tasks reales se añadirán en services/docking/queue_handler.py,
este archivo debe existir ya para que la infraestructura del backend sea
coherente desde la Fase 1.
"""

from celery import Celery

from core.config import get_settings

settings = get_settings()

celery_app = Celery(
    "moldesign",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["services.docking.queue_handler"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_track_started=True,
    task_time_limit=settings.celery_task_time_limit,
    task_soft_time_limit=settings.celery_task_soft_time_limit,
    result_expires=3600,
    timezone="UTC",
    enable_utc=True,
    # Prefetch 1 tarea a la vez: el docking es CPU-bound y de larga duración.
    # Con el default (4), un worker agarraría 4 tareas y bloquearía 3 mientras
    # ejecuta 1. Con prefetch=1, cada worker solo toma la siguiente tarea cuando
    # termina la actual.
    worker_prefetch_multiplier=1,
)
