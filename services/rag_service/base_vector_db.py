import logging
import os
from abc import abstractmethod
from typing import Iterable, List, Optional, Tuple

from langchain.docstore.document import Document
from langchain_openai import AzureOpenAIEmbeddings

from helpers import get_env_value

logger = logging.getLogger(__name__)
DEFAULT_OPENAI_EMBEDDING_MODEL = "text-embedding-ada-002"
AZURE_EMBEDDING_MODEL =get_env_value("AZURE_OPENAI_EMBEDDING_MODEL", default="embedding")
ENDPOINT = get_env_value("AZURE_OPENAI_ENDPOINT")
API_VERSION = get_env_value("OPENAI_API_VERSION")
API_KEY = get_env_value("AZURE_OPENAI_API_KEY")


class VectorDB:
    async def create_azure_embedding(self, text, embeddings: AzureOpenAIEmbeddings):
        try:
            input_text = text
            embedding_vector = await embeddings.aembed_query(input_text)
            return list(embedding_vector)
        except Exception as e:
            logger.error(f"Error creating embedding: {str(e)}")
        raise

    @abstractmethod
    async def ingest_data(
            self,
            texts: Iterable[str],
            metadatas: Optional[List[dict]] = None,
            ids: Optional[List[str]] = None,
            namespace: Optional[str] = None,
    ) -> List[str]:
        pass

    @abstractmethod
    async def similarity_search_with_score(
            self,
            query: str,
            filter: Optional[dict] = None,
            namespace: Optional[str] = None,
    ) -> List[Tuple[Document, float]]:
         pass

    @abstractmethod
    async def delete_namespace(self,
        namespace: Optional[str] = None):
        pass
