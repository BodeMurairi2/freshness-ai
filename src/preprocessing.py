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

    def load_image(self, file) -> Image.Image:
        """
        Opens an image upright, in RGB, with its longest side reduced to 512 px
        (the same path the training images took)
        """
        opened_image = ImageOps.exif_transpose(Image.open(file)).convert("RGB")
        opened_image.thumbnail((STORAGE_MAX_SIDE, STORAGE_MAX_SIDE), Image.Resampling.LANCZOS)
        return opened_image

    def to_model_input(self, image: Image.Image, image_size=IMAGE_SIZE):
        return tf.image.resize(np.array(image), image_size)

    def process_image(self, file, image_size=IMAGE_SIZE):
        """
        This function opens and resize the file to match mobilenetv2
        """
        return self.to_model_input(self.load_image(file), image_size)

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
