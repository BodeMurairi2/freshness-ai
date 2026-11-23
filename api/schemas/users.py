import re

from pydantic import BaseModel, Field, EmailStr, field_validator, model_validator

PASSWORD_PATTERN = r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[^\w\s]).{8,64}$"
PASSWORD_RULE = "Password needs 8-64 characters with an uppercase letter, a lowercase letter, a digit and a symbol"
USERNAME_PATTERN = r"^[a-zA-Z0-9_.]{3,30}$"


def check_password_strength(password: str) -> str:
    if not re.match(PASSWORD_PATTERN, password):
        raise ValueError(PASSWORD_RULE)
    return password


class NewUser(BaseModel):
    """
    Register a new user
    """
    first_name: str = Field(..., min_length=1, max_length=50, description="User first name")
    last_name: str = Field(..., min_length=1, max_length=50, description="User last name")
    username: str = Field(..., description="3-30 letters, digits, _ or .")
    email_address: EmailStr = Field(..., description="User email address")
    password: str = Field(..., description=PASSWORD_RULE)
    confirm_password: str = Field(..., description="Same as password")

    @field_validator("first_name", "last_name")
    @classmethod
    def clean_name(cls, name: str) -> str:
        if not name.strip():
            raise ValueError("Name cannot be empty")
        return name.strip()

    @field_validator("username")
    @classmethod
    def validate_username(cls, username: str) -> str:
        if not re.match(USERNAME_PATTERN, username):
            raise ValueError("Username needs 3-30 letters, digits, _ or .")
        return username.lower()

    @field_validator("password")
    @classmethod
    def validate_password(cls, password: str) -> str:
        return check_password_strength(password)

    @model_validator(mode="after")
    def passwords_match(self):
        if self.password != self.confirm_password:
            raise ValueError("Passwords do not match")
        return self


class UserLogin(BaseModel):
    """
    Login with email or username
    """
    username: str = Field(..., description="Email or username")
    password: str


class PasswordCodeRequest(BaseModel):
    """
    Ask for a code to change (or reset) the password
    """
    email_address: EmailStr


class ChangePassword(BaseModel):
    """
    Change password with the code received by email. Works for a forgotten password too
    """
    email_address: EmailStr
    code: str = Field(..., min_length=6, max_length=6, description="6-digit code received by email")
    new_password: str = Field(..., description=PASSWORD_RULE)
    confirm_password: str

    @field_validator("new_password")
    @classmethod
    def validate_password(cls, new_password: str) -> str:
        return check_password_strength(new_password)

    @model_validator(mode="after")
    def passwords_match(self):
        if self.new_password != self.confirm_password:
            raise ValueError("Passwords do not match")
        return self


class RegisteredUser(BaseModel):
    message: str
    username: str
    email_address: EmailStr


class AccessToken(BaseModel):
    access_token: str
    token_type: str = "bearer"
