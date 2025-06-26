# backend/services/message_service.py
from datetime import datetime
from typing import List
from fastapi import HTTPException

from dao.message_dao import MessageDAO
from models.message_model import Message, MessageInDB
from models.ai_processing_models import MessageRecommendationContext, MessageAnalysis
from dao.user_dao import UserDAO
from services.ai_processing_service import DMAIService


class MessageService:
    """
    Business logic for chat messages.
    • Uses MessageDAO for persistence.
    • Verifies the user exists via UserDAO.
    • Provides helper to echo-reply (can be swapped for real bot logic).
    """
    def __init__(self, message_dao: MessageDAO, user_dao: UserDAO, ai_processing_service: DMAIService):
        self.message_dao = message_dao
        self.user_dao = user_dao
        self.ai_prcoessing_service = ai_processing_service

    def store_message(
        self,
        text: str,
        sender: str,          # 'user' | 'bot'
        user_id: int,
        ts: datetime | None = None,
    ) -> int:
        # 1. validate sender
        if sender not in {"user", "bot"}:
            raise HTTPException(status_code=400, detail="Invalid sender")

        # 2. verify user exists (optional but nice)
        if not self.user_dao.find_by_id(user_id):
            raise HTTPException(status_code=404, detail="User not found")

        # 3. persist
        msg = Message(
            text=text,
            sender=sender,
            user_id=user_id,
            timestamp=ts or datetime.utcnow(),
        )
        return self.message_dao.store_message(msg)

    def get_messages(self, user_id: int, limit: int = 20) -> List[MessageInDB]:
        if not self.user_dao.find_by_id(user_id):
            raise HTTPException(status_code=404, detail="User not found")

        return self.message_dao.get_messages(user_id=user_id, limit=limit)

    async def process_user_message(self, user_id: int, text: str) -> str:
        # Save user's message
        self.store_message(text=text, sender="user", user_id=user_id)
        db_rows = self.get_messages(user_id=user_id)
        history_dicts = [
            {k: v for k, v in row.model_dump().items() if k != "timestamp"}
            if hasattr(row, "model_dump")

            else {
                "id": row.id,
                "text": row.text,
                "sender": row.sender,
                "user_id": row.user_id,
            }
            for row in db_rows
        ]

        message_context = MessageRecommendationContext(
            enriched_messages=history_dicts,
            user=self.user_dao.find_by_id(user_id=user_id)
        )
        message_analysis: MessageAnalysis = await self.ai_prcoessing_service.analyse_dm_with_ai(message_context=message_context)

        # Save bot's message
        self.store_message(text=message_analysis.suggested_message_reply, sender="bot", user_id=user_id)

        return message_analysis.suggested_message_reply
