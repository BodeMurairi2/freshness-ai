from pydantic import BaseModel


class ClassProbability(BaseModel):
    class_name: str  # e.g. fresh_banana
    fruit_name: str
    fruit_condition: str  # fresh / rotten
    probability: float  # 0-1


class PredictionResult(BaseModel):
    """
    Answer of a prediction: the fruit, its condition and confidence.
    status False means uncertain (confidence below the decision threshold).
    top_classes holds the 3 most likely classes (best first), shown on demand
    """
    status: bool
    fruit_name: str | None = None
    fruit_condition: str | None = None
    confidence: str | None = None
    message: str | None = None
    images_supported: list[str] | None = None
    model: str
    top_classes: list[ClassProbability] | None = None
    fresh_probability: float | None = None
    rotten_probability: float | None = None
    latency_ms: int | None = None


class GradCamResult(BaseModel):
    """
    Prediction plus Grad-CAM: show heatmap_image over photo_image with any opacity.
    Red areas mattered most for the explained class
    """
    prediction: PredictionResult
    explained_class: str
    photo_image: str  # JPEG data URL, the photo the model saw (512 px)
    heatmap_image: str  # PNG data URL, same size as the photo
