# backend/routes/message_route.py
from fastapi import APIRouter, Depends, HTTPException, status, Body, Query
from container import ServicesContainer
from services.messaging_service import MessageService
from services.user_service import UserService

messaging_router = APIRouter(prefix="/messages")

messaging_service: MessageService = ServicesContainer.message_service()
user_service: UserService = ServicesContainer.user_service()

@messaging_router.post(
    "/process",
    summary="Process a user message and return bot reply",
    status_code=status.HTTP_200_OK,
)
async def process_message(
    text: str = Body(..., embed=True, max_length=500),
    token: str = Depends(user_service.oauth2_scheme),
):
    payload = user_service.decode_token(token)
    email = payload.get("sub") or _unauth()
    user = user_service.get_user_by_email(email) or _unauth()

    reply = await messaging_service.process_user_message(user_id=user.user_id, text=text)
    return {"response": reply}


@messaging_router.get(
    "/history",
    summary="Get last N messages for the logged-in user",
    status_code=status.HTTP_200_OK,
)
def get_message_history(
    limit: int = Query(20, ge=1, le=100),
    token: str = Depends(user_service.oauth2_scheme),
):
    payload = user_service.decode_token(token)
    email = payload.get("sub") or _unauth()
    user = user_service.get_user_by_email(email) or _unauth()

    msgs = messaging_service.get_messages(user_id=user.user_id, limit=limit)
    return {"messages": msgs}


def _unauth():
    raise HTTPException(status_code=401, detail="Invalid or expired token")
