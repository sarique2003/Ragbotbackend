from fastapi import HTTPException
from passlib.context import CryptContext
from backend.models.user_model import User, UserInDB
from typing import Optional
from datetime import datetime, timedelta
from backend.dao.user_dao import UserDAO
from jose import jwt, JWTError
from fastapi.security import OAuth2PasswordBearer
import uuid


class UserService:
    def __init__(self, user_dao: UserDAO, secret_key: str):
        self.user_dao = user_dao
        self.secret_key = secret_key
        self._algorithm = 'HS256'
        self._access_token_expiry_minutes = 60
        self.oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")
        self._pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

    def get_password_hash(self, password: str) -> str:
        return self._pwd_context.hash(password)

    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        return self._pwd_context.verify(plain_password, hashed_password)

    def get_user_by_email(self, email: str) -> Optional[UserInDB]:
        user_data = self.user_dao.find_by_email(email)
        return UserInDB(**user_data) if user_data else None

    def create_user(self, user: User) -> UserInDB:
        if self.get_user_by_email(user.user_email):
            raise ValueError("User already exists")
        user_id = str(uuid.uuid4())
        hashed_password = self.get_password_hash(user.password)
        user_data = {
            "user_id": user_id,
            "user_name": user.user_name,
            "user_email": user.user_email,
            "password": hashed_password
        }
        self.user_dao.insert_user(user_data)
        return UserInDB(**user_data)

    def authenticate_user(self, email: str, password: str) -> Optional[UserInDB]:
        user = self.get_user_by_email(email)
        if not user or not self.verify_password(password, user.password):
            return None
        return user

    def create_access_token(self, data: dict, expires_delta: Optional[timedelta] = None) -> str:
        to_encode = data.copy()
        expire = datetime.utcnow() + (expires_delta or timedelta(minutes=self._access_token_expiry_minutes))
        to_encode.update({"exp": expire})
        return jwt.encode(to_encode, self.secret_key, algorithm=self._algorithm)

    def decode_token(self, token: str) -> dict:
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self._algorithm])
            return payload
        except JWTError:
            raise ValueError("Invalid token")

    def get_user_by_token(self, token: str) -> UserInDB:
        payload = self.decode_token(token)
        email: str | None = payload.get("sub")
        if not email:
            raise HTTPException(status_code=401, detail="Invalid token payload")

        user = self.get_user_by_email(email)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        return user

    def delete_user(self, email: str):
        """Delete user by email"""
        user = self.get_user_by_email(email)
        if not user:
            raise ValueError("User not found")
        return self.user_dao.delete_user(user.user_id)