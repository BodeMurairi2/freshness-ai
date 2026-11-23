"""
Users in the users collection, and the dependency that protects routes.
"""
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pymongo.asynchronous.database import AsyncDatabase
from pymongo.errors import DuplicateKeyError

from api.database.connection import get_database
from api.schemas.users import NewUser
from api.services.retrain_status import current_time
from api.services.security import hash_password, read_access_token

USERS = "users"

# Swagger's "Authorize" button: paste the access_token from /auth/login
bearer_scheme = HTTPBearer(auto_error=False)


async def find_user(database: AsyncDatabase, email_address: str) -> dict | None:
    return await database[USERS].find_one({"email_address": email_address.lower()})


async def find_user_for_login(database: AsyncDatabase, email_or_username: str) -> dict | None:
    """Login accepts the email or the username"""
    identifier = email_or_username.strip().lower()
    return await database[USERS].find_one({"$or": [{"email_address": identifier}, {"username": identifier}]})


async def create_user(database: AsyncDatabase, new_user: NewUser) -> str | None:
    """Returns the field already taken ("email_address" or "username"), or None once created"""
    try:
        await database[USERS].insert_one({
            "first_name": new_user.first_name,
            "last_name": new_user.last_name,
            "username": new_user.username,
            "email_address": new_user.email_address.lower(),
            "password_hash": hash_password(new_user.password),
            "created_at": current_time(),
        })
    except DuplicateKeyError as error:
        taken_fields = list((error.details or {}).get("keyPattern", {}).keys())
        return taken_fields[0] if taken_fields else "email_address"
    return None


async def update_password(database: AsyncDatabase, email_address: str, new_password: str):
    await database[USERS].update_one(
        {"email_address": email_address.lower()},
        {"$set": {"password_hash": hash_password(new_password), "password_changed_at": current_time()}},
    )


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    database: Annotated[AsyncDatabase, Depends(get_database)],
) -> dict:
    """
    FastAPI dependency: the logged in user, or 401
    """
    email_address = read_access_token(credentials.credentials) if credentials else None
    user = await find_user(database, email_address) if email_address else None
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token, please log in again",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user
