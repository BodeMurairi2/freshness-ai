import uvicorn

from fastapi import FastAPI
from contextlib import asynccontextmanager

from api.config.settings import app_settings
from api.router import routing
from api.services.app_description import app_information

from api.database.connection import mongo
from api.database.indexes import create_indexes

from api.cors_handler.cors_middleware import cors_handler
@asynccontextmanager
async def lifespan(app:FastAPI):
    await mongo.connect()
    await create_indexes(mongo.database)
    yield
    await mongo.close()

settings = app_settings()

# Swagger (/docs), ReDoc (/redoc) and the OpenAPI schema are hidden unless DOCS_ENABLED=true
app = FastAPI(
    docs_url="/docs" if settings.DOCS_ENABLED else None,
    redoc_url="/redoc" if settings.DOCS_ENABLED else None,
    openapi_url="/openapi.json" if settings.DOCS_ENABLED else None,
    title=app_information["title"],
    summary=app_information["summary"],
    description=app_information["description"],
    version=app_information["version"],
    lifespan=lifespan
)

cors_handler(app=app)

@app.get("/")
async def welcome():
    return {
        "message":"Welcome to Freshnesss-ai"
    }

routing(app=app)

if __name__ == "__main__":
    uvicorn.run(
        app="api.main:app",
        port=8000,
        reload=True
    )
