from fastapi import APIRouter, HTTPException, Depends, status, Query
from fastapi.security import OAuth2PasswordRequestForm
from models.user_model import User, UserInDB, Token
from container import ServicesContainer

user_router = APIRouter(prefix="/user")
user_service = ServicesContainer.user_service()


@user_router.post("/register", response_model=UserInDB, status_code=status.HTTP_201_CREATED)
def register(user: User):
    try:
        return user_service.create_user(user)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@user_router.post("/login", response_model=Token)
def login(form_data: OAuth2PasswordRequestForm = Depends()):
    user = user_service.authenticate_user(form_data.username, form_data.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid email or password")
    token = user_service.create_access_token({"sub": user.user_email})
    return {
        "access_token": token,
        "token_type": "bearer",
    }

@user_router.get("/fetch", response_model=UserInDB)
def get_user(user_token: str = Query(..., alias="token")):
    try:
        # Decode token (use UserService helper if you added one)
        return user_service.get_user_by_token(token=user_token)
    except Exception:
            raise HTTPException(status_code=401, detail="Invalid token")


@user_router.delete("/users/me", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(token: str = Depends(user_service.oauth2_scheme)):
    try:
        payload = user_service.decode_token(token)
        email = payload.get("sub")
        user = user_service.get_user_by_email(email)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        user_service.delete_user(email)
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")
