import asyncio
from collections import Counter

from fastapi import HTTPException, File, UploadFile, Form, BackgroundTasks, status
from fastapi.routing import APIRouter

from api.config.settings import app_settings
from api.services.check_image import verify_image
from api.services.save_image import save_uploaded_image, UPLOADS_DIR
from api.services.retrain_status import read_status, start_run_if_idle
from api.services.retrain_job import run_retraining
from src.model import list_models
from src.preprocessing import ImageProcessing
from src.retraining import ModelRetrain
from src.target_class import CLASS_NAMES

settings = app_settings()

router = APIRouter(
    prefix="/retrain",
    tags=["Retrain the model with new dataset"]
)

@router.post("/model")
async def retrain_custom_model(images: list[UploadFile] = File(
                                   ...,
                                   json_schema_extra={"items": {"type": "string", "format": "binary"}},
                               ),
                               labels: list[str] = Form(...)):
    """
    This function uploads labelled images for retraining, all classes in one request.
    The frontend repeats each group's class name once per image.
    """
    labels = [
        single_label.strip()
        for label in labels
        for single_label in label.split(",")
        if single_label.strip()
    ]

    if len(images) != len(labels):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Got {len(images)} images but {len(labels)} labels: each image needs exactly one label"
        )

    unknown_labels = sorted(set(labels) - set(CLASS_NAMES))
    if unknown_labels:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown labels: {unknown_labels}. Allowed labels: {CLASS_NAMES}"
        )

    for image in images:
        try:
            await verify_image(file=image)
        except HTTPException as error:
            raise HTTPException(
                status_code=error.status_code,
                detail=f"{image.filename}: {error.detail}"
            )

    image_processor = ImageProcessing()
    for image, label in zip(images, labels):
        await asyncio.to_thread(save_uploaded_image, image.file, label, image_processor)

    return {
        "message": f"{len(images)} images saved for retraining",
        "images_per_class": dict(Counter(labels)),
    }


@router.post("/start", status_code=status.HTTP_202_ACCEPTED)
async def start_retraining(background_tasks: BackgroundTasks):
    """
    This function retrain button starts retraining in the background and answers immediately.
    Follow the progress with GET /retrain/status.
    """
    n_uploads = ModelRetrain.count_images(UPLOADS_DIR)
    if n_uploads < settings.RETRAIN_MIN_IMAGES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Upload at least {settings.RETRAIN_MIN_IMAGES} images before retraining "
                   f"({n_uploads} uploaded so far)"
        )

    if not start_run_if_idle(total_epochs=settings.RETRAIN_EPOCHS):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Retraining is already in progress. Follow it with GET /retrain/status"
        )

    background_tasks.add_task(run_retraining)
    return {"message": "Retraining started", "uploaded_images": n_uploads, "status": read_status()}


@router.get("/status")
async def retraining_status():
    """
    This function shows the progress report in each epoch
    """
    return read_status()


@router.get("/models/all")
async def display_all_models():
    """Model used for predictions, the latest model, and archived models (newest first)."""
    return await asyncio.to_thread(list_models)


@router.post("/models/select")
async def select_prediction_model(model_name: str = Form(..., description="e.g. freshness-ai.keras")):
    """This function chooses which model is used for predictions. No file is moved."""
    try:
        return await asyncio.to_thread(ModelRetrain().rollback_previous_model, model_name)
    except FileNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error))
