import io
import numpy as np
import tensorflow as tf
from pillow_heif import register_heif_opener
from PIL import Image, ImageOps
from api.config.settings import app_settings

IMAGE_SIZE = tuple(app_settings().IMAGE_SIZE)

STORAGE_MAX_SIDE = 512
STORAGE_JPEG_QUALITY = 90

register_heif_opener()

class ImageProcessing:
    def __init__(self):
        pass

    def process_image(self, file, image_size=IMAGE_SIZE):
        """
        This function opens and resize the file to match mobilenetv2
        """
        opened_image = ImageOps.exif_transpose(Image.open(file)).convert("RGB")
        resize_image = tf.image.resize(np.array(opened_image), image_size)
        return resize_image

    def prepare_for_storage(self, file) -> bytes:
        """
        Converts an image into the storage format
        """
        image = ImageOps.exif_transpose(Image.open(file)).convert("RGB")
        image.thumbnail((STORAGE_MAX_SIDE, STORAGE_MAX_SIDE), Image.Resampling.LANCZOS)

        buffer = io.BytesIO()
        image.save(buffer, format="JPEG", quality=STORAGE_JPEG_QUALITY, optimize=True)

        if hasattr(file, "seek"):
            file.seek(0)
        return buffer.getvalue()
