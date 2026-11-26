from datetime import datetime, timedelta, timezone

from bson import ObjectId
from pymongo.asynchronous.database import AsyncDatabase
from pymongo.errors import DuplicateKeyError

from api.database.connection import mongo

RETRAINING_RUNS = "retraining_runs"

STALE_AFTER = timedelta(minutes=10)


def current_time() -> datetime:
    return datetime.now(timezone.utc)


def run_as_json(run: dict) -> dict:
    """Replaces the ObjectId (not JSON friendly) with a run_id string"""
    run_id = str(run.pop("_id"))
    return {"run_id": run_id, **run}


async def read_status(database: AsyncDatabase) -> dict:
    """Latest retraining run, or {"state": "idle"} if nothing has run yet"""
    latest_run = await database[RETRAINING_RUNS].find_one(sort=[("started_at", -1)])
    if latest_run is None:
        return {"state": "idle"}
    return run_as_json(latest_run)


async def start_run_if_idle(database: AsyncDatabase, total_epochs: int, uploaded_images: int) -> str | None:
    """
    This function creates a new run unless one is already running.
    Returns the run id, or None if a run is in progress.
    """
    runs = database[RETRAINING_RUNS]
    now = current_time()

    await runs.update_many(
        {"state": "running", "updated_at": {"$lt": now - STALE_AFTER}},
        {"$set": {
            "state": "failed",
            "stage": "failed",
            "finished_at": now,
            "error": "No progress for 10 minutes: the server probably restarted during retraining",
        }},
    )

    try:
        new_run = await runs.insert_one({
            "state": "running",
            "stage": "queued",
            "started_at": now,
            "updated_at": now,
            "finished_at": None,
            "total_epochs": total_epochs,
            "uploaded_images": uploaded_images,
            "progress_percent": 0,
            "epoch_history": [],
            "result": None,
            "error": None,
        })
    except DuplicateKeyError:
        return None
    return str(new_run.inserted_id)


def write_status(run_id: str, **changes):
    """
    Updates some fields of a run
    """
    mongo.sync_database[RETRAINING_RUNS].update_one(
        {"_id": ObjectId(run_id)},
        {"$set": {**changes, "updated_at": current_time()}},
    )
