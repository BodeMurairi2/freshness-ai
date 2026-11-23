from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


# ----------------------------------------------------------------- uploads
class UploadRecord(BaseModel):
    """
    One uploaded image. storage_status becomes "stored" (or "failed") once sent to R2
    """
    upload_id: str
    label: str
    original_filename: str | None = None
    storage_status: str


class UploadResponse(BaseModel):
    message: str
    images_per_class: dict[str, int]
    uploads: list[UploadRecord]


# ----------------------------------------------------------------- evaluation
class Evaluation(BaseModel):
    """
    Test set evaluation of a model, before or after retraining
    """
    accuracy: float
    precision: float
    recall: float
    f1: float
    auc_score: float
    confusion: list[list[int]]
    report: dict[str, Any]  # sklearn classification report, per class


class RetrainingResult(BaseModel):
    version: str
    model: str
    n_uploads: int
    epochs: int
    history: dict[str, list[float]]
    before: Evaluation
    after: Evaluation
    previous_model: str


class EpochResult(BaseModel):
    """
    Validation scores of one finished epoch (metric names come from Keras)
    """
    model_config = ConfigDict(extra="allow")
    epoch: int


# ----------------------------------------------------------------- runs
class StartedRetraining(BaseModel):
    message: str
    run_id: str
    uploaded_images: int


class RetrainingRun(BaseModel):
    """
    Progress of the latest retraining. Only "state" is set when nothing has run yet ("idle")
    """
    state: str  # idle, running, done, failed
    run_id: str | None = None
    stage: str | None = None
    started_at: datetime | None = None
    updated_at: datetime | None = None
    finished_at: datetime | None = None
    total_epochs: int | None = None
    uploaded_images: int | None = None
    base_model: str | None = None
    epoch: int | None = None
    batch: int | None = None
    batches_per_epoch: int | None = None
    progress_percent: float | None = None
    current_metrics: dict[str, float] | None = None
    evaluated_batches: int | None = None
    evaluation_batches: int | None = None
    epoch_history: list[EpochResult] | None = None
    result: RetrainingResult | None = None
    error: str | None = None
    performance_error: str | None = None


# ----------------------------------------------------------------- models
class ModelList(BaseModel):
    selected: str
    latest: str
    archived: list[str]


class SelectedModel(BaseModel):
    selected: str
    location: str  # "model" (latest) or "archive"
    latest: str


class ClassScores(BaseModel):
    precision: float
    recall: float
    f1: float
    support: int


class TestEvaluation(BaseModel):
    test_images: int
    accuracy: float
    precision: float
    recall: float
    f1: float
    auc_score: float
    errors: int
    per_class: dict[str, ClassScores]
    confusion_matrix: list[list[int]]


class FinalValidation(BaseModel):
    loss: float
    accuracy: float


class TrainingInfo(BaseModel):
    epochs: int
    learning_rate: float
    uploaded_images: int
    final_validation: FinalValidation


class ModelPerformance(BaseModel):
    """
    How a model was trained and how it scores on the test set
    """
    model: str
    created_at: datetime | None = None
    evaluated_at: datetime
    source: str  # notebook or retraining
    parent_model: str | None = None
    retraining_run_id: str | None = None
    image_size: list[int]
    training: TrainingInfo | None = None
    test_evaluation: TestEvaluation
