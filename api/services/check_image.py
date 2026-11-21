from pathlib import Path
from PIL import Image
from pillow_heif import register_heif_opener
from fastapi import UploadFile, HTTPException, status
from api.config.settings import app_settings

register_heif_opener()

async def verify_image(file:UploadFile):
    """
    This function runs quick verification on the image
    and validate
    """
    file_ext = Path(file.filename).suffix.lower()
    image_file = file.file 
    settings = app_settings()
    allowed_size = int(settings.IMAGE_ALLOWED_SIZE) * 1024*1024
    
    if file_ext not in settings.IMAGE_ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File image extension not allowed. Allowed extension:\n{settings.IMAGE_ALLOWED_EXTENSIONS}"
        )
    
    if file.size > allowed_size or file.size == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File size shoud not be greater than {settings.IMAGE_ALLOWED_SIZE} or empty"
        )

    try:
        Image.open(image_file).verify()
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not open the file. File may be corrupted or not an image"
        )
    finally:
        image_file.seek(0)
