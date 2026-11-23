"""
Grad-CAM: shows which parts of the image the model relied on for its prediction.
Same method as the notebook (last MobileNetV2 feature map, out_relu).
"""
import io
from functools import lru_cache
from pathlib import Path

import cv2
import numpy as np
import tensorflow as tf
from PIL import Image

from src.model import load_model
from src.preprocessing import ImageProcessing
from src.target_class import CLASS_NAMES


class GradCam:
    def __init__(self, model: tf.keras.Model):
        """
        Splits the model into the parts Grad-CAM needs: rescaling, MobileNetV2 features,
        pooling and the final dense layer (augmentation and dropout are skipped, as at inference)
        """
        self.model = model
        base = next(layer for layer in model.layers if layer.name.startswith("mobilenetv2"))
        self.conv_model = tf.keras.Model(base.inputs, base.get_layer("out_relu").output)
        self.rescale = next(layer for layer in model.layers if isinstance(layer, tf.keras.layers.Rescaling))
        self.pooling = next(layer for layer in model.layers if isinstance(layer, tf.keras.layers.GlobalAveragePooling2D))
        self.dense = model.layers[-1]

    def generate_heatmap(self, model_input, class_index: int | None = None) -> tuple[np.ndarray, int]:
        """
        This function returns the Grad-CAM heatmap (7x7, values 0-1) of one image
        for a class (the predicted one by default)
        """
        scaled_input = self.rescale(tf.convert_to_tensor(model_input[None], dtype=tf.float32))
        with tf.GradientTape() as tape:
            feature_maps = self.conv_model(scaled_input, training=False)
            tape.watch(feature_maps)
            logits = tf.matmul(self.pooling(feature_maps), self.dense.kernel) + self.dense.bias
            if class_index is None:
                class_index = int(tf.argmax(logits[0]))
            class_score = logits[:, class_index]

        gradients = tape.gradient(class_score, feature_maps)
        feature_weights = tf.reduce_mean(gradients, axis=(1, 2))
        heatmap = tf.nn.relu(tf.reduce_sum(feature_maps * feature_weights[:, None, None, :], axis=-1)[0])
        heatmap = heatmap / (tf.reduce_max(heatmap) + 1e-8)
        return heatmap.numpy(), class_index

    @staticmethod
    def overlay_heatmap(image: Image.Image, heatmap: np.ndarray, alpha: float = 0.4) -> bytes:
        """Heatmap (red = most important) drawn over the image, as PNG bytes"""
        width, height = image.size
        heatmap_resized = cv2.resize(heatmap, (width, height), interpolation=cv2.INTER_CUBIC)
        colored_heatmap = cv2.applyColorMap(np.uint8(255 * np.clip(heatmap_resized, 0, 1)), cv2.COLORMAP_JET)
        colored_heatmap = cv2.cvtColor(colored_heatmap, cv2.COLOR_BGR2RGB)
        blended = np.uint8((1 - alpha) * np.array(image) + alpha * colored_heatmap)

        buffer = io.BytesIO()
        Image.fromarray(blended).save(buffer, format="PNG", optimize=True)
        return buffer.getvalue()

    def explain(self, image_file, image_processor: ImageProcessing, image_size) -> dict:
        """
        This function predicts an image and explains the predicted class with Grad-CAM
        """
        image = image_processor.load_image(image_file)
        model_input = image_processor.to_model_input(image, image_size)
        probabilities = self.model(tf.expand_dims(model_input, axis=0), training=False).numpy()[0]
        predicted_index = int(np.argmax(probabilities))
        heatmap, _ = self.generate_heatmap(model_input, class_index=predicted_index)
        return {
            "predicted_class": CLASS_NAMES[predicted_index],
            "confidence": float(probabilities[predicted_index]),
            "heatmap_png": self.overlay_heatmap(image, heatmap),
        }


@lru_cache(maxsize=2)
def load_gradcam(model_path: Path) -> GradCam:
    """One Grad-CAM per model, built once (same cache idea as load_model)"""
    return GradCam(load_model(model_path))
