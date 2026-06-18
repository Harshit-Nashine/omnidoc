# ================================================================
# services/api/app/notifications.py
# ================================================================
# Notification consumers for document events.
#
# Three consumers run as background tasks:
#   1. email_notification    — sends email to document owner
#   2. slack_notification    — posts to Slack webhook
#   3. audit_log_writer      — writes to PostgreSQL audit_log
#
# All consumers are triggered by emit_document_event() calls.
# If NOTIFICATIONS_ENABLED=false, consumers silently skip sending.
# ================================================================

import json
import httpx
from services.api.app.config import settings


# ── Email notifications ──────────────────────────────────────────

async def send_email_notification(
    to_email: str,
    subject: str,
    body: str,
) -> bool:
    """
    Sends an email notification via SMTP.

    Returns True if sent, False if disabled or failed.
    Never raises — notification failures should not crash
    the document processing pipeline.
    """
    if not settings.notifications_enabled:
        return False

    if not settings.smtp_user or not settings.smtp_password:
        return False

    try:
        import aiosmtplib
        from email.mime.text import MIMEText
        from email.mime.multipart import MIMEMultipart

        message = MIMEMultipart("alternative")
        message["Subject"] = subject
        message["From"] = settings.smtp_from
        message["To"] = to_email

        text_part = MIMEText(body, "plain")
        message.attach(text_part)

        await aiosmtplib.send(
            message,
            hostname=settings.smtp_host,
            port=settings.smtp_port,
            username=settings.smtp_user,
            password=settings.smtp_password,
            start_tls=True,
        )
        return True

    except Exception as e:
        print(f"Email notification failed: {e}")
        return False


# ── Slack notifications ──────────────────────────────────────────

async def send_slack_notification(
    message: str,
    emoji: str = ":page_facing_up:",
) -> bool:
    """
    Sends a message to Slack via incoming webhook.

    Returns True if sent, False if disabled or failed.
    Never raises — same reasoning as email.
    """
    if not settings.notifications_enabled:
        return False

    if not settings.slack_webhook_url:
        return False

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                settings.slack_webhook_url,
                json={"text": f"{emoji} {message}"},
                timeout=10.0,
            )
            return response.status_code == 200

    except Exception as e:
        print(f"Slack notification failed: {e}")
        return False


# ── Notification dispatcher ──────────────────────────────────────

async def notify_document_event(
    event_type: str,
    document_id: str,
    filename: str,
    tenant_name: str,
    user_email: str,
    extra_info: str = "",
) -> None:
    """
    Dispatches notifications for a document event.
    Called after emitting to Redis Streams.

    Sends both email and Slack (if configured).
    Failures are logged but never raised.
    """
    # Build human-readable messages per event type
    messages = {
        "document.uploaded": (
            f"Document '{filename}' uploaded successfully.",
            f"Document uploaded in {tenant_name}: {filename}",
            ":inbox_tray:",
        ),
        "document.processed": (
            f"Document '{filename}' has been processed and is ready for review.",
            f"Document processed in {tenant_name}: {filename}",
            ":white_check_mark:",
        ),
        "document.flagged": (
            f"Document '{filename}' was flagged for PII review. {extra_info}",
            f"PII flagged in {tenant_name}: {filename}. {extra_info}",
            ":warning:",
        ),
        "document.approved": (
            f"Document '{filename}' has been approved and is being embedded.",
            f"Document approved in {tenant_name}: {filename}",
            ":rocket:",
        ),
        "document.embedded": (
            f"Document '{filename}' is now in the knowledge base and ready to query.",
            f"Document ready to query in {tenant_name}: {filename}",
            ":brain:",
        ),
        "document.failed": (
            f"Document '{filename}' failed processing. {extra_info}",
            f"Processing failed in {tenant_name}: {filename}. {extra_info}",
            ":x:",
        ),
    }

    if event_type not in messages:
        return

    email_body, slack_msg, emoji = messages[event_type]

    # Send both notifications concurrently
    import asyncio
    await asyncio.gather(
        send_email_notification(
            to_email=user_email,
            subject=f"OmniDoc: {event_type.replace('.', ' ').title()}",
            body=email_body,
        ),
        send_slack_notification(
            message=slack_msg,
            emoji=emoji,
        ),
        return_exceptions=True,  # don't let one failure cancel the other
    )