"""
Exports the figures of the original model's notebook (notebook/freshness_ai.ipynb) as WebP images
for the frontend: freshness_frontend/public/notebook/, plus figures.json describing them.

The figures are found by the code that draws them, so the script keeps working if cells move.
Usage (from the repo root):  python scripts/export_notebook_figures.py
"""
import base64
import io
import json
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))  # so `src` can be imported when run as a script

from src.target_class import CLASS_NAMES  # noqa: E402

NOTEBOOK = ROOT / "notebook" / "freshness_ai.ipynb"
OUTPUT_DIR = ROOT / "freshness_frontend" / "public" / "notebook"
WEBP_QUALITY = 82

# (code that draws the figure, file name, title, caption)
FIGURES = [
    ("def plot_history(", "training-history", "Training history",
     "Training and validation loss, accuracy, precision, recall and F1 for each epoch, with the learning rate. "
     "The dashed line marks epoch 25, whose weights were kept by early stopping."),
    ("ConfusionMatrixDisplay(", "confusion-matrix", "Confusion matrix (test set)",
     "Predictions on the 640 test images. The diagonal holds the correct answers; everything else is a mistake."),
    ("OUTCOME_COLORS = {", "decision-threshold", "Decision threshold",
     "Top-class confidence on the validation set, used to choose the 75% threshold below which an answer is marked as uncertain."),
    ("fig, axes = plt.subplots(1, 3, figsize=(18, 5))", "class-distribution", "Class distribution",
     "Number of images per class in the training, validation and test splits."),
    ("fig, axes = plt.subplots(3, 3, figsize=(15, 15))", "dataset-samples", "Dataset samples",
     "Nine random photos from the dataset."),
]
GRADCAM_CODE = "generate_gradcam(image=image.numpy()"


def figure_images(cell: dict) -> list[bytes]:
    return [base64.b64decode(output["data"]["image/png"])
            for output in cell.get("outputs", []) if "image/png" in output.get("data", {})]


def save_webp(png_bytes: bytes, name: str) -> dict:
    image = Image.open(io.BytesIO(png_bytes)).convert("RGB")
    path = OUTPUT_DIR / f"{name}.webp"
    image.save(path, format="WEBP", quality=WEBP_QUALITY, method=6)
    return {"file": f"/notebook/{name}.webp", "width": image.width, "height": image.height}


def main():
    cells = [cell for cell in json.loads(NOTEBOOK.read_text())["cells"] if cell["cell_type"] == "code"]
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for old_file in OUTPUT_DIR.glob("*.webp"):
        old_file.unlink()

    figures = []
    for code, name, title, caption in FIGURES:
        cell = next((cell for cell in cells if code in "".join(cell["source"]) and figure_images(cell)), None)
        if cell is None:
            print(f"  not found (no output): {title}")
            continue
        figures.append({"name": name, "title": title, "caption": caption, **save_webp(figure_images(cell)[0], name)})
        print(f"  saved {name}.webp")

    gradcam = []
    gradcam_cell = next((cell for cell in cells if GRADCAM_CODE in "".join(cell["source"])), None)
    if gradcam_cell:
        # the test set is read in class order, so the n-th figure explains the n-th class
        for class_name, png_bytes in zip(CLASS_NAMES, figure_images(gradcam_cell)):
            gradcam.append({"class_name": class_name, **save_webp(png_bytes, f"gradcam-{class_name}")})
        print(f"  saved {len(gradcam)} Grad-CAM figures")

    (OUTPUT_DIR / "figures.json").write_text(json.dumps({
        "model": "freshness-ai.keras",
        "notebook": "notebook/freshness_ai.ipynb",
        "figures": figures,
        "gradcam": gradcam,
    }, indent=2))
    total = sum(path.stat().st_size for path in OUTPUT_DIR.glob("*.webp")) // 1024
    print(f"Exported {len(figures)} figures and {len(gradcam)} Grad-CAM images ({total} KB) to {OUTPUT_DIR.relative_to(ROOT)}/")


if __name__ == "__main__":
    main()
