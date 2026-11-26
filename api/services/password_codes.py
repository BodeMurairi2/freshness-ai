
import hashlib
import hmac
import logging
import secrets
from datetime import timedelta

from pymongo.asynchronous.database import AsyncDatabase

from api.config.settings import app_settings
from api.services.email_sender import send_email
from api.services.retrain_status import current_time

logger = logging.getLogger(__name__)
settings = app_settings()

PASSWORD_CODES = "password_codes"
MAX_ATTEMPTS = 5
SECONDS_BETWEEN_CODES = 60


def hash_code(code: str) -> str:
    return hmac.new(settings.JWT_SECRET_KEY.encode(), code.encode(), hashlib.sha256).hexdigest()


async def create_code(database: AsyncDatabase, email_address: str) -> str | None:
    """
    This function creates a new code for an email, replacing the previous one.
    Returns None if a code was already sent less than a minute ago.
    """
    codes = database[PASSWORD_CODES]
    now = current_time()
    previous_code = await codes.find_one({"_id": email_address})
    if previous_code and (now - previous_code["created_at"]).total_seconds() < SECONDS_BETWEEN_CODES:
        return None

    code = f"{secrets.randbelow(1_000_000):06d}"
    await codes.replace_one(
        {"_id": email_address},
        {
            "code_hash": hash_code(code),
            "attempts": 0,
            "created_at": now,
            "expires_at": now + timedelta(minutes=settings.PASSWORD_CODE_MINUTES),
        },
        upsert=True,
    )
    return code


async def check_code(database: AsyncDatabase, email_address: str, code: str) -> bool:
    """
    True if the code is right and still valid. A used code is deleted,
    and a code is deleted after MAX_ATTEMPTS wrong tries.
    """
    codes = database[PASSWORD_CODES]
    saved_code = await codes.find_one({"_id": email_address})
    if saved_code is None or saved_code["expires_at"] < current_time():
        return False

    if hmac.compare_digest(saved_code["code_hash"], hash_code(code)):
        await codes.delete_one({"_id": email_address})
        return True

    if saved_code["attempts"] + 1 >= MAX_ATTEMPTS:
        await codes.delete_one({"_id": email_address})
    else:
        await codes.update_one({"_id": email_address}, {"$inc": {"attempts": 1}})
    return False


def send_code_email(email_address: str, first_name: str, code: str):
    """Background task: errors are logged since nobody waits on it"""
    minutes = settings.PASSWORD_CODE_MINUTES
    try:
        send_email(
            recipient=email_address,
            subject=f"Your Freshness-ai code: {code}",
            text_body=(
                f"Hi {first_name},\n\n"
                f"Your code to change your Freshness-ai password is: {code}\n"
                f"It expires in {minutes} minutes.\n\n"
                "If you did not ask for it, you can ignore this email."
            ),
            html_body=(
                f"<p>Hi {first_name},</p>"
                f"<p>Your code to change your Freshness-ai password is:</p>"
                f"<p style='font-size:28px;font-weight:bold;letter-spacing:6px'>{code}</p>"
                f"<p>It expires in {minutes} minutes.</p>"
                "<p>If you did not ask for it, you can ignore this email.</p>"
            ),
        )
    except Exception:
        logger.exception("Could not send the password code to %s", email_address)
