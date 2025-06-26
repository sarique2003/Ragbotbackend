# backend/container.py
from dependency_injector import containers, providers
from pymongo import MongoClient
from dotenv import load_dotenv

from dao.user_dao import UserDAO
from dao.message_dao import MessageDAO
from helpers import get_env_value
from models.vectordb_models import PineconeConfig
from services.ai_processing_service import DMAIService
from services.rag_service.pinecone import PineconeDB
from services.user_service import UserService
from services.messaging_service import MessageService
from services.vector_db_service import VectorDbService

load_dotenv()  # .env -> env vars


class ServicesContainer(containers.DeclarativeContainer):
    """Central DI container"""

    # ── config values from env ──────────────────────────────────────────
    config = providers.Configuration()
    config.mongo_uri.from_env("MONGO_URI", required=True)
    config.mongo_db_name.from_env("MONGO_DB_NAME", required=True)
    config.secret_key.from_env("SECRET_KEY", required=True)

    # ── MongoDB connection ──────────────────────────────────────────────
    mongo_client = providers.Singleton(MongoClient, config.mongo_uri)

    mongo_database = providers.Singleton(
        lambda client, db_name: client[db_name],
        client=mongo_client,
        db_name=config.mongo_db_name,
    )

    # ── MongoDB collections ─────────────────────────────────────────────
    users_collection = providers.Singleton(lambda db: db["users"], db=mongo_database)
    messages_collection = providers.Singleton(lambda db: db["messages"], db=mongo_database)
    counters_collection = providers.Singleton(lambda db: db["counters"], db=mongo_database)

    # ── DAOs ────────────────────────────────────────────────────────────
    user_dao = providers.Singleton(UserDAO,
                                   users_collection=users_collection,
                                   counters_collection=counters_collection)

    message_dao = providers.Singleton(MessageDAO,
                                      messages_collection=messages_collection,
                                      counters_collection=counters_collection)

    # ── Services ────────────────────────────────────────────────────────
    pinecone_db = providers.Singleton(
        PineconeDB,
        config=PineconeConfig(
            api_key=get_env_value('PINECONE_API_KEY'),
            base_url=get_env_value('PINECONE_URL')
        )
    )

    vectordb_service = providers.Singleton(
        VectorDbService,
        vector_db=pinecone_db
    )

    ai_processing_service = providers.Singleton(
        DMAIService,
        vector_db_service=vectordb_service
    )
    user_service = providers.Singleton(UserService,
                                       user_dao=user_dao,
                                       secret_key=config.secret_key)

    message_service = providers.Singleton(MessageService,
                                          message_dao=message_dao,
                                          user_dao=user_dao,
                                          ai_processing_service=ai_processing_service)
