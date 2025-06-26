from pydantic import BaseModel, EmailStr


class User(BaseModel):
    user_name: str
    user_email: EmailStr
    password: str


class UserInDB(User):
    user_id: int


class Token(BaseModel):
    access_token: str
    token_type: str
