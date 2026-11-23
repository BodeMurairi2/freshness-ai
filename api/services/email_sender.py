"""
Sends emails through Gmail SMTP (app password).
"""
import smtplib
import ssl
from email.message import EmailMessage
from email.utils import formataddr

from api.config.settings import app_settings

settings = app_settings()


def send_email(recipient: str, subject: str, text_body: str, html_body: str | None = None):
    """Blocking: call it from a thread or a background task"""
    message = EmailMessage()
    message["From"] = formataddr((settings.EMAIL_SENDER_NAME, settings.SMTP_USERNAME))
    message["To"] = recipient
    message["Subject"] = subject
    message.set_content(text_body)
    if html_body:
        message.add_alternative(html_body, subtype="html")

    with smtplib.SMTP_SSL(settings.SMTP_HOST, settings.SMTP_PORT, context=ssl.create_default_context(), timeout=20) as server:
        server.login(settings.SMTP_USERNAME, settings.SMTP_APP_PASSWORD)
        server.send_message(message)
