
import asyncio
import logging
from uuid import uuid4

from pymongo.asynchronous.database import AsyncDatabase

from api.config.settings import app_settings
from api.services.file_storage import upload_image
from api.services.retrain_status import current_time
from src.preprocessing import ImageProcessing

logger = logging.getLogger(__name__)
settings = app_settings()
PREDICTIONS = "predictions"


async def save_prediction(database: AsyncDatabase, jpeg_bytes: bytes, predicted_class: str,
                          confidence: float, answered: bool, model_name: str):
    """
    Background task: uploads the photo, then records the prediction.
    The prediction is recorded even if R2 fails, so insights stay complete
    """
    storage_key = f"data/predictions/{uuid4().hex}.jpg"
    storage_url, storage_status, storage_error = None, "stored", None
    try:
        storage_url = await asyncio.to_thread(upload_image, jpeg_bytes, storage_key)
    except Exception as error:
        logger.warning("R2 upload failed for %s: %s", storage_key, error)
        storage_status, storage_error = "failed", f"{type(error).__name__}: {error}"

    try:
        await database[PREDICTIONS].insert_one({
            "storage_key": storage_key,
            "storage_url": storage_url,
            "storage_status": storage_status,
            "storage_error": storage_error,
            "predicted_class": predicted_class,
            "confidence": round(confidence, 4),
            "answered": answered,  # False when refused (below the decision threshold)
            "model": model_name,
            "label": None,  # set later by a person: may be a supported class or not (tomato, mango...)
            "created_at": current_time(),
        })
    except Exception:
        logger.exception("Could not record the prediction %s", storage_key)


async def keep_prediction_photo(background_tasks, database: AsyncDatabase, image_file, predicted_class: str,
                                confidence: float, answered: bool, model_name: str):
    """
    Prepares the photo now (the upload is closed after the response)
    and saves it in the background, so the user does not wait
    """
    if not settings.SAVE_PREDICTION_IMAGES:
        return
    image_file.seek(0)
    jpeg_bytes = await asyncio.to_thread(ImageProcessing().prepare_for_storage, image_file)
    background_tasks.add_task(save_prediction, database, jpeg_bytes, predicted_class, confidence, answered, model_name)
