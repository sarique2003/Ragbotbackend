from enum import Enum
from typing import Optional
from pydantic import BaseModel

DEFAULT_EMBEDDINGS_MODEL = "text-embedding-ada-002"


class VectorDBConfig(BaseModel):
    embeddings_model: str = DEFAULT_EMBEDDINGS_MODEL


class PineconeConfig(VectorDBConfig):
    api_key: Optional[str]
    top_k: int = 3
    base_url: str
