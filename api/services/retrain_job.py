"""
The retraining job that runs in the background after POST /retrain/start.
"""
from functools import partial
from pathlib import Path

from api.services.model_performance import save_model_performance
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


def run_retraining(run_id: str):
    """
    Retrains the selected model and reports progress to the run document.
    A plain def: FastAPI runs it in a worker thread, so predictions keep working.
    Errors are stored in the run, since nobody is waiting on this function.
    """
    report_progress = partial(write_status, run_id)
    try:
        retrainer = ModelRetrain()
        base_model_name = retrainer.model_path.name
        result = retrainer.retrain_model(data=RETRAIN_DATA_FOLDERS, report_progress=report_progress)
    except Exception as error:
        report_progress(
            state="failed",
            stage="failed",
            finished_at=current_time(),
            error=f"{type(error).__name__}: {error}",
        )
        return

    # the model is already saved here: a database error should not mark the run as failed
    performance_error = None
    try:
        save_model_performance(run_id, base_model_name, result)
    except Exception as error:
        performance_error = f"{type(error).__name__}: {error}"

    report_progress(
        state="done",
        stage="finished",
        progress_percent=100,
        finished_at=current_time(),
        result=result,
        performance_error=performance_error,
    )
