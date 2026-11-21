import math
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import tensorflow as tf
from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    roc_auc_score,
    confusion_matrix,
    classification_report,
)

from api.config.settings import app_settings
from src.target_class import CLASS_NAMES
from src.model import (
    LATEST_MODEL_DIR,
    ARCHIVE_MODEL_DIR,
    MODEL_PREFIX,
    get_latest_model_path,
    get_selected_model_path,
    select_model,
)

settings = app_settings()
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png"}
SECONDS_BETWEEN_BATCH_REPORTS = 1.0  # batch-level progress is reported at most once a second


def ignore_progress(**changes):
    """Default progress reporter: does nothing (used when retraining runs without a status page)."""


def rounded_metrics(logs: dict | None) -> dict:
    """Keras metric values as plain, rounded numbers, ready to be sent as JSON."""
    return {metric_name: round(float(metric_value), 4) for metric_name, metric_value in (logs or {}).items()}


class RetrainingProgress(tf.keras.callbacks.Callback):
    """
    Keras callback that reports what fit() is doing: current epoch, batch,
    overall progress, running metrics, and the validation results of every finished epoch.
    """

    def __init__(self, report_progress, total_epochs: int, batches_per_epoch: int):
        super().__init__()
        self.report_progress = report_progress
        self.total_epochs = total_epochs
        self.batches_per_epoch = batches_per_epoch
        self.current_epoch = 0
        self.epoch_history = []
        self.last_report_time = 0.0

    def training_percent(self, finished_batches_in_epoch: int) -> float:
        total_batches = self.total_epochs * self.batches_per_epoch
        finished_batches = (self.current_epoch - 1) * self.batches_per_epoch + finished_batches_in_epoch
        return round(100 * finished_batches / total_batches, 1)

    def on_epoch_begin(self, epoch, logs=None):
        self.current_epoch = epoch + 1
        self.report_progress(
            stage="training",
            epoch=self.current_epoch,
            batch=0,
            batches_per_epoch=self.batches_per_epoch,
            progress_percent=self.training_percent(0),
        )

    def on_train_batch_end(self, batch, logs=None):
        now = time.monotonic()
        if now - self.last_report_time < SECONDS_BETWEEN_BATCH_REPORTS:
            return
        self.last_report_time = now
        self.report_progress(
            batch=batch + 1,
            progress_percent=self.training_percent(batch + 1),
            current_metrics=rounded_metrics(logs),  # running averages over this epoch so far
        )

    def on_test_begin(self, logs=None):
        self.report_progress(stage="validating")

    def on_epoch_end(self, epoch, logs=None):
        self.epoch_history.append({"epoch": epoch + 1, **rounded_metrics(logs)})
        self.report_progress(
            batch=self.batches_per_epoch,
            progress_percent=self.training_percent(self.batches_per_epoch),
            epoch_history=self.epoch_history,
        )


class ModelRetrain:
    def __init__(self, model_path: Path | None = None):
        """
        Loads own copy of the saved model, by default the selected one
        (the model currently used for predictions)
        """
        self.model_path = Path(model_path) if model_path else get_selected_model_path()
        if not self.model_path.exists():
            raise FileNotFoundError(f"Model file not found: {self.model_path}")
        self.image_size = tuple(settings.IMAGE_SIZE)
        self.loaded_model = None

    @property
    def model(self) -> tf.keras.Model:
        """
        This helper loads the model being retrained from model_path the first time it is needed."""
        if self.loaded_model is None:
            self.loaded_model = tf.keras.models.load_model(self.model_path, compile=False)
            self.check_image_size()
        return self.loaded_model

    def check_image_size(self):
        """
        This function resize to the dimension the model was first trained
        """
        model_size = tuple(self.model.input_shape[1:3])
        if model_size != self.image_size:
            raise ValueError(
                f"IMAGE_SIZE in .env is {self.image_size} but the model expects {model_size}. "
                "Update IMAGE_SIZE or use a model trained at that size."
            )

    @staticmethod
    def count_images(folder) -> int:
        """Number of images in a class-folder dataset"""
        return sum(
            1 for image_path in Path(folder).rglob("*")
            if image_path.suffix.lower() in IMAGE_EXTENSIONS
        )

    def prepare_data(self, data: dict, batch: int = 32, seed: int = 42) -> dict:
        """
        This function loads the datasets for retraining.
        """
        n_uploads = self.count_images(data["uploads"])
        if n_uploads == 0:
            raise ValueError("No uploaded images found. Upload images before retraining.")

        common = dict(
            image_size=self.image_size,
            label_mode="categorical",
            class_names=CLASS_NAMES,
            batch_size=None,
        )
        old_train_data = tf.keras.utils.image_dataset_from_directory(data["old_train"], **common)
        upload_data = tf.keras.utils.image_dataset_from_directory(data["uploads"], **common)

        combined = (
            old_train_data.concatenate(upload_data)
            .shuffle(buffer_size=3000, seed=seed)
            .batch(batch)
            .prefetch(tf.data.AUTOTUNE)
        )
        validation_data = tf.keras.utils.image_dataset_from_directory(
            data["validation"], **common, shuffle=False
        ).batch(batch).prefetch(tf.data.AUTOTUNE)

        test_data = tf.keras.utils.image_dataset_from_directory(
            data["test"], **common, shuffle=False
        ).batch(batch).prefetch(tf.data.AUTOTUNE)

        n_training_images = self.count_images(data["old_train"]) + n_uploads
        return {
            "new_training_data": combined,
            "validation": validation_data,
            "test": test_data,
            "n_uploads": n_uploads,
            "batches_per_epoch": math.ceil(n_training_images / batch),
        }

    def compile_model(self, learning_rate: float = settings.RETRAIN_LEARNING_RATE):
        """
        This function uses the same compiles with a lower learning rate,
        updating a custom pretrained model
        """
        self.model.compile(
            optimizer=tf.keras.optimizers.Adam(learning_rate=learning_rate),
            loss=tf.keras.losses.CategoricalCrossentropy(),
            metrics=[
                "accuracy",
                tf.keras.metrics.Precision(name="Precision"),
                tf.keras.metrics.Recall(name="Recall"),
                tf.keras.metrics.F1Score(average="macro", name="F1Score"),
            ],
        )
        return self.model

    def evaluate_model(self, data, report_progress=ignore_progress) -> dict:
        """
        This function uses the same evaluation
        """
        total_batches = int(data.cardinality())
        y_true, y_pred, y_prob = [], [], []
        for batch_number, (images, labels) in enumerate(data, start=1):
            probabilities = self.model.predict(images, verbose=0)
            y_prob.extend(probabilities)
            y_pred.extend(np.argmax(probabilities, axis=1))
            y_true.extend(np.argmax(labels.numpy(), axis=1))
            report_progress(evaluated_batches=batch_number, evaluation_batches=total_batches)

        return {
            "accuracy": float(accuracy_score(y_true, y_pred)),
            "precision": float(precision_score(y_true, y_pred, average="macro", zero_division=0)),
            "recall": float(recall_score(y_true, y_pred, average="macro", zero_division=0)),
            "f1": float(f1_score(y_true, y_pred, average="macro", zero_division=0)),
            "auc_score": float(roc_auc_score(y_true, np.array(y_prob), multi_class="ovr", average="macro")),
            "confusion": confusion_matrix(y_true, y_pred, labels=range(len(CLASS_NAMES))).tolist(),
            "report": classification_report(
                y_true, y_pred, labels=range(len(CLASS_NAMES)), target_names=CLASS_NAMES,
                digits=4, zero_division=0, output_dict=True,
            ),
        }

    @staticmethod
    def replace_latest_model(new_model_path: Path) -> Path:
        """
        This function makes the new model the latest one: the previous latest model
        moves to models/archive/ under its original name, the new model goes in models/model/.
        Returns the archived path of the previous latest model.
        """
        ARCHIVE_MODEL_DIR.mkdir(parents=True, exist_ok=True)
        previous_latest_path = get_latest_model_path()
        archived_model_path = ARCHIVE_MODEL_DIR / previous_latest_path.name
        if archived_model_path.exists():
            raise FileExistsError(f"{archived_model_path.name} already exists in {ARCHIVE_MODEL_DIR}")

        final_model_name = new_model_path.name.replace(".tmp.keras", ".keras")
        new_model_path.replace(LATEST_MODEL_DIR / final_model_name)
        previous_latest_path.replace(archived_model_path)
        return archived_model_path

    def save_model(self, version: str) -> tuple[Path, Path]:
        """
        This function saves the retrained model inside models/model, archives the previous
        latest model, and selects the new model for predictions.
        """
        new_model_name = f"{MODEL_PREFIX}-{version}"
        temporary_model_path = LATEST_MODEL_DIR / f"{new_model_name}.tmp.keras"
        self.model.save(temporary_model_path)
        archived_model_path = self.replace_latest_model(temporary_model_path)
        new_model_path = select_model(new_model_name)  # predictions now use the retrained model
        return new_model_path, archived_model_path

    def retrain_model(
        self,
        data: dict,
        batch: int = 32,
        epochs: int = settings.RETRAIN_EPOCHS,
        seed: int = 42,
        report_progress=ignore_progress,
    ) -> dict:
        """
        Retrains the saved model on original and uploaded images.
        report_progress(**changes) is called at every stage, so a status page can follow along.
        """
        report_progress(stage="preparing data")
        retrain_data = self.prepare_data(data=data, batch=batch, seed=seed)

        report_progress(stage="evaluating current model", base_model=self.model_path.name)
        before = self.evaluate_model(retrain_data["test"], report_progress)

        self.compile_model()
        progress_callback = RetrainingProgress(
            report_progress,
            total_epochs=epochs,
            batches_per_epoch=retrain_data["batches_per_epoch"],
        )
        history = self.model.fit(
            retrain_data["new_training_data"],
            validation_data=retrain_data["validation"],
            epochs=epochs,
            callbacks=[progress_callback],
            verbose=2,  # one line per epoch in the server log
        )

        report_progress(stage="evaluating new model")
        after = self.evaluate_model(retrain_data["test"], report_progress)

        report_progress(stage="saving model")
        version = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        new_model_path, archived_model_path = self.save_model(version)

        return {
            "version": version,
            "model": new_model_path.name,
            "n_uploads": retrain_data["n_uploads"],
            "epochs": epochs,
            "history": {key: [float(value) for value in values] for key, values in history.history.items()},
            "before": before,
            "after": after,
            "previous_model": archived_model_path.name,
        }

    def rollback_previous_model(self, model_name: str) -> dict:
        """
        This function rollback to a previously trained model for prediction
        """
        chosen_model_path = select_model(model_name)

        self.model_path = chosen_model_path
        self.loaded_model = None
        return {
            "selected": chosen_model_path.name,
            "location": chosen_model_path.parent.name,  # "model" (latest) or "archive"
            "latest": get_latest_model_path().name,
        }
