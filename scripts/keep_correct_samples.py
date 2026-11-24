"""
Cleans data/samples/ (the photos for retraining demos, from scripts/download_samples.py):

  - keeps only the photos the current model classifies correctly (right fruit AND condition),
    so the labels coming from other datasets agree with this project's classes;
  - removes copies of training images (grape: no public dataset exists), because the model
    has already learned from them and they add nothing to a retraining.

Kept photos are renumbered 1..n per class, and data/samples/SOURCES.csv is rewritten.
Usage (from the repo root):  python scripts/keep_correct_samples.py
"""
import csv
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))  # so `src` can be imported when run as a script

from src.prediction import classify_image  # noqa: E402
from src.target_class import CLASS_NAMES  # noqa: E402

SAMPLES_DIR = ROOT / "data" / "samples"
SOURCES_FILE = SAMPLES_DIR / "SOURCES.csv"
TRAINING_COPY_SOURCE = "Copy of data/train"


def main():
    predictor = classify_image()
    sources = {row["file"]: row for row in csv.DictReader(open(SOURCES_FILE))}
    kept_rows, counts = [], defaultdict(lambda: [0, 0])  # class -> [kept, total]

    for class_dir in sorted(path for path in SAMPLES_DIR.iterdir() if path.is_dir()):
        class_name = class_dir.name
        image_paths = sorted(class_dir.glob("*.jpg"), key=lambda path: int(path.stem))
        kept = []
        for image_path in image_paths:
            row = sources.get(f"{class_name}/{image_path.name}")
            counts[class_name][1] += 1
            if row is None or row["source"].startswith(TRAINING_COPY_SOURCE):
                continue
            probabilities = predictor.predict_probabilities(image_path)
            predicted_index = int(np.argmax(probabilities))
            if CLASS_NAMES[predicted_index] == class_name:
                kept.append((image_path, row, float(probabilities[predicted_index])))

        # renumber the kept photos 1..n (temporary names first, so no file is overwritten)
        kept_paths = {image_path for image_path, _, _ in kept}
        for image_path in image_paths:
            if image_path not in kept_paths:
                image_path.unlink()
        temporary_paths = []
        for image_path, row, confidence in kept:
            temporary_path = image_path.with_name(f"keep-{image_path.name}")
            image_path.rename(temporary_path)
            temporary_paths.append((temporary_path, row, confidence))
        for number, (temporary_path, row, confidence) in enumerate(temporary_paths, start=1):
            temporary_path.rename(class_dir / f"{number}.jpg")
            kept_rows.append([f"{class_name}/{number}.jpg", class_name, row["source"], row["original_id"], f"{confidence:.4f}"])
        counts[class_name][0] = len(kept)
        if not kept:
            (class_dir / ".gitkeep").touch()  # keep every class folder, even when empty

    with open(SOURCES_FILE, "w", newline="") as sources_file:
        writer = csv.writer(sources_file)
        writer.writerow(["file", "class", "source", "original_id", "model_confidence"])
        writer.writerows(kept_rows)

    print(f"{'class':20s} kept / before")
    for class_name in CLASS_NAMES:
        kept_count, total = counts.get(class_name, [0, 0])
        print(f"{class_name:20s} {kept_count:4d} / {total}")
    print(f"Total kept: {sum(kept for kept, _ in counts.values())} of {sum(total for _, total in counts.values())}")


if __name__ == "__main__":
    main()
