import asyncio
import base64
import time
from typing import Annotated

from fastapi import File, UploadFile, BackgroundTasks, Depends
from fastapi.routing import APIRouter
from pymongo.asynchronous.database import AsyncDatabase

from api.config.settings import app_settings
from api.database.connection import get_database
from api.schemas.prediction import PredictionResult, GradCamResult
from api.services.check_image import verify_image
from api.services.prediction_records import keep_prediction_photo
from src.gradcam import load_gradcam
from src.model import get_selected_model_path
from src.preprocessing import ImageProcessing
from src.prediction import classify_image, probability_details
from src.target_class import CLASS_NAMES

settings = app_settings()

router = APIRouter(
    prefix="/predict",
    tags=["Prediction"]
    )


def data_url(content: bytes, media_type: str) -> str:
    return f"data:{media_type};base64,{base64.b64encode(content).decode()}"


@router.post("/", response_model=PredictionResult, response_model_exclude_none=True)
async def prediction(background_tasks: BackgroundTasks,
                     database: Annotated[AsyncDatabase, Depends(get_database)],
                     image: UploadFile = File(...)):
    """prediction router"""
    await verify_image(file=image)
    prediction = classify_image()

    started = time.perf_counter()
    probabilities = await asyncio.to_thread(prediction.predict_probabilities, image.file)
    latency_ms = round((time.perf_counter() - started) * 1000)

    predicted_index = int(probabilities.argmax())
    predicted_class, confidence = CLASS_NAMES[predicted_index], float(probabilities[predicted_index])
    answer = {
        **prediction.build_answer(predicted_class, confidence),
        **probability_details(probabilities),
        "latency_ms": latency_ms,
    }

    await keep_prediction_photo(background_tasks, database, image.file, predicted_class,
                                confidence, answer["status"], prediction.model_name)
    return answer


@router.post("/gradcam", response_model=GradCamResult, response_model_exclude_none=True)
async def prediction_with_gradcam(background_tasks: BackgroundTasks,
                                  database: Annotated[AsyncDatabase, Depends(get_database)],
                                  image: UploadFile = File(...)):
    """
    This function predicts an image and shows what the model relied on (Grad-CAM)
    """
    await verify_image(file=image)
    prediction = classify_image()
    gradcam = load_gradcam(get_selected_model_path())

    started = time.perf_counter()
    explanation = await asyncio.to_thread(gradcam.explain, image.file, ImageProcessing(), tuple(settings.IMAGE_SIZE))
    latency_ms = round((time.perf_counter() - started) * 1000)

    answer = {
        **prediction.build_answer(explanation["predicted_class"], explanation["confidence"]),
        **probability_details(explanation["probabilities"]),
        "latency_ms": latency_ms,
    }

    await keep_prediction_photo(background_tasks, database, image.file, explanation["predicted_class"],
                                explanation["confidence"], answer["status"], prediction.model_name)
    return {
        "prediction": answer,
        "explained_class": explanation["predicted_class"],
        "photo_image": data_url(explanation["photo_jpeg"], "image/jpeg"),
        "heatmap_image": data_url(explanation["heatmap_png"], "image/png"),
    }
