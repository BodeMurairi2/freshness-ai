import asyncio
from fastapi import File, UploadFile
from fastapi.routing import APIRouter
from api.services.check_image import verify_image
from src.prediction import classify_image

router = APIRouter(
    prefix="/predict",
    tags=["Prediction"]
    )

@router.post("/")
async def prediction(image:UploadFile = File(...)):
    """prediction router"""
    await verify_image(file=image)
    prediction = classify_image()
    return await asyncio.to_thread(prediction.classify_image, image=image.file)
