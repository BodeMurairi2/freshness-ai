"""
Stores the progress of the background retraining so the frontend can poll it.

For now the status lives in models/retrain_status.json. Everything else only uses the
functions below, so moving to MongoDB later means rewriting this file only.
"""
import json
import threading
from datetime import datetime, timezone
from pathlib import Path

STATUS_FILE = Path(__file__).resolve().parents[2] / "models" / "retrain_status.json"

# A "running" status that has not been updated for this long is treated as stuck
# (e.g. the server restarted in the middle of a retraining), so a new run can start.
STALE_AFTER_SECONDS = 10 * 60

status_lock = threading.Lock()  # one writer at a time inside this process


def current_time() -> str:
    """Current UTC time as text, e.g. 2026-11-21T14:05:09+00:00"""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def read_status() -> dict:
    """The latest retraining status, or {"state": "idle"} if nothing has run yet."""
    if not STATUS_FILE.exists():
        return {"state": "idle"}
    try:
        return json.loads(STATUS_FILE.read_text())
    except json.JSONDecodeError:
        return {"state": "idle"}


def save_status(status: dict) -> dict:
    """Writes the whole status through a temporary file, so a reader never sees half a file."""
    status["updated_at"] = current_time()
    temporary_status_file = STATUS_FILE.with_suffix(".tmp")
    temporary_status_file.write_text(json.dumps(status, indent=2))
    temporary_status_file.replace(STATUS_FILE)
    return status


def write_status(**changes) -> dict:
    """Updates some fields of the current status, e.g. write_status(stage="training", epoch=1)."""
    with status_lock:
        status = read_status()
        status.update(changes)
        return save_status(status)


def is_stale(status: dict) -> bool:
    """True if a 'running' status has not been updated for STALE_AFTER_SECONDS."""
    last_update = status.get("updated_at")
    if not last_update:
        return True
    seconds_since_update = (datetime.now(timezone.utc) - datetime.fromisoformat(last_update)).total_seconds()
    return seconds_since_update > STALE_AFTER_SECONDS


def start_run_if_idle(total_epochs: int) -> bool:
    """
    Marks a new retraining run as started, unless one is already running.
    Check and update happen under the same lock, so two clicks can't start two runs.
    Returns True if this call started the run.
    """
    with status_lock:
        status = read_status()
        if status.get("state") == "running" and not is_stale(status):
            return False
        save_status({
            "state": "running",
            "stage": "queued",
            "started_at": current_time(),
            "finished_at": None,
            "total_epochs": total_epochs,
            "progress_percent": 0,
            "epoch_history": [],
            "result": None,
            "error": None,
        })
        return True
