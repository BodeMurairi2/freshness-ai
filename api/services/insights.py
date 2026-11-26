
import json
from datetime import timedelta
from functools import lru_cache
from pathlib import Path

from pymongo.asynchronous.database import AsyncDatabase

from api.services.model_performance import MODELS
from api.services.prediction_records import PREDICTIONS
from api.services.retrain_status import current_time
from api.services.save_image import UPLOADS
from src.model import get_selected_model_path
from src.target_class import CLASS_NAMES

DATA_DIR = Path(__file__).resolve().parents[2] / "data"
DATASET_SPLITS = ("train", "validation", "test")
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png"}
DATASET_FEATURES_FILE = DATA_DIR / "dataset_features.json"  # scripts/compute_dataset_features.py


def condition_of(class_name: str) -> str:
    return class_name.split("_")[0]  # fresh / rotten


@lru_cache(maxsize=1)
def dataset_counts() -> dict:
    """Images per class and split, counted once (the dataset does not change while running)"""
    images_per_class = {
        class_name: {
            split: sum(1 for image_path in (DATA_DIR / split / class_name).glob("*")
                       if image_path.suffix.lower() in IMAGE_EXTENSIONS)
            for split in DATASET_SPLITS
        }
        for class_name in CLASS_NAMES
    }
    split_totals = {split: sum(counts[split] for counts in images_per_class.values()) for split in DATASET_SPLITS}
    condition_totals = {"fresh": 0, "rotten": 0}
    for class_name, counts in images_per_class.items():
        condition_totals[condition_of(class_name)] += sum(counts.values())
    return {
        "images_per_class": images_per_class,
        "split_totals": split_totals,
        "condition_totals": condition_totals,
        "total_images": sum(split_totals.values()),
    }


@lru_cache(maxsize=1)
def dataset_features() -> dict | None:
    """Visual features of the training images per class, computed once by a script"""
    if not DATASET_FEATURES_FILE.exists():
        return None
    return json.loads(DATASET_FEATURES_FILE.read_text())


async def dataset_insights(database: AsyncDatabase) -> dict:
    """
    This function adds the uploads (from MongoDB) to the fixed dataset counts
    """
    uploads = await (await database[UPLOADS].aggregate([
        {"$group": {"_id": "$label", "count": {"$sum": 1}}},
    ])).to_list()
    uploads_per_class = {upload["_id"]: upload["count"] for upload in uploads}
    return {
        **dataset_counts(),
        "features": dataset_features(),
        "uploads_per_class": uploads_per_class,
        "total_uploads": sum(uploads_per_class.values()),
    }


async def model_insights(database: AsyncDatabase) -> dict:
    """
    This function returns the selected model's test scores and every model version
    """
    selected_model = get_selected_model_path().name
    versions = await database[MODELS].find().sort("evaluated_at", 1).to_list()

    insights = {
        "selected_model": selected_model,
        "versions": [
            {
                "model": version["_id"],
                "source": version["source"],
                "parent_model": version.get("parent_model"),
                "evaluated_at": version["evaluated_at"],
                "accuracy": version["test_evaluation"]["accuracy"],
                "f1": version["test_evaluation"]["f1"],
                "errors": version["test_evaluation"]["errors"],
            }
            for version in versions
        ],
    }
    selected = next((version for version in versions if version["_id"] == selected_model), None)
    if selected is not None:
        scores = selected["test_evaluation"]
        insights.update({
            metric: scores[metric] for metric in ("accuracy", "precision", "recall", "f1", "auc_score")
        })
        insights["training"] = selected.get("training")
        # a retrained model continues from its parents: their trainings, oldest first, give the full path
        by_name = {version["_id"]: version for version in versions}
        lineage, parent_name = [], selected.get("parent_model")
        while parent_name in by_name and len(lineage) < 50:
            lineage.insert(0, by_name[parent_name].get("training"))
            parent_name = by_name[parent_name].get("parent_model")
        insights["lineage_training"] = [training for training in lineage if training]
        insights["f1_per_class"] = {
            class_name: class_scores["f1"] for class_name, class_scores in scores["per_class"].items()
        }
    return insights


async def usage_insights(database: AsyncDatabase) -> dict:
    """
    This function summarises real-world predictions in one MongoDB query
    """
    week_start = (current_time() - timedelta(days=6)).replace(hour=0, minute=0, second=0, microsecond=0)
    results = await (await database[PREDICTIONS].aggregate([
        {"$facet": {
            "totals": [{"$group": {
                "_id": None,
                "total": {"$sum": 1},
                "answered": {"$sum": {"$cond": ["$answered", 1, 0]}},
                "average_confidence": {"$avg": {"$cond": ["$answered", "$confidence", None]}},
            }}],
            "per_class": [
                {"$match": {"answered": True}},
                {"$group": {"_id": "$predicted_class", "count": {"$sum": 1}}},
            ],
            "per_day": [
                {"$match": {"created_at": {"$gte": week_start}}},
                {"$group": {"_id": {"$dateToString": {"format": "%Y-%m-%d", "date": "$created_at"}}, "count": {"$sum": 1}}},
            ],
        }},
    ])).to_list()
    facets = results[0]

    totals = facets["totals"][0] if facets["totals"] else {"total": 0, "answered": 0, "average_confidence": None}
    predictions_per_class = {item["_id"]: item["count"] for item in facets["per_class"]}
    condition_totals = {"fresh": 0, "rotten": 0}
    for class_name, count in predictions_per_class.items():
        condition_totals[condition_of(class_name)] += count

    per_day = {item["_id"]: item["count"] for item in facets["per_day"]}
    days = [(week_start + timedelta(days=offset)).strftime("%Y-%m-%d") for offset in range(7)]
    refused = totals["total"] - totals["answered"]
    average_confidence = totals["average_confidence"]
    return {
        "total_predictions": totals["total"],
        "answered": totals["answered"],
        "refused": refused,
        "refusal_rate": round(refused / totals["total"], 4) if totals["total"] else 0.0,
        "average_confidence": round(average_confidence, 4) if average_confidence is not None else None,
        "predictions_per_class": predictions_per_class,
        "condition_totals": condition_totals,
        "last_7_days": [{"day": day, "predictions": per_day.get(day, 0)} for day in days],
    }
