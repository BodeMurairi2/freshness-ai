import tensorflow as tf
import numpy as np
from pathlib import Path
from src.model import load_model, get_selected_model_path
from src.preprocessing import ImageProcessing
from api.config.settings import app_settings
from src.target_class import CLASS_NAMES

settings = app_settings()

class Prediction:
    def __init__(self, model:tf.keras.Model, img_processor:ImageProcessing, model_name:str = ""):
        self.model = model
        self.img_processing = img_processor
        self.model_name = model_name  # shown in every response, so a model switch is visible

    def predict_top_class(self, image) -> tuple[str, float]:
        """
        This function returns the most likely class and its probability
        """
        image_size = tuple(settings.IMAGE_SIZE)
        model_size = tuple(self.model.input_shape[1:3])  # (height, width) the loaded model was built for
        if model_size != image_size:
            raise ValueError(
                f"IMAGE_SIZE in .env is {image_size} but the model expects {model_size}. "
                "Update IMAGE_SIZE or load a model trained at that size."
            )
        process_image = self.img_processing.process_image(file=image, image_size=image_size)
        image_ext = tf.expand_dims(process_image, axis=0)
        prediction = self.model(image_ext, training=False)
        get_arg_max = int(np.argmax(prediction[0]))
        highest_prob = float(np.max(prediction[0]))
        return CLASS_NAMES[get_arg_max], highest_prob

    def build_answer(self, get_class: str, highest_prob: float) -> dict:
        """
        This function turns a prediction into the answer shown to the user
        """
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
                "images_supported":supported_classes,
                "model": self.model_name}
        return {
            "status":True,
            "fruit_name": get_class.split("_")[1],
            "fruit_condition": get_class.split("_")[0],
            "confidence": f"{highest_prob*100:.2f}%",
            "model": self.model_name
        }

    def classify_image(self, image):
        """
        This function predicts and classify a unseen image
        """
        return self.build_answer(*self.predict_top_class(image))

def classify_image():
    model_path = get_selected_model_path()  # the model the user chose (latest by default)
    return Prediction(
        model=load_model(model_path=model_path),
        img_processor=ImageProcessing(),
        model_name=model_path.name
        )
