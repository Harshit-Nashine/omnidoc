# ================================================================
# services/api/app/audit_queries.py
# ================================================================
# Writes to and reads from the audit_log table.
#
# WHY AUDIT LOG:
# Every document state change is permanently recorded.
# Admins can see full history: who uploaded what, when it was
# approved, who approved it, when it was embedded.
# Required for enterprise compliance (SOC2, ISO27001 etc.)
# ================================================================

import uuid
import json
from asyncpg import Pool


async def write_audit_log(
    pool: Pool,
    tenant_id: uuid.UUID,
    event_type: str,
    document_id: str | None = None,
    user_id: str | None = None,
    payload: dict | None = None,
) -> None:
    """
    Writes one audit log entry.
    Called after every document state change event.
    Never raises — audit log failure should not block operations.
    """
    try:
        await pool.execute(
            """
            INSERT INTO audit_log (
                tenant_id, user_id, document_id,
                event_type, payload
            )
            VALUES ($1, $2, $3, $4, $5)
            """,
            tenant_id,
            uuid.UUID(user_id) if user_id and user_id != "system" else None,
            uuid.UUID(document_id) if document_id else None,
            event_type,
            json.dumps(payload or {}),
        )
    except Exception as e:
        print(f"Audit log write failed: {e}")


async def get_audit_log(
    pool: Pool,
    tenant_id: uuid.UUID,
    document_id: uuid.UUID | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[dict]:
    """
    Fetches audit log entries for a tenant.
    Optionally filtered by document_id.
    Returns newest entries first.
    """
    if document_id:
        rows = await pool.fetch(
            """
            SELECT id, tenant_id, user_id, document_id,
                   event_type, payload, created_at
            FROM audit_log
            WHERE tenant_id = $1 AND document_id = $2
            ORDER BY created_at DESC
            LIMIT $3 OFFSET $4
            """,
            tenant_id,
            document_id,
            limit,
            offset,
        )
    else:
        rows = await pool.fetch(
            """
            SELECT id, tenant_id, user_id, document_id,
                   event_type, payload, created_at
            FROM audit_log
            WHERE tenant_id = $1
            ORDER BY created_at DESC
            LIMIT $2 OFFSET $3
            """,
            tenant_id,
            limit,
            offset,
        )

    return [dict(row) for row in rows]