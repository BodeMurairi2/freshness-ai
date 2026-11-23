from pymongo import AsyncMongoClient, MongoClient
from pymongo.asynchronous.database import AsyncDatabase
from pymongo.database import Database

from api.config.settings import app_settings

settings = app_settings()

class MongoConnection:
    def __init__(self):
        self.async_client:AsyncMongoClient|None = None
        self.sync_client:MongoClient|None = None

    async def connect(self):
        """Create a new connection mongodb"""
        self.async_client = AsyncMongoClient(settings.MONGODB_URI, serverSelectionTimeoutMS=10_000, tz_aware=True)
        self.sync_client = MongoClient(settings.MONGODB_URI, serverSelectionTimeoutMS=10_000, tz_aware=True)

        await self.async_client.admin.command("ping")

    async def close(self):
        if self.async_client is not None:
            await self.async_client.close()
        if self.sync_client is not None:
            self.sync_client.close()

    @property
    def database(self) -> AsyncDatabase:
        if self.async_client is None:
            raise RuntimeError("MongoDB is not connected: was the app started with its lifespan?")
        return self.async_client[settings.MONGODB_DATABASE]

    @property
    def sync_database(self) -> Database:
        if self.sync_client is None:
            raise RuntimeError("MongoDB is not connected: was the app started with its lifespan?")
        return self.sync_client[settings.MONGODB_DATABASE]

mongo = MongoConnection()

async def get_database() -> AsyncDatabase:
    """FastAPI dependency: database connecion for all routes"""    
    return mongo.database
