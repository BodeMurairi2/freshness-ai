"""
Measures 3 visual features of the training images, per class, for the insights page:

  saturation    how colourful the image is (mean HSV saturation, 0-1)
  dark_share    share of dark pixels (brightness below 0.30): dark spots, bruises, mould
  brown_share   share of brown pixels (hue 10-45 degrees, mid brightness, some saturation)

Writes data/dataset_features.json, served by GET /insights.
Usage (from the repo root):  python scripts/compute_dataset_features.py
"""
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
TRAIN_DIR = ROOT / "data" / "train"
OUTPUT_FILE = ROOT / "data" / "dataset_features.json"
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png"}

DARK_BELOW = 0.30
BROWN_HUE_DEGREES = (10, 45)
BROWN_MIN_SATURATION = 0.25
BROWN_BRIGHTNESS = (0.15, 0.60)

FEATURES = {
    "saturation": {"label": "Colour saturation", "unit": "mean saturation (0-1)",
                   "description": "How colourful the photo is. Rotting fruit tends to lose its bright colour."},
    "dark_share": {"label": "Dark spots", "unit": "share of pixels darker than 30%",
                   "description": "Dark patches such as bruises, black spots or mould."},
    "brown_share": {"label": "Brown areas", "unit": "share of brown pixels",
                    "description": "Brown, decaying skin or flesh."},
}


def image_features(image_path: Path) -> dict:
    hsv = np.asarray(Image.open(image_path).convert("HSV"), dtype=np.float32)
    hue = hsv[..., 0] * 360 / 255
    saturation = hsv[..., 1] / 255
    brightness = hsv[..., 2] / 255
    brown = (
        (hue >= BROWN_HUE_DEGREES[0]) & (hue <= BROWN_HUE_DEGREES[1])
        & (saturation >= BROWN_MIN_SATURATION)
        & (brightness >= BROWN_BRIGHTNESS[0]) & (brightness <= BROWN_BRIGHTNESS[1])
    )
    return {
        "saturation": float(saturation.mean()),
        "dark_share": float((brightness < DARK_BELOW).mean()),
        "brown_share": float(brown.mean()),
    }


def main():
    per_class = {}
    for class_dir in sorted(path for path in TRAIN_DIR.iterdir() if path.is_dir()):
        image_paths = [path for path in sorted(class_dir.iterdir()) if path.suffix.lower() in IMAGE_EXTENSIONS]
        measurements = [image_features(image_path) for image_path in image_paths]
        per_class[class_dir.name] = {
            "images": len(measurements),
            **{name: round(float(np.mean([item[name] for item in measurements])), 4) for name in FEATURES},
        }
        print(f"{class_dir.name:20s} {per_class[class_dir.name]}")

    OUTPUT_FILE.write_text(json.dumps({
        "computed_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "split": "train",
        "images": sum(item["images"] for item in per_class.values()),
        "features": FEATURES,
        "per_class": per_class,
    }, indent=2))
    print(f"Saved {OUTPUT_FILE.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
