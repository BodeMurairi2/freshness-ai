from datetime import datetime

from pydantic import BaseModel

from api.schemas.retraining import TrainingInfo


class FeatureDescription(BaseModel):
    label: str
    unit: str
    description: str


class DatasetFeatures(BaseModel):
    """
    Visual features of the training images, averaged per class
    """
    computed_at: str
    split: str
    images: int
    features: dict[str, FeatureDescription]  # saturation, dark_share, brown_share
    per_class: dict[str, dict[str, float]]  # class -> {"images": n, "saturation": x, ...}


class DatasetInsights(BaseModel):
    """
    Images per class in each split, and how the dataset grows through uploads
    """
    images_per_class: dict[str, dict[str, int]]  # class -> {"train": n, "validation": n, "test": n}
    split_totals: dict[str, int]
    condition_totals: dict[str, int]  # fresh / rotten
    total_images: int
    features: DatasetFeatures | None = None
    uploads_per_class: dict[str, int]
    total_uploads: int


class ModelVersion(BaseModel):
    model: str
    source: str
    parent_model: str | None = None
    evaluated_at: datetime
    accuracy: float
    f1: float
    errors: int


class ModelInsights(BaseModel):
    """
    Scores of the model used for predictions, and every model version
    """
    selected_model: str
    accuracy: float | None = None
    precision: float | None = None
    recall: float | None = None
    f1: float | None = None
    auc_score: float | None = None
    f1_per_class: dict[str, float] | None = None
    training: TrainingInfo | None = None  # how the model was trained, epoch by epoch
    lineage_training: list[TrainingInfo] = []  # for a retrained model: its parents' trainings, oldest first
    versions: list[ModelVersion]


class DailyPredictions(BaseModel):
    day: str  # YYYY-MM-DD
    predictions: int


class UsageInsights(BaseModel):
    """
    How the app is used on real photos
    """
    total_predictions: int
    answered: int
    refused: int
    refusal_rate: float
    average_confidence: float | None = None  # answered predictions only
    predictions_per_class: dict[str, int]  # answered predictions only
    condition_totals: dict[str, int]  # fresh / rotten, answered only
    last_7_days: list[DailyPredictions]


class Insights(BaseModel):
    dataset: DatasetInsights
    model: ModelInsights
    usage: UsageInsights
