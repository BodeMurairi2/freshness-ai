import asyncio
import base64
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
from src.prediction import classify_image

settings = app_settings()

router = APIRouter(
    prefix="/predict",
    tags=["Prediction"]
    )

@router.post("/", response_model=PredictionResult, response_model_exclude_none=True)
async def prediction(background_tasks: BackgroundTasks,
                     database: Annotated[AsyncDatabase, Depends(get_database)],
                     image: UploadFile = File(...)):
    """prediction router"""
    await verify_image(file=image)
    prediction = classify_image()
    predicted_class, confidence = await asyncio.to_thread(prediction.predict_top_class, image.file)
    answer = prediction.build_answer(predicted_class, confidence)

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
    explanation = await asyncio.to_thread(gradcam.explain, image.file, ImageProcessing(), tuple(settings.IMAGE_SIZE))
    answer = prediction.build_answer(explanation["predicted_class"], explanation["confidence"])

    await keep_prediction_photo(background_tasks, database, image.file, explanation["predicted_class"],
                                explanation["confidence"], answer["status"], prediction.model_name)
    return {
        "prediction": answer,
        "explained_class": explanation["predicted_class"],
        "heatmap_image": "data:image/png;base64," + base64.b64encode(explanation["heatmap_png"]).decode(),
    }
