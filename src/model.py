from pathlib import Path
from functools import lru_cache
import tensorflow as tf

MODELS_DIR = Path(__file__).resolve().parents[1] / "models"
LATEST_MODEL_DIR = MODELS_DIR / "model"      # the most recent model (only one file)
ARCHIVE_MODEL_DIR = MODELS_DIR / "archive"   # every older model, under its original name
SELECTED_MODEL_FILE = MODELS_DIR / "selected_model.txt"  # name of the model used for predictions
MODEL_PREFIX = "freshness-ai"


def list_model_files(folder: Path) -> list[Path]:
    """Model files in a folder, ignoring half-written temporary files."""
    if not folder.exists():
        return []
    return [
        model_file
        for model_file in folder.glob("*.keras")
        if not model_file.name.endswith(".tmp.keras")
    ]


def last_modified_time(model_file: Path) -> float:
    """When a model file was last written (used to sort models from oldest to newest)."""
    return model_file.stat().st_mtime


def get_latest_model_path() -> Path:
    """Path of the most recent model (the .keras file in models/model/)."""
    latest_model_files = list_model_files(LATEST_MODEL_DIR)
    if not latest_model_files:
        raise FileNotFoundError(f"No model found in {LATEST_MODEL_DIR}")
    return max(latest_model_files, key=last_modified_time)


def all_model_files() -> list[Path]:
    """Latest and archived models together, newest first."""
    every_model_file = list_model_files(LATEST_MODEL_DIR) + list_model_files(ARCHIVE_MODEL_DIR)
    return sorted(every_model_file, key=last_modified_time, reverse=True)


def find_model_path(model_name: str) -> Path:
    """
    Finds a model by name, wherever it is: models/model/ (latest) or models/archive/.
    Only the file name is used, so a request can't point outside the models folders.
    """
    clean_model_name = Path(model_name).name
    if not clean_model_name.endswith(".keras"):
        clean_model_name += ".keras"

    for folder in (LATEST_MODEL_DIR, ARCHIVE_MODEL_DIR):
        model_path = folder / clean_model_name
        if model_path.exists():
            return model_path

    available_models = [model_file.name for model_file in all_model_files()]
    raise FileNotFoundError(f"No model named {clean_model_name}. Available: {available_models}")


def get_selected_model_path() -> Path:
    """
    Path of the model used for predictions: the one chosen with select_model().
    If nothing was chosen yet (or the chosen file no longer exists), the latest model is used.
    """
    if SELECTED_MODEL_FILE.exists():
        selected_model_name = SELECTED_MODEL_FILE.read_text().strip()
        try:
            return find_model_path(selected_model_name)
        except FileNotFoundError:
            pass
    return get_latest_model_path()


def select_model(model_name: str) -> Path:
    """
    Chooses which model is used for predictions. No file is moved: only the
    chosen model's name is saved in models/selected_model.txt (kept across restarts).
    """
    chosen_model_path = find_model_path(model_name)  # raises if the model doesn't exist
    temporary_selection_file = SELECTED_MODEL_FILE.with_suffix(".tmp")
    temporary_selection_file.write_text(chosen_model_path.name)
    temporary_selection_file.replace(SELECTED_MODEL_FILE)  # never leaves a half-written file
    return chosen_model_path


def list_models() -> dict:
    """Selected, latest and archived model names (newest first), e.g. for a model dropdown."""
    archived_model_files = sorted(list_model_files(ARCHIVE_MODEL_DIR), key=last_modified_time, reverse=True)
    return {
        "selected": get_selected_model_path().name,
        "latest": get_latest_model_path().name,
        "archived": [model_file.name for model_file in archived_model_files],
    }


@lru_cache(maxsize=2)
def load_model(model_path: Path):
    """
    This function loads the CV model.
    Cached per path: when another model is selected, its path is a new cache key, so it is
    loaded on the next prediction. maxsize=2 keeps at most 2 models in memory (RAM is limited).
    """
    if not model_path.exists():
        raise FileNotFoundError(f"Model file not found: {model_path}")
    return tf.keras.models.load_model(model_path, compile=False)
