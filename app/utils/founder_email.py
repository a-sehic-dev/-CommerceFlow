"""Optional SMTP notifications to the founder inbox."""

from __future__ import annotations

import logging
import smtplib
from email.message import EmailMessage

from app.config import get_settings

logger = logging.getLogger("commerceflow.email")


def _smtp_ready() -> bool:
    return bool(get_settings().smtp_host)


def send_email(
    *,
    to: str,
    subject: str,
    body: str,
    attachment: tuple[str, bytes, str] | None = None,
) -> bool:
    settings = get_settings()
    if not settings.smtp_host:
        return False
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = settings.smtp_from_email or settings.smtp_username or settings.assistant_alert_email
    msg["To"] = to
    msg.set_content(body)
    if attachment:
        filename, data, mime = attachment
        maintype, _, subtype = mime.partition("/")
        subtype = subtype or "octet-stream"
        msg.add_attachment(data, maintype=maintype, subtype=subtype, filename=filename)
    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as smtp:
            smtp.starttls()
            if settings.smtp_username and settings.smtp_password:
                smtp.login(settings.smtp_username, settings.smtp_password)
            smtp.send_message(msg)
        return True
    except Exception:
        logger.exception("Failed to send email: %s", subject)
        return False


def send_founder_email(*, subject: str, body: str) -> bool:
    settings = get_settings()
    return send_email(to=settings.assistant_alert_email, subject=subject, body=body)


def smtp_configured() -> bool:
    return _smtp_ready()
