"""
Minimal SMTP transactional email sender for auth flows.

Deliberately simple — synchronous `smtplib`, no template engine, no
provider SDK — because every call site here runs inside a FastAPI
`BackgroundTask`, off the request/response path. Swap in a provider (SES,
Postmark, SendGrid) behind this same two-function surface later without
touching the service layer that calls it.
"""
import smtplib
from email.message import EmailMessage

import structlog

from app.core.config import get_settings

logger = structlog.get_logger(__name__)
settings = get_settings()


def _send_email(to_email: str, subject: str, html_body: str, text_body: str) -> None:
    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = settings.EMAIL_FROM_ADDRESS
    message["To"] = to_email
    message.set_content(text_body)
    message.add_alternative(html_body, subtype="html")

    try:
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=10) as smtp:
            if settings.SMTP_USE_TLS:
                smtp.starttls()
            if settings.SMTP_USER and settings.SMTP_PASSWORD:
                smtp.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            smtp.send_message(message)
        logger.info("email_sent", to=to_email, subject=subject)
    except (smtplib.SMTPException, OSError) as exc:
        # A background task has nothing left to roll back and no request
        # to fail — log and move on. A production deployment would push
        # this onto a retry queue (e.g. Celery/RQ with backoff) instead.
        logger.error("email_send_failed", to=to_email, subject=subject, error=str(exc))


def send_password_reset_email(to_email: str, token: str) -> None:
    reset_link = f"{settings.FRONTEND_URL}/reset-password?token={token}"
    subject = "Reset your password"
    text_body = (
        "We received a request to reset your password.\n\n"
        f"Reset it here: {reset_link}\n\n"
        "This link expires in 30 minutes. If you didn't request this, "
        "you can safely ignore this email."
    )
    html_body = (
        "<p>We received a request to reset your password.</p>"
        f'<p><a href="{reset_link}">Click here to reset your password</a></p>'
        "<p>This link expires in 30 minutes. If you didn't request this, "
        "you can safely ignore this email.</p>"
    )
    _send_email(to_email, subject, html_body, text_body)


def send_verification_email(to_email: str, token: str) -> None:
    verify_link = f"{settings.FRONTEND_URL}/verify-email?token={token}"
    subject = "Verify your email address"
    text_body = (
        "Welcome! Please verify your email address to activate your account.\n\n"
        f"Verify here: {verify_link}\n\n"
        "This link expires in 24 hours."
    )
    html_body = (
        "<p>Welcome! Please verify your email address to activate your account.</p>"
        f'<p><a href="{verify_link}">Click here to verify your email</a></p>'
        "<p>This link expires in 24 hours.</p>"
    )
    _send_email(to_email, subject, html_body, text_body)