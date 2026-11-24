from functools import lru_cache
from pathlib import Path
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict

class AppSettings(BaseSettings):
    """
    Application base settings
    """
    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parents[2]/".env",
        case_sensitive=True,
        extra="forbid"
    )
    # CORS: frontend addresses allowed to call the API (add the deployed frontend URL later)
    CORS_ALLOWED_ORIGINS:list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]
    CORS_ALLOWED_METHODS:list[str] = ["GET", "POST", "PUT", "DELETE", "PATCH"]

    # API documentation (Swagger /docs, /redoc, /openapi.json): hidden by default
    DOCS_ENABLED:bool = False

    # Hugging face
    HF_TOKEN:Optional[str] = None

    # File extension
    IMAGE_ALLOWED_EXTENSIONS:list[str]
    IMAGE_ALLOWED_SIZE:int=10
    DECISION_THRESHOLD:float=0.6
    SAVE_PREDICTION_IMAGES:bool=True  # keep prediction photos (unlabelled) in R2 for later labelling

    # Model input size
    IMAGE_SIZE:tuple[int, int]=(224, 224)

    # Retraining
    RETRAIN_EPOCHS:int=2  # used when the user does not choose
    RETRAIN_MAX_EPOCHS:int=10  # upper limit for a user's choice (protects the server)
    RETRAIN_LEARNING_RATE:float=1e-4
    RETRAIN_MIN_IMAGES:int=10
    RETRAIN_SHUFFLE_BUFFER:int=512  # ~0.3 GB at 224x224; 3000 needs ~1.8 GB of RAM

    # Database
    MONGODB_USERNAME:str
    MONGODB_PASSWORD:str
    MONGODB_URI:str
    MONGODB_DATABASE:str

    # File storage (Cloudflare R2)
    R2_ACCOUNT_ID:str
    R2_ACCESS_KEY_ID:str
    R2_SECRET_ACCESS_KEY:str
    R2_BUCKET:str
    R2_PUBLIC_URL:str
    R2_BUCKET_JURISDICTION:Optional[str] = None  # e.g. "eu" for buckets created in the EU

    # Authentication
    JWT_SECRET_KEY:str
    JWT_EXPIRE_MINUTES:int = 60

    # Email (Gmail SMTP with an app password)
    SMTP_HOST:str = "smtp.gmail.com"
    SMTP_PORT:int = 465
    SMTP_USERNAME:str
    SMTP_APP_PASSWORD:str
    EMAIL_SENDER_NAME:str = "Freshness-ai"
    PASSWORD_CODE_MINUTES:int = 10

@lru_cache(maxsize=128)
def app_settings() -> AppSettings:
    return AppSettings()
