from typing import List, Optional, Union
from pydantic import BaseModel
from backend.models.user_model import User


class MessageRecommendationContext(BaseModel):
    enriched_messages: list[dict]
    user: User


class MessageAnalysis(BaseModel):
    message_category: str
    suggested_message_reply: str
    conversation_summary: str
    factual_consistency: str