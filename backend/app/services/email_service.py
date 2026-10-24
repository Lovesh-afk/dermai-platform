"""
Sends one email. Two modes, chosen by configuration:

  - SMTP mode (SMTP_HOST set): a real email via any SMTP server
    (Gmail, SendGrid, Amazon SES...), using STARTTLS encryption.
  - Console mode (SMTP_HOST empty): the email is written to the logs
    instead, so the whole app works with no email account.

Called from a Celery task, never directly from a web request, so a
slow or unreachable mail server can't slow down the website.
"""
import smtplib
from email.message import EmailMessage

from app.core.config import settings
from app.core.logging import logger

SMTP_TIMEOUT_SECONDS = 15


def send_email(to: str, subject: str, text: str, html: str | None = None) -> str:
    """Returns which mode was used: "smtp" or "console"."""
    if not settings.SMTP_HOST:
        logger.info("email_console_mode", to=to, subject=subject, body=text)
        return "console"

    msg = EmailMessage()
    msg["From"] = settings.EMAIL_FROM
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(text)  # plain-text version for every mail client
    if html:
        msg.add_alternative(html, subtype="html")

    with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=SMTP_TIMEOUT_SECONDS) as smtp:
        smtp.starttls()  # encrypt before sending the password
        if settings.SMTP_USER:
            smtp.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
        smtp.send_message(msg)
    logger.info("email_sent", to=to, subject=subject)
    return "smtp"
