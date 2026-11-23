"""
Password hashing and JWT tokens.
"""
from datetime import datetime, timedelta, timezone

import jwt
from pwdlib import PasswordHash

from api.config.settings import app_settings

settings = app_settings()
JWT_ALGORITHM = "HS256"

password_hasher = PasswordHash.recommended()  # Argon2


def hash_password(password: str) -> str:
    return password_hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return password_hasher.verify(password, password_hash)


def create_access_token(email_address: str) -> str:
    """Signed token that identifies the user until it expires"""
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=settings.JWT_EXPIRE_MINUTES)
    return jwt.encode({"sub": email_address, "exp": expires_at}, settings.JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)


def read_access_token(token: str) -> str | None:
    """Email address inside a valid token, None if the token is invalid or expired"""
    try:
        return jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM]).get("sub")
    except jwt.InvalidTokenError:
        return None
