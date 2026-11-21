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

@lru_cache(maxsize=128)
def app_settings() -> AppSettings:
    return AppSettings()
