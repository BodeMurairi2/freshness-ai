import asyncio
import logging
from pathlib import Path
from uuid import uuid4

from pymongo import UpdateOne
from pymongo.asynchronous.database import AsyncDatabase

from api.services.file_storage import upload_image
from api.services.retrain_status import current_time
from src.preprocessing import ImageProcessing

logger = logging.getLogger(__name__)

PROJECT_DIR = Path(__file__).resolve().parents[2]
UPLOADS_DIR = PROJECT_DIR / "data" / "uploads"
UPLOADS = "uploads"


def save_uploaded_image(image_file, label: str, image_processor: ImageProcessing) -> Path:
    """
    Converts one image to the storage format (upright, RGB, 512 px, JPEG)
    and saves it as data/uploads/<label>/<random id>.jpg
    """
    jpeg_bytes = image_processor.prepare_for_storage(image_file)
    saved_image_path = UPLOADS_DIR / label / f"{uuid4().hex}.jpg"
    saved_image_path.parent.mkdir(parents=True, exist_ok=True)
    saved_image_path.write_bytes(jpeg_bytes)
    return saved_image_path


def storage_key(saved_image_path: Path) -> str:
    """Same path in R2 as in the repo: data/uploads/<label>/<id>.jpg"""
    return saved_image_path.relative_to(PROJECT_DIR).as_posix()


def upload_to_storage(saved_image_path: Path) -> str:
    return upload_image(saved_image_path.read_bytes(), storage_key(saved_image_path))


def upload_document(saved_image_path: Path, label: str, original_filename: str | None, uploaded_by: str) -> dict:
    """Metadata of one upload. storage_url is filled once the image reaches R2"""
    return {
        "label": label,
        "path": saved_image_path.relative_to(PROJECT_DIR).as_posix(),
        "storage_key": storage_key(saved_image_path),
        "storage_url": None,
        "storage_status": "pending",
        "storage_error": None,
        "original_filename": original_filename,
        "size_bytes": saved_image_path.stat().st_size,
        "uploaded_by": uploaded_by,
        "uploaded_at": current_time(),
    }


async def save_uploads(database: AsyncDatabase, images: list, labels: list[str], uploaded_by: str) -> list[dict]:
    """
    This function saves a batch of uploads locally (used by retraining) and records them in MongoDB.
    If one step fails, the local files of the batch are removed.
    """
    image_processor = ImageProcessing()
    saved_image_paths = []
    try:
        for image, label in zip(images, labels):
            saved_image_paths.append(
                await asyncio.to_thread(save_uploaded_image, image.file, label, image_processor)
            )
        upload_documents = [
            upload_document(saved_image_path, label, image.filename, uploaded_by)
            for saved_image_path, label, image in zip(saved_image_paths, labels, images)
        ]
        await database[UPLOADS].insert_many(upload_documents)
    except Exception:
        for saved_image_path in saved_image_paths:
            saved_image_path.unlink(missing_ok=True)
        raise
    return upload_documents


async def store_uploads_in_cloud(database: AsyncDatabase, upload_documents: list[dict]):
    """
    Background task: sends a batch to R2 at the same time, then saves each public link,
    or the error if that image failed. Retraining does not wait for it (it uses the local copies).
    """
    try:
        results = await asyncio.gather(
            *(asyncio.to_thread(upload_to_storage, PROJECT_DIR / upload["path"]) for upload in upload_documents),
            return_exceptions=True,
        )
        updates = []
        for upload, result in zip(upload_documents, results):
            if isinstance(result, Exception):
                logger.warning("R2 upload failed for %s: %s", upload["path"], result)
                changes = {"storage_status": "failed", "storage_error": f"{type(result).__name__}: {result}"}
            else:
                changes = {"storage_status": "stored", "storage_url": result}
            updates.append(UpdateOne({"_id": upload["_id"]}, {"$set": changes}))
        await database[UPLOADS].bulk_write(updates, ordered=False)
    except Exception:
        # nobody waits on a background task: log it instead of losing it
        logger.exception("Could not store %d uploads in R2", len(upload_documents))


def upload_as_json(upload: dict) -> dict:
    return {
        "upload_id": str(upload["_id"]),
        "label": upload["label"],
        "original_filename": upload["original_filename"],
        "storage_status": upload["storage_status"],
    }
