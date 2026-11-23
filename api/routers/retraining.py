import asyncio
from collections import Counter
from typing import Annotated

from fastapi import HTTPException, File, UploadFile, Form, BackgroundTasks, Depends, status
from fastapi.routing import APIRouter
from pymongo.asynchronous.database import AsyncDatabase

from api.config.settings import app_settings
from api.database.connection import get_database
from api.schemas.retraining import (
    UploadResponse,
    StartedRetraining,
    RetrainingRun,
    ModelList,
    ModelPerformance,
    SelectedModel,
)
from api.services.check_image import verify_image
from api.services.model_performance import list_model_performance
from api.services.save_image import save_uploads, store_uploads_in_cloud, upload_as_json, UPLOADS_DIR
from api.services.users import get_current_user
from api.services.retrain_status import read_status, start_run_if_idle
from api.services.retrain_job import run_retraining
from src.model import list_models
from src.retraining import ModelRetrain
from src.target_class import CLASS_NAMES

settings = app_settings()

# every route here needs a logged in user
router = APIRouter(
    prefix="/retrain",
    tags=["Retrain the model with new dataset"],
    dependencies=[Depends(get_current_user)],
)

@router.post("/model", response_model=UploadResponse)
async def retrain_custom_model(database: Annotated[AsyncDatabase, Depends(get_database)],
                               current_user: Annotated[dict, Depends(get_current_user)],
                               background_tasks: BackgroundTasks,
                               images: list[UploadFile] = File(
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

    try:
        upload_documents = await save_uploads(database, images, labels, uploaded_by=current_user["email_address"])
    except Exception as error:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Could not save the images, nothing was kept: {type(error).__name__}: {error}"
        )

    # R2 runs after the response: the user does not wait for it, retraining uses the local copies
    background_tasks.add_task(store_uploads_in_cloud, database, upload_documents)

    return {
        "message": f"{len(images)} images saved for retraining",
        "images_per_class": dict(Counter(labels)),
        "uploads": [upload_as_json(upload) for upload in upload_documents],
    }


@router.post("/start", status_code=status.HTTP_202_ACCEPTED, response_model=StartedRetraining)
async def start_retraining(background_tasks: BackgroundTasks,
                           database: Annotated[AsyncDatabase, Depends(get_database)]):
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

    run_id = await start_run_if_idle(database, total_epochs=settings.RETRAIN_EPOCHS, uploaded_images=n_uploads)
    if run_id is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Retraining is already in progress. Follow it with GET /retrain/status"
        )

    background_tasks.add_task(run_retraining, run_id)
    return {"message": "Retraining started", "run_id": run_id, "uploaded_images": n_uploads}


@router.get("/status", response_model=RetrainingRun, response_model_exclude_none=True)
async def retraining_status(database: Annotated[AsyncDatabase, Depends(get_database)]):
    """
    This function shows the progress report in each epoch
    """
    return await read_status(database)


@router.get("/models/all", response_model=ModelList)
async def display_all_models():
    """Model used for predictions, the latest model, and archived models (newest first)."""
    return await asyncio.to_thread(list_models)


@router.get("/models/performance", response_model=list[ModelPerformance])
async def models_performance(database: Annotated[AsyncDatabase, Depends(get_database)]):
    """This function shows each model's training info and test set scores, newest first"""
    return await list_model_performance(database)


@router.post("/models/select", response_model=SelectedModel)
async def select_prediction_model(model_name: str = Form(..., description="e.g. freshness-ai.keras")):
    """This function chooses which model is used for predictions. No file is moved."""
    try:
        return await asyncio.to_thread(ModelRetrain().rollback_previous_model, model_name)
    except FileNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error))
