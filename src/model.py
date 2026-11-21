from pathlib import Path
from functools import lru_cache
import tensorflow as tf

@lru_cache(maxsize=1)
def load_model(model_path:Path):
    """
    This function loads the CV model
    """
    if not model_path.exists():
        raise FileNotFoundError(f"Model file not found")
    return tf.keras.models.load_model(model_path, compile=False)
