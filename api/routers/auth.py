from typing import Annotated

from fastapi import HTTPException, Depends, BackgroundTasks, status
from fastapi.routing import APIRouter
from pymongo.asynchronous.database import AsyncDatabase

from api.database.connection import get_database
from api.schemas.common import MessageResponse
from api.schemas.users import NewUser, UserLogin, PasswordCodeRequest, ChangePassword, AccessToken, RegisteredUser
from api.services.password_codes import create_code, check_code, send_code_email
from api.services.security import verify_password, create_access_token
from api.services.users import find_user, find_user_for_login, create_user, update_password

router = APIRouter(
    prefix="/auth",
    tags=["Authentication"]
)

TAKEN_MESSAGES = {
    "email_address": "This email is already registered",
    "username": "This username is already taken",
}


@router.post("/register", status_code=status.HTTP_201_CREATED, response_model=RegisteredUser)
async def register(new_user: NewUser, database: Annotated[AsyncDatabase, Depends(get_database)]):
    """
    This function registers a new user
    """
    taken_field = await create_user(database, new_user)
    if taken_field:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=TAKEN_MESSAGES.get(taken_field, "Already registered"))
    return {
        "message": "Account created, you can now log in",
        "username": new_user.username,
        "email_address": new_user.email_address.lower(),
    }


@router.post("/login", response_model=AccessToken)
async def login(credentials: UserLogin,
                database: Annotated[AsyncDatabase, Depends(get_database)]):
    """
    Logs in with email or username and password, returns a JWT token
    """
    user = await find_user_for_login(database, credentials.username)
    if user is None or not verify_password(credentials.password, user["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Wrong email, username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return AccessToken(access_token=create_access_token(user["email_address"]))


@router.post("/password/code", response_model=MessageResponse)
async def request_password_code(request: PasswordCodeRequest,
                                background_tasks: BackgroundTasks,
                                database: Annotated[AsyncDatabase, Depends(get_database)]):
    """
    Sends a 6-digit code by email to change the password (or reset a forgotten one).
    Same answer whether the email exists or not, so accounts can't be guessed
    """
    user = await find_user(database, request.email_address)
    if user is not None:
        code = await create_code(database, user["email_address"])
        if code is not None:
            background_tasks.add_task(send_code_email, user["email_address"], user["first_name"], code)
    return {"message": "If this email is registered, a code was sent. It expires in a few minutes"}


@router.put("/password", response_model=MessageResponse)
async def change_password(passwords: ChangePassword, database: Annotated[AsyncDatabase, Depends(get_database)]):
    """
    This function changes the password with the code received by email
    """
    email_address = passwords.email_address.lower()
    if not await check_code(database, email_address, passwords.code):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired code")
    await update_password(database, email_address, passwords.new_password)
    return {"message": "Password changed, you can now log in"}
