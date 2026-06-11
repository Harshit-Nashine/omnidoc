# ================================================================
# services/api/app/celery_app.py
# ================================================================
# Celery application instance and configuration.
#
# WHY CELERY OVER FASTAPI BACKGROUNDTASKS:
# FastAPI BackgroundTasks run in the same process as the API.
# If the API restarts, all in-progress tasks are lost.
# Celery tasks persist in Redis — survive restarts, crashes,
# and deployments. Critical for long-running parsing jobs.
#
# BROKER vs BACKEND:
# Broker (Redis) = where tasks are queued and sent to workers
# Backend (Redis) = where task results are stored after completion
# We use Redis for both — simpler than adding RabbitMQ.
# ================================================================

from celery import Celery
from services.api.app.config import settings

# Build Redis URL with password
# redis://:password@host:port/db_number
# db_number 0 = default Redis database
# We use db 0 for Celery broker and db 1 for results
# Separating them makes it easier to clear one without the other
REDIS_BROKER_URL = (
    f"redis://:{settings.redis_password}"
    f"@{settings.redis_host}"
    f":{settings.redis_port}/0"
)

REDIS_RESULT_BACKEND = (
    f"redis://:{settings.redis_password}"
    f"@{settings.redis_host}"
    f":{settings.redis_port}/1"
)

# Create the Celery application
# First argument = name used in logs to identify this app
celery_app = Celery(
    "omnidoc",
    broker=REDIS_BROKER_URL,
    backend=REDIS_RESULT_BACKEND,
)

# Configuration
celery_app.conf.update(
    # Serialize tasks as JSON — readable in Redis, debuggable
    # Default is pickle which has security issues
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],

    # Timezone — always UTC
    timezone="UTC",
    enable_utc=True,

    # How long to keep task results in Redis
    # 24 hours is enough for checking status — old results auto-deleted
    result_expires=86400,

    # Retry failed tasks up to 3 times with 60 second delay
    # Handles transient errors (DB briefly unavailable etc.)
    task_acks_late=True,
    task_reject_on_worker_lost=True,

    # Which modules contain task definitions
    # Celery auto-discovers tasks in these modules
    include=["services.api.app.tasks"],
)