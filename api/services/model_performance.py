from bson import ObjectId

from api.config.settings import app_settings
from api.database.connection import mongo
from api.services.retrain_status import current_time
from src.model import MODEL_PREFIX
from src.target_class import CLASS_NAMES

settings = app_settings()
MODELS = "models"


def test_evaluation(evaluation: dict) -> dict:
    """Metrics, error count and per-class scores from an evaluate_model() result"""
    confusion = evaluation["confusion"]
    test_images = sum(sum(row) for row in confusion)
    correct_predictions = sum(confusion[index][index] for index in range(len(confusion)))
    return {
        "test_images": test_images,
        "accuracy": evaluation["accuracy"],
        "precision": evaluation["precision"],
        "recall": evaluation["recall"],
        "f1": evaluation["f1"],
        "auc_score": evaluation["auc_score"],
        "errors": test_images - correct_predictions,
        "per_class": {
            class_name: {
                "precision": evaluation["report"][class_name]["precision"],
                "recall": evaluation["report"][class_name]["recall"],
                "f1": evaluation["report"][class_name]["f1-score"],
                "support": int(evaluation["report"][class_name]["support"]),
            }
            for class_name in CLASS_NAMES
        },
        "confusion_matrix": confusion,
    }


def save_model_performance(run_id: str, base_model_name: str, result: dict):
    """
    This function saves the retrained model document, and the base model
    document if it has none yet (e.g. the notebook model, the first time it is retrained)
    """
    models = mongo.sync_database[MODELS]
    now = current_time()

    models.update_one(
        {"_id": base_model_name},
        {"$setOnInsert": {
            "created_at": None,  # trained outside the app
            "evaluated_at": now,
            "source": "notebook" if base_model_name == f"{MODEL_PREFIX}.keras" else "unknown",
            "parent_model": None,
            "retraining_run_id": None,
            "image_size": list(settings.IMAGE_SIZE),
            "training": None,
            "test_evaluation": test_evaluation(result["before"]),
        }},
        upsert=True,
    )

    history = result["history"]
    models.insert_one({
        "_id": result["model"],
        "created_at": now,
        "evaluated_at": now,
        "source": "retraining",
        "parent_model": base_model_name,
        "retraining_run_id": ObjectId(run_id),
        "image_size": list(settings.IMAGE_SIZE),
        "training": {
            "epochs": result["epochs"],
            "learning_rate": settings.RETRAIN_LEARNING_RATE,
            "uploaded_images": result["n_uploads"],
            "final_validation": {
                "loss": history["val_loss"][-1],
                "accuracy": history["val_accuracy"][-1],
            },
            "best_epoch": len(history["val_loss"]),  # no early stopping: the last epoch is kept
            "history": {metric: [round(value, 4) for value in values] for metric, values in history.items()},
        },
        "test_evaluation": test_evaluation(result["after"]),
    })


async def list_model_performance(database) -> list[dict]:
    """Every model's training info and test scores, newest first"""
    model_documents = await database[MODELS].find().sort("evaluated_at", -1).to_list()
    for model_document in model_documents:
        model_document["model"] = model_document.pop("_id")
        if model_document.get("retraining_run_id") is not None:
            model_document["retraining_run_id"] = str(model_document["retraining_run_id"])
    return model_documents
