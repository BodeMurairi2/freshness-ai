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
    # Hugging face
    HF_TOKEN:Optional[str] = None

    # File extension
    IMAGE_ALLOWED_EXTENSIONS:list[str]
    IMAGE_ALLOWED_SIZE:int=10
    DECISION_THRESHOLD:float=0.6

    # Model input size
    IMAGE_SIZE:tuple[int, int]=(224, 224)

    # Retraining
    RETRAIN_EPOCHS:int=2
    RETRAIN_LEARNING_RATE:float=1e-4
    RETRAIN_MIN_IMAGES:int=10  # uploads needed before retraining can start

@lru_cache(maxsize=128)
def app_settings() -> AppSettings:
    return AppSettings()
