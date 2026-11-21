from pathlib import Path
from uuid import uuid4

from src.preprocessing import ImageProcessing

UPLOADS_DIR = Path(__file__).resolve().parents[2] / "data" / "uploads"


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
