import re
from pydantic import BaseModel, Field, EmailStr, field_validator

class NewUser(BaseModel):
    """
    Add a new user
    """
    first_name:str = Field(..., description="User first name")
    last_name:str = Field(..., description="User last name")
    username:str = Field(..., description="Username")
    email_address:EmailStr = Field(..., description="User email address")
    password:str = Field(..., description="User password")
    confirm_password:str = Field(..., description="User password")

    @field_validator
    def validate_password(password, cls):
        password_regex = r'^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[^\w\s]).{8,16}$'
        if not re.match(pattern=password_regex, string=password):
            raise ValueError("Password needs at least 8 characters")

class UserLogin(BaseModel):
    """
    Login user
    """
    email_address:EmailStr = Field(..., description="User email address")
    password:str = Field(..., description="User password")

class ChangePassword(BaseModel):
    """
    Change Password
    """
    password:str
    confirm_password:str

    @field_validator
    def validate_password(password, cls):
        password_regex = r'^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[^\w\s]).{8,16}$'
        if not re.match(pattern=password_regex, string=password):
            raise ValueError("Password needs at least 8 characters")
