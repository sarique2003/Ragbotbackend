import logging
import uuid
import aiohttp
from typing import Iterable, List, Optional, Tuple
from langchain.docstore.document import Document
from langchain_openai import AzureOpenAIEmbeddings

from services.rag_service.base_vector_db import VectorDB
from models.vectordb_models import PineconeConfig

from helpers import get_env_value

logger = logging.getLogger(__name__)
DEFAULT_OPENAI_EMBEDDING_MODEL = "text-embedding-ada-002"
AZURE_EMBEDDING_MODEL = get_env_value("AZURE_OPENAI_EMBEDDING_MODEL", default="embedding")
ENDPOINT = get_env_value("AZURE_OPENAI_ENDPOINT")
API_VERSION = get_env_value("OPENAI_API_VERSION")
API_KEY = get_env_value("AZURE_OPENAI_API_KEY")


class PineconeDB(VectorDB):
    def __init__(self, config: PineconeConfig, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.config = config
        self._text_key = "text"
        self.embeddings = AzureOpenAIEmbeddings(
            model=AZURE_EMBEDDING_MODEL,
            azure_endpoint=ENDPOINT,
            api_key=API_KEY,
            openai_api_version=API_VERSION
        )

    def _get_headers(self) -> dict:
        """Generate common headers for all HTTP requests."""
        return {
            "Api-Key": self.config.api_key,
            "Content-Type": "application/json"
        }

    async def _post(self, endpoint: str, payload: dict) -> dict:
        """
        Send a POST request to a given endpoint on the Pinecone service.
        Automatically checks for unauthorized responses and returns JSON.
        """
        url = f"{self.config.base_url}/{endpoint}"
        headers = self._get_headers()
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=payload) as response:
                logger.debug(f"POST {url} returned status {response.status}")
                if response.status == 401:
                    raise Exception("Unauthorized: Check your API key and URL.")
                try:
                    return await response.json()
                except aiohttp.ContentTypeError:
                    # In some cases, a non-JSON response might be acceptable.
                    return {}
        await session.close()

    async def delete_namespace(self, namespace: Optional[str] = None) -> None:
        """
        Deletes the specified namespace.
        """
        payload = {
            "deleteAll": True,
            "namespace": namespace,
        }
        headers = self._get_headers()
        # POST request to delete vectors and the namespace
        async with aiohttp.ClientSession() as session:
            delete_url = f"{self.config.base_url}/vectors/delete"
            async with session.post(delete_url, headers=headers, json=payload) as response:
                if response.status == 200:
                    logger.info(f"Namespace '{namespace}' has been successfully deleted.")
                else:
                    error_msg = await response.text()
                    logger.error(f"Failed to delete namespace '{namespace}'. Response: {error_msg}")
                    raise Exception(f"Namespace deletion failed with status {response.status}")
        await session.close()

    async def ingest_data(
            self,
            texts: Iterable[str],
            metadatas: Optional[List[dict]] = None,
            ids: Optional[List[str]] = None,
            namespace: Optional[str] = None,
    ) -> List[str]:
        """
        Process texts into embeddings and upsert them into Pinecone.
        """
        # Clear the namespace before adding new vectors.
        docs = []
        ids = ids or [str(uuid.uuid4()) for _ in texts]

        for i, text in enumerate(texts):
            embedding = await self.create_azure_embedding(text, embeddings=self.embeddings)
            metadata = metadatas[i] if metadatas else {}
            metadata[self._text_key] = text
            docs.append({"id": ids[i], "values": embedding, "metadata": metadata})

        logger.info("Embeddings are created!")
        batch_size = 100

        upserted_ids: list[str] = []
        for i in range(0, len(docs), batch_size):
            batch: list[dict[str, str]] = docs[i:i + batch_size]
            payload: dict = {
                "vectors": batch,
                "namespace": namespace
            }
            try:
                response_json: dict = await self._post("vectors/upsert", payload)
                if "message" in response_json:
                    logger.error(f"Error upserting vectors: {response_json}")
                else:
                    upserted_ids.extend([doc["id"] for doc in batch])
            except Exception as e:
                logger.error(f"Error upserting batch {i // batch_size + 1}: {e}")

        return upserted_ids

    async def similarity_search_with_score(
            self,
            query: str,
            filter: Optional[dict] = None,
            namespace: Optional[str] = None,
    ) -> List[Tuple[Document, float]]:
        """
        Return Pinecone documents most similar to the query, along with scores.
        """

        query_obj = await self.create_azure_embedding(query, embeddings=self.embeddings)
        payload = {
            "top_k": self.config.top_k,
            "namespace": namespace,
            "filter": filter,
            "vector": query_obj,
            "includeMetadata": True,
        }
        results = await self._post("query", payload)

        docs = []
        for res in results.get("matches", []):
            metadata = res.get("metadata", {})
            if self._text_key in metadata:
                text = metadata.pop(self._text_key)
                score = res.get("score", 0)
                docs.append((Document(page_content=text, metadata=metadata), score))
            else:
                logger.warning(f"Found document with no `{self._text_key}` key. Skipping.")
        logger.debug(f"Found docs in the vector db: {docs}")
        return docs
