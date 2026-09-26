"""Recovery messages are delivered after commit, never returned or logged."""

import logging
import smtplib
import ssl
from dataclasses import dataclass, field
from email.message import EmailMessage
from urllib.parse import urlencode

from app.core.config import Settings

logger = logging.getLogger("gopher.auth.delivery")


@dataclass(frozen=True)
class Delivery:
    recipient: str = field(repr=False)
    token: str = field(repr=False)
    purpose: str


class RecoveryMailer:
    def __init__(self, settings: Settings):
        self.settings = settings

    def send(self, delivery: Delivery) -> bool:
        settings = self.settings
        message = EmailMessage()
        message["From"] = str(settings.smtp_from)
        message["To"] = delivery.recipient
        message["Subject"] = "Gopher Fit account recovery"
        link = (
            settings.recovery_frontend_url
            + "#"
            + urlencode({"purpose": delivery.purpose, "token": delivery.token})
        )
        message.set_content(
            f"Open this link to {delivery.purpose} your Gopher Fit account.\n{link}\n\n"
            f"The link expires in {settings.recovery_ttl_seconds // 60} minutes and works once.\n"
            "If you did not request this message, ignore it."
        )
        try:
            context = ssl.create_default_context()
            client: smtplib.SMTP
            if settings.smtp_tls == "implicit":
                client = smtplib.SMTP_SSL(
                    settings.smtp_host,
                    settings.smtp_port,
                    timeout=settings.smtp_timeout_seconds,
                    context=context,
                )
            else:
                client = smtplib.SMTP(
                    settings.smtp_host, settings.smtp_port, timeout=settings.smtp_timeout_seconds
                )
            with client:
                if settings.smtp_tls == "starttls":
                    client.starttls(context=context)
                if settings.smtp_username:
                    client.login(settings.smtp_username, settings.smtp_password.get_secret_value())
                client.send_message(message)
            return True
        except (OSError, smtplib.SMTPException):
            # SMTP errors can contain recipients or message contents; never log the exception.
            logger.error("recovery_delivery_failed")
            return False
