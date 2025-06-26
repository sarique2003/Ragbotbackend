from pymongo.collection import Collection
from pymongo import ReturnDocument
from typing import List, Dict
from datetime import datetime
from backend.models.message_model import Message, MessageInDB


class MessageDAO:
    """
    Data-access object for chat messages.

    • Each message gets an auto-incrementing integer `id`.
    • Messages are stored in `messages` collection.
    • Auto-increment counter lives in a shared `counters` collection.
    """

    COUNTER_KEY = "id"

    def __init__(
        self,
        messages_collection: Collection,
        counters_collection: Collection,
    ) -> None:
        self._messages = messages_collection
        self._counters = counters_collection

        # Index for fast querying by user and time (newest first)
        self._messages.create_index([("user_id", 1), ("timestamp", -1)])

    # ------------------------ private helper --------------------------- #
    def _next_id(self) -> int:
        """
        Atomically bump and return the next integer id
        using the counters collection.
        """
        doc = self._counters.find_one_and_update(
            {"_id": self.COUNTER_KEY},
            {"$inc": {"seq": 1}},
            upsert=True,
            return_document=ReturnDocument.AFTER,
        )
        return doc["seq"]

    # ------------------------ public methods --------------------------- #
    def store_message(self, msg: Message) -> int:
        """
        Insert a new message and return its integer id.
        """
        data: Dict = msg.dict()
        data["id"] = self._next_id()
        self._messages.insert_one(data)
        return data["id"]

    def get_messages(
        self,
        user_id: int,
        limit: int = 20,
    ) -> List[MessageInDB]:
        """
        Return newest → oldest messages for a given user.
        """
        cursor = (
            self._messages.find({"user_id": user_id})
            .sort("timestamp", -1)
            .limit(limit)
        )
        return [MessageInDB(**doc) for doc in cursor]
