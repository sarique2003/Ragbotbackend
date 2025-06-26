from pydantic import BaseModel, Field
from datetime import datetime
from typing import Literal


class Message(BaseModel):
    text: str                       # the message text
    sender: Literal["user", "bot"]  # who sent it
    user_id: int                    # FK to users collection
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class MessageInDB(Message):
    """Schema returned from DB (with Mongo's _id)."""
    id: int  # hex string of ObjectId
