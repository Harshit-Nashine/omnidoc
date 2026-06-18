# ================================================================
# services/api/app/events.py
# ================================================================
# Redis Streams event bus for document state changes.
#
# WHY REDIS STREAMS OVER SIMPLE PUBSUB:
# Redis PubSub is fire-and-forget — if a consumer is down,
# the message is lost. Redis Streams persist messages and let
# consumers read from any point in history. Critical for audit
# trails and guaranteed notification delivery.
#
# EVENT FORMAT:
# Every event has: event_type, document_id, tenant_id,
# user_id, timestamp, and optional payload.
#
# CONSUMERS:
# - email_consumer    → sends email to document uploader
# - slack_consumer    → posts to Slack channel
# - audit_consumer    → writes to audit_log table
# ================================================================

import json
import uuid
from datetime import datetime, timezone
from services.api.app.database import get_redis_client


# Stream name — all document events go here
DOCUMENT_EVENTS_STREAM = "omnidoc:document_events"

# Consumer group name
CONSUMER_GROUP = "omnidoc_notifications"

# Event types
class DocumentEvent:
    UPLOADED    = "document.uploaded"
    PROCESSED   = "document.processed"
    FLAGGED     = "document.flagged"
    APPROVED    = "document.approved"
    REJECTED    = "document.rejected"
    EMBEDDED    = "document.embedded"
    FAILED      = "document.failed"


async def emit_document_event(
    event_type: str,
    document_id: str,
    tenant_id: str,
    user_id: str,
    payload: dict = None,
) -> str:
    """
    Emits a document event to Redis Streams.

    Events are persisted in Redis — even if consumers are
    temporarily down, they will process events when they restart.

    Returns the Redis stream message ID.
    """
    redis = get_redis_client()

    event_data = {
        "event_type": event_type,
        "document_id": document_id,
        "tenant_id": tenant_id,
        "user_id": user_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "payload": json.dumps(payload or {}),
    }

    # xadd adds a message to the stream
    # '*' tells Redis to auto-generate the message ID
    message_id = await redis.xadd(
        DOCUMENT_EVENTS_STREAM,
        event_data,
    )

    return message_id


async def ensure_consumer_group():
    """
    Creates the consumer group if it doesn't exist.
    Consumer groups allow multiple consumers to coordinate
    which messages each one has processed.
    Called once on application startup.
    """
    redis = get_redis_client()

    try:
        # MKSTREAM=True creates the stream if it doesn't exist
        # '$' means start from new messages only (not historical)
        await redis.xgroup_create(
            DOCUMENT_EVENTS_STREAM,
            CONSUMER_GROUP,
            id="0",
            mkstream=True,
        )
    except Exception as e:
        # BUSYGROUP error means group already exists — that's fine
        if "BUSYGROUP" not in str(e):
            raise