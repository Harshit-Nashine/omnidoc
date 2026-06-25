# ================================================================
# services/api/app/audit_routes.py
# ================================================================
# Audit log endpoints — admin only.
#
# GET /audit/           — all events for this tenant
# GET /audit/{doc_id}   — all events for one document
# POST /audit/process   — manually trigger audit log write
#                         from Redis Stream (backfill)
# ================================================================

import uuid
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel

from services.api.app.database import get_postgresql_pool
from services.api.app.auth_routes import get_current_user
from services.api.app.audit_queries import write_audit_log, get_audit_log
from services.api.app.events import emit_document_event

router = APIRouter(prefix="/audit", tags=["Audit"])


class AuditLogEntry(BaseModel):
    """One audit log entry returned to client."""
    id: uuid.UUID
    tenant_id: uuid.UUID
    user_id: Optional[uuid.UUID]
    document_id: Optional[uuid.UUID]
    event_type: str
    payload: str
    created_at: datetime

    model_config = {"from_attributes": True}


@router.get("/", response_model=list[AuditLogEntry])
async def list_audit_log(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    current_user: dict = Depends(get_current_user),
    pool=Depends(get_postgresql_pool),
):
    """
    Returns audit log entries for the current tenant.
    Admin and editor roles only — viewers cannot see audit log.
    Newest entries first.
    """
    if current_user["role"] not in ("admin", "editor"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admin and editor roles can view audit logs.",
        )

    tenant_id = uuid.UUID(str(current_user["tenant_id"]))

    entries = await get_audit_log(
        pool=pool,
        tenant_id=tenant_id,
        limit=limit,
        offset=offset,
    )

    return [AuditLogEntry(**entry) for entry in entries]


@router.get("/{document_id}", response_model=list[AuditLogEntry])
async def get_document_audit_log(
    document_id: uuid.UUID,
    current_user: dict = Depends(get_current_user),
    pool=Depends(get_postgresql_pool),
):
    """
    Returns all audit events for a specific document.
    Shows the complete lifecycle: uploaded → processed →
    approved → embedded.
    """
    if current_user["role"] not in ("admin", "editor"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admin and editor roles can view audit logs.",
        )

    tenant_id = uuid.UUID(str(current_user["tenant_id"]))

    entries = await get_audit_log(
        pool=pool,
        tenant_id=tenant_id,
        document_id=document_id,
    )

    return [AuditLogEntry(**entry) for entry in entries]


@router.post("/sync", status_code=status.HTTP_200_OK)
async def sync_audit_log_from_stream(
    current_user: dict = Depends(get_current_user),
    pool=Depends(get_postgresql_pool),
):
    """
    Reads unprocessed events from Redis Stream and writes
    them to the audit_log table.

    Admin only. Use this to backfill audit log from stream
    or after a consumer downtime.
    """
    if current_user["role"] != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admin role can sync audit log.",
        )

    from services.api.app.database import get_redis_client

    redis = get_redis_client()
    tenant_id = uuid.UUID(str(current_user["tenant_id"]))

    # Read all events from the stream
    messages = await redis.xrange("omnidoc:document_events")

    count = 0
    for message_id, data in messages:
        # Only process events belonging to this tenant
        if data.get("tenant_id") != str(tenant_id):
            continue

        import json
        payload = {}
        try:
            payload = json.loads(data.get("payload", "{}"))
        except Exception:
            pass

        await write_audit_log(
            pool=pool,
            tenant_id=tenant_id,
            event_type=data.get("event_type", "unknown"),
            document_id=data.get("document_id"),
            user_id=data.get("user_id"),
            payload=payload,
        )
        count += 1

    return {
        "message": f"Synced {count} events to audit log.",
        "events_processed": count,
    }