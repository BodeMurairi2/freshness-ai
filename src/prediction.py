import tensorflow as tf
import numpy as np
from pathlib import Path
from src.model import load_model
from src.preprocessing import ImageProcessing
from api.config.settings import app_settings

CLASS_NAMES = [
    'fresh_apple',
    'fresh_banana',
    'fresh_grape',
    'fresh_guava',
    'fresh_jujube',
    'fresh_orange',
    'fresh_pomegranate',
    'fresh_strawberry',
    'rotten_apple',
    'rotten_banana',
    'rotten_grape',
    'rotten_guava',
    'rotten_jujube',
    'rotten_orange',
    'rotten_pomegranate',
    'rotten_strawberry'
    ]

settings = app_settings()

class Prediction:
    def __init__(self, model:tf.keras.Model, img_processor:ImageProcessing):
        self.model = model
        self.img_processing = img_processor

    def classify_image(self, image):
        """
        This function predicts and classify a unseen image
        """
        process_image = self.img_processing.process_image(file=image)
        image_ext = tf.expand_dims(process_image, axis=0)
        prediction = self.model(image_ext, training=False)
        get_arg_max = int(np.argmax(prediction[0]))
        highest_prob = float(np.max(prediction[0]))
        get_class = CLASS_NAMES[get_arg_max]

        if highest_prob < settings.DECISION_THRESHOLD:
            supported_classes = [
                classes.split("_")[1].upper()
                for classes in CLASS_NAMES
                if classes.startswith("fresh_")
                ]
            return {
                "status":False,
                "message":"Unsure about the image. It may be blurred,"
                "not containing a fruit, or an image that is not supported",
                "images_supported":supported_classes}
        return {
            "status":True,
            "fruit_name": get_class.split("_")[1],
            "fruit_condition": get_class.split("_")[0],
            "confidence": f"{highest_prob*100:.2f}%"
        }

def classify_image():
    model_path = Path(__file__).resolve().parents[1]/"models"/"model"/"freshness-ai.keras"  # src/prediction.py -> repo root
    return Prediction(
        model=load_model(model_path=model_path),
        img_processor=ImageProcessing()
        )
