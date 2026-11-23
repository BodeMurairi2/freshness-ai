from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.config.settings import app_settings


def cors_handler(app: FastAPI):
    """
    This function lets the frontend (another origin) call the API
    """
    settings = app_settings()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ALLOWED_ORIGINS,
        allow_methods=settings.CORS_ALLOWED_METHODS,
        allow_headers=["Authorization", "Content-Type"],
        allow_credentials=False,
    )
