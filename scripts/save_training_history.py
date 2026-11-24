"""
Saves the notebook model's epoch-by-epoch training history in its MongoDB document,
read from the TensorBoard logs the notebook wrote (models/logs/train and models/logs/validation).

Only the newest run is used (the logs folder may hold older runs).
Usage (from the repo root):
    python scripts/save_training_history.py
    python scripts/save_training_history.py --model freshness-ai.keras --best-epoch 25
"""
import argparse
import sys
from pathlib import Path

import tensorflow as tf
from dotenv import dotenv_values
from pymongo import MongoClient
from tensorboard.backend.event_processing.event_accumulator import EventAccumulator

ROOT = Path(__file__).resolve().parent.parent
LOGS_DIR = ROOT / "models" / "logs"
NOTEBOOK_LEARNING_RATE = 1e-3
METRICS = ["loss", "accuracy", "Precision", "Recall", "F1Score", "AUC"]


def newest_run(split: str) -> dict[str, list[float]]:
    """Metric name -> value per epoch, from the newest event file of a split"""
    event_files = list((LOGS_DIR / split).glob("events.out.tfevents.*"))
    if not event_files:
        sys.exit(f"No TensorBoard logs in {LOGS_DIR / split}")
    newest = max(event_files, key=lambda path: int(path.name.split(".")[3]))  # name holds the start time
    accumulator = EventAccumulator(str(newest), size_guidance={"tensors": 0})
    accumulator.Reload()
    history = {}
    for tag in accumulator.Tags()["tensors"]:
        if tag.startswith("epoch_"):
            events = sorted(accumulator.Tensors(tag), key=lambda event: event.step)
            history[tag.removeprefix("epoch_")] = [round(float(tf.make_ndarray(event.tensor_proto)), 4) for event in events]
    return history


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--model", default="freshness-ai.keras")
    parser.add_argument("--best-epoch", type=int, help="epoch restored by early stopping (default: lowest validation loss)")
    args = parser.parse_args()

    train, validation = newest_run("train"), newest_run("validation")
    history = {metric: train[metric] for metric in METRICS if metric in train}
    history.update({f"val_{metric}": validation[metric] for metric in METRICS if metric in validation})
    if "learning_rate" in train:
        history["learning_rate"] = train["learning_rate"]

    validation_losses = history["val_loss"]
    best_epoch = args.best_epoch or validation_losses.index(min(validation_losses)) + 1
    training = {
        "epochs": len(validation_losses),
        "learning_rate": NOTEBOOK_LEARNING_RATE,
        "uploaded_images": 0,
        "best_epoch": best_epoch,
        "final_validation": {
            "loss": validation_losses[best_epoch - 1],
            "accuracy": history["val_accuracy"][best_epoch - 1],
        },
        "history": history,
    }

    environment = dotenv_values(ROOT / ".env")
    with MongoClient(environment["MONGODB_URI"]) as client:
        result = client[environment["MONGODB_DATABASE"]]["models"].update_one({"_id": args.model}, {"$set": {"training": training}})
    if result.matched_count == 0:
        sys.exit(f"No document for {args.model}: run the notebook's metadata cell first")
    print(f"Saved {len(validation_losses)} epochs for {args.model} (best epoch {best_epoch}, "
          f"val loss {training['final_validation']['loss']}, metrics: {sorted(history)})")


if __name__ == "__main__":
    main()
