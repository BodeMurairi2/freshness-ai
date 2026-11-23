from pydantic import BaseModel


class PredictionResult(BaseModel):
    """
    Answer of a prediction: the fruit and its condition, or "unsure" (status False)
    """
    status: bool
    fruit_name: str | None = None
    fruit_condition: str | None = None
    confidence: str | None = None
    message: str | None = None
    images_supported: list[str] | None = None
    model: str


class GradCamResult(BaseModel):
    """
    Prediction plus the Grad-CAM image: red areas mattered most for the explained class
    """
    prediction: PredictionResult
    explained_class: str
    heatmap_image: str  # PNG as a data URL, ready for <img src="...">
