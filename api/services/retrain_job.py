"""
The retraining job that runs in the background after POST /retrain/start.
"""
from pathlib import Path

from api.services.retrain_status import write_status, current_time
from api.services.save_image import UPLOADS_DIR
from src.retraining import ModelRetrain

DATA_DIR = Path(__file__).resolve().parents[2] / "data"

RETRAIN_DATA_FOLDERS = {
    "old_train": DATA_DIR / "train",
    "uploads": UPLOADS_DIR,
    "validation": DATA_DIR / "validation",
    "test": DATA_DIR / "test",
}


def run_retraining():
    """
    Retrains the selected model on the original + uploaded images, reporting progress
    to the status store. A plain `def` (not async): FastAPI runs it in a worker thread,
    so predictions keep working while it trains.
    Errors are caught and stored, because nobody is waiting on this function to see them.
    """
    try:
        retrainer = ModelRetrain()
        result = retrainer.retrain_model(data=RETRAIN_DATA_FOLDERS, report_progress=write_status)
        write_status(
            state="done",
            stage="finished",
            progress_percent=100,
            finished_at=current_time(),
            result=result,
        )
    except Exception as error:
        write_status(
            state="failed",
            stage="failed",
            finished_at=current_time(),
            error=f"{type(error).__name__}: {error}",
        )
