import numpy as np
import tensorflow as tf
from pillow_heif import register_heif_opener
from PIL import Image, ImageOps

IMAGE_SIZE = (222, 224)

register_heif_opener()

class ImageProcessing:
    def __init__(self):
        pass

    def process_image(self, file):
        """
        This function opens the image
        """
        opened_image = ImageOps.exif_transpose(Image.open(file)).convert("RGB")
        resize_image = tf.image.resize(np.array(opened_image), IMAGE_SIZE)
        return resize_image
