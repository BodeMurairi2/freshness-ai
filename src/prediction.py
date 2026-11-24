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

    def predict_probabilities(self, image) -> np.ndarray:
        """
        This function returns the probability of each of the 16 classes
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
        return self.model(image_ext, training=False).numpy()[0]

    def predict_top_class(self, image) -> tuple[str, float]:
        """
        This function returns the most likely class and its probability
        """
        probabilities = self.predict_probabilities(image)
        get_arg_max = int(np.argmax(probabilities))
        return CLASS_NAMES[get_arg_max], float(probabilities[get_arg_max])

    def build_answer(self, get_class: str, highest_prob: float) -> dict:
        """
        This function turns a prediction into the answer shown to the user
        """
        answer = {
            "status": True,
            "fruit_name": get_class.split("_")[1],
            "fruit_condition": get_class.split("_")[0],
            "confidence": f"{highest_prob*100:.2f}%",
            "model": self.model_name,
        }
        # below the threshold the class is still given, but marked as uncertain (status False)
        if highest_prob < settings.DECISION_THRESHOLD:
            supported_classes = [
                classes.split("_")[1].upper()
                for classes in CLASS_NAMES
                if classes.startswith("fresh_")
                ]
            answer.update({
                "status": False,
                "message": "Uncertain prediction: the image may be blurred, "
                "show a cut fruit, or a fruit that is not supported",
                "images_supported": supported_classes,
            })
        return answer

    def classify_image(self, image):
        """
        This function predicts and classify a unseen image
        """
        return self.build_answer(*self.predict_top_class(image))

def probability_details(probabilities: np.ndarray, top: int = 3) -> dict:
    """
    The most likely classes (best first) and the total probability of fresh vs rotten
    """
    best_indexes = np.argsort(probabilities)[::-1][:top]
    rotten_probability = float(sum(
        probabilities[index] for index, class_name in enumerate(CLASS_NAMES) if class_name.startswith("rotten_")
    ))
    return {
        "top_classes": [
            {
                "class_name": CLASS_NAMES[index],
                "fruit_name": CLASS_NAMES[index].split("_")[1],
                "fruit_condition": CLASS_NAMES[index].split("_")[0],
                "probability": round(float(probabilities[index]), 4),
            }
            for index in best_indexes
        ],
        "fresh_probability": round(1 - rotten_probability, 4),
        "rotten_probability": round(rotten_probability, 4),
    }


def classify_image():
    model_path = get_selected_model_path()  # the model the user chose (latest by default)
    return Prediction(
        model=load_model(model_path=model_path),
        img_processor=ImageProcessing(),
        model_name=model_path.name
        )
