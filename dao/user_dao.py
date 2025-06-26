from pymongo.collection import Collection
from pymongo import ReturnDocument
from typing import Optional, Dict


class UserDAO:
    """User data-access with auto-incrementing integer user_id."""
    COUNTER_KEY = "user_id"

    def __init__(self, users_collection: Collection, counters_collection: Collection):
        self._col = users_collection
        self._counters = counters_collection

        # Ensure a unique index on email for fast look-ups & no duplicates
        self._col.create_index("user_email", unique=True)

    # ---------- private helper -----------------------------------------
    def _next_user_id(self) -> int:
        doc = self._counters.find_one_and_update(
            {"_id": self.COUNTER_KEY},
            {"$inc": {"seq": 1}},
            upsert=True,
            return_document=ReturnDocument.AFTER,
        )
        return doc["seq"]

    # ---------- CRUD ----------------------------------------------------
    def find_by_email(self, email: str) -> Optional[Dict]:
        return self._col.find_one({"user_email": email})

    def insert_user(self, user_data: Dict) -> int:
        """Add user, return new integer user_id."""
        user_data["user_id"] = self._next_user_id()
        self._col.insert_one(user_data)
        return user_data["user_id"]

    def find_by_id(self, user_id: int) -> Optional[Dict]:
        return self._col.find_one({"user_id": user_id})

    def update_user(self, user_id: int, updates: Dict) -> None:
        self._col.update_one({"user_id": user_id}, {"$set": updates})

    def delete_user(self, user_id: int) -> None:
        self._col.delete_one({"user_id": user_id})