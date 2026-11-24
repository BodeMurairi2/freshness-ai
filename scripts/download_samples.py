"""
Build data/samples/: ready-to-upload labelled images for testing (re)training.

For every one of the 16 classes, IMAGES_PER_CLASS images are saved as
    data/samples/<class>/1.jpg, 2.jpg, ... n.jpg
in the same storage format as uploads (upright, RGB, longest side <= 512 px, JPEG),
using ImageProcessing.prepare_for_storage from src/preprocessing.py.

Sources (none of these images are in the training/validation/test split):
  apple, banana, guava, orange, pomegranate
      FruitNet (Meshram & Patil, 2022), CC-BY-4.0
      huggingface.co/datasets/Project-AgML/FruitNet_quality_classification
      quality "Good" -> fresh_<fruit>, "Bad" -> rotten_<fruit>  ("Mixed" is skipped)
  strawberry
      FRUIT-16K, CC-BY-SA-4.0
      huggingface.co/datasets/marwan3637/fruit-16k-fresh-spoiled
      "F_Strawberry" -> fresh_strawberry, "S_Strawberry" -> rotten_strawberry
  jujube
      Jujube bruise classification (Project-AgML), CC-BY-4.0
      huggingface.co/datasets/Project-AgML/jujube_bruise_classification
      "healthy" -> fresh_jujube, "bruised" -> rotten_jujube
      (note: "bruised" is close to, but not exactly, "rotten")
  grape
      No public fresh/rotten grape dataset exists, so grape samples are COPIES of
      images from data/train/ (never validation or test, so evaluation stays fair).

Every downloaded image is compared with all images of data/train, data/validation and
data/test (perceptual hash); near-duplicates are skipped, so no test image can leak in.
data/samples/SOURCES.csv records where every saved image came from.

Usage (from the repo root):
    python scripts/download_samples.py                 # 25 images per class
    python scripts/download_samples.py --per-class 30  # more per class

Then run scripts/keep_correct_samples.py: photos from other datasets often look different
or are labelled differently (e.g. FruitNet "Bad" is not always visibly rotten), so only the
ones the model classifies correctly are kept, and the grape copies of training images are removed.
"""

from __future__ import annotations

import argparse
import csv
import io
import random
import shutil
import sys
import zipfile
from collections import defaultdict
from pathlib import Path

import numpy as np
import pyarrow.parquet as pq
from huggingface_hub import HfFileSystem
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))  # so `src` can be imported when run as a script

from src.preprocessing import ImageProcessing  # noqa: E402
from src.target_class import CLASS_NAMES  # noqa: E402

DATA_DIR = ROOT / "data"
OUTPUT_DIR = DATA_DIR / "samples"
SPLIT_FOLDERS = ["train", "validation", "test"]
SEED = 42
DUPLICATE_DISTANCE = 5  # hashes this close (out of 64 bits) count as the same picture

FRUITNET_REPO = "Project-AgML/FruitNet_quality_classification"
FRUITNET_FILE = "data/train-00000-of-00009.parquet"  # every file mixes all fruits; one is enough
FRUITNET_FRUITS = {"Apple": "apple", "Banana": "banana", "Guava": "guava", "Orange": "orange", "Pomegranate": "pomegranate"}
FRUITNET_QUALITY = {"Good": "fresh", "Bad": "rotten"}

FRUIT16K_REPO = "marwan3637/fruit-16k-fresh-spoiled"
FRUIT16K_FILE = "FRUIT-16K.zip"
FRUIT16K_FOLDERS = {"FRUIT-16K/F_Strawberry/": "fresh_strawberry", "FRUIT-16K/S_Strawberry/": "rotten_strawberry"}

JUJUBE_REPO = "Project-AgML/jujube_bruise_classification"
JUJUBE_FILE = "raw/train-00000-of-00001.parquet"
JUJUBE_LABELS = {"healthy": "fresh_jujube", "bruised": "rotten_jujube"}

hugging_face_files = HfFileSystem()
image_processor = ImageProcessing()


# ----------------------------------------------------------------- duplicate check
def picture_hash(image: Image.Image) -> np.ndarray:
    """64-bit difference hash: survives resizing and JPEG re-compression of the same picture."""
    small = np.asarray(image.convert("L").resize((9, 8), Image.Resampling.LANCZOS), dtype=np.int16)
    return (small[:, 1:] > small[:, :-1]).flatten()


def dataset_hashes() -> np.ndarray:
    """Hashes of every image in the train/validation/test split."""
    hashes = []
    for folder in SPLIT_FOLDERS:
        for image_path in (DATA_DIR / folder).rglob("*.jpg"):
            with Image.open(image_path) as image:
                hashes.append(picture_hash(image))
    print(f"Duplicate check: hashed {len(hashes)} dataset images")
    return np.array(hashes)


def is_in_dataset(image: Image.Image, known_hashes: np.ndarray) -> bool:
    differences = (known_hashes != picture_hash(image)).sum(axis=1)
    return bool(differences.min() <= DUPLICATE_DISTANCE)


# ----------------------------------------------------------------- sources
def class_label_names(parquet_file: pq.ParquetFile, column: str) -> list[str]:
    """Class names of a Hugging Face ClassLabel column, read from the Parquet metadata."""
    import json
    features = json.loads(parquet_file.schema_arrow.metadata[b"huggingface"])["info"]["features"]
    return features[column]["names"]


def fruitnet_candidates(needed_per_class: int):
    """Yields (class_name, image_bytes, original_id) from FruitNet until every fruit/quality is filled."""
    collected = defaultdict(int)
    with hugging_face_files.open(f"datasets/{FRUITNET_REPO}/{FRUITNET_FILE}", "rb") as remote_file:
        parquet_file = pq.ParquetFile(remote_file)
        crop_names = class_label_names(parquet_file, "crop")
        quality_names = class_label_names(parquet_file, "label")
        for row_group in range(parquet_file.num_row_groups):
            rows = parquet_file.read_row_group(row_group, columns=["image", "crop", "label"]).to_pylist()
            for row_number, row in enumerate(rows):
                fruit = FRUITNET_FRUITS.get(crop_names[row["crop"]])
                condition = FRUITNET_QUALITY.get(quality_names[row["label"]])
                if not fruit or not condition:
                    continue
                class_name = f"{condition}_{fruit}"
                if collected[class_name] < needed_per_class:
                    collected[class_name] += 1
                    yield class_name, row["image"]["bytes"], f"{FRUITNET_FILE}#rowgroup{row_group}-row{row_number}"
            if len(collected) == 10 and min(collected.values()) >= needed_per_class:
                return


def fruit16k_candidates(needed_per_class: int):
    """Yields (class_name, image_bytes, original_id) of fresh/spoiled strawberries from FRUIT-16K."""
    random_generator = random.Random(SEED)
    with hugging_face_files.open(f"datasets/{FRUIT16K_REPO}/{FRUIT16K_FILE}", "rb", block_size=2**20) as remote_file:
        archive = zipfile.ZipFile(remote_file)  # only the requested files are downloaded
        for folder, class_name in FRUIT16K_FOLDERS.items():
            file_names = sorted(name for name in archive.namelist() if name.startswith(folder) and not name.endswith("/"))
            for file_name in random_generator.sample(file_names, needed_per_class):
                yield class_name, archive.read(file_name), f"{FRUIT16K_FILE}/{file_name}"


def jujube_candidates(needed_per_class: int):
    """Yields (class_name, image_bytes, original_id) of healthy/bruised jujubes."""
    collected = defaultdict(int)
    with hugging_face_files.open(f"datasets/{JUJUBE_REPO}/{JUJUBE_FILE}", "rb") as remote_file:
        parquet_file = pq.ParquetFile(remote_file)
        label_names = class_label_names(parquet_file, "label")
        rows = parquet_file.read(columns=["image", "label"]).to_pylist()
    random.Random(SEED).shuffle(rows)
    for row in rows:
        class_name = JUJUBE_LABELS.get(label_names[row["label"]])
        if class_name and collected[class_name] < needed_per_class:
            collected[class_name] += 1
            yield class_name, row["image"]["bytes"], f"{JUJUBE_FILE}:{row['image'].get('path')}"


def grape_candidates(needed_per_class: int):
    """Yields (class_name, image_bytes, original_id): copies of TRAINING grape images (no other source exists)."""
    random_generator = random.Random(SEED)
    for class_name in ("fresh_grape", "rotten_grape"):
        training_images = sorted((DATA_DIR / "train" / class_name).glob("*.jpg"))
        for image_path in random_generator.sample(training_images, needed_per_class):
            yield class_name, image_path.read_bytes(), f"data/train/{class_name}/{image_path.name}"


SOURCES = [
    ("FruitNet (CC-BY-4.0)", fruitnet_candidates, True),
    ("FRUIT-16K (CC-BY-SA-4.0)", fruit16k_candidates, True),
    ("Jujube bruise classification (CC-BY-4.0)", jujube_candidates, True),
    ("Copy of data/train (grape: no public source)", grape_candidates, False),  # copies: no duplicate check
]


# ----------------------------------------------------------------- main
def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--per-class", type=int, default=25, help="images saved per class (default 25)")
    args = parser.parse_args()

    known_hashes = dataset_hashes()
    saved_per_class = defaultdict(int)
    source_rows = []

    if OUTPUT_DIR.exists():
        shutil.rmtree(OUTPUT_DIR)  # rebuilt from scratch, so numbering always starts at 1

    for source_name, candidates, check_duplicates in SOURCES:
        print(f"\n{source_name}")
        # ask for extra candidates, in case some are rejected as duplicates or unreadable
        extra = args.per_class if check_duplicates else 0
        for class_name, image_bytes, original_id in candidates(args.per_class + extra):
            if saved_per_class[class_name] >= args.per_class:
                continue
            try:
                image = Image.open(io.BytesIO(image_bytes))
                image.load()
            except Exception:
                print(f"  skipped unreadable image {original_id}")
                continue
            if check_duplicates and is_in_dataset(image, known_hashes):
                print(f"  skipped {original_id}: same picture as one in the dataset")
                continue

            saved_per_class[class_name] += 1
            number = saved_per_class[class_name]
            output_path = OUTPUT_DIR / class_name / f"{number}.jpg"
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(image_processor.prepare_for_storage(io.BytesIO(image_bytes)))
            source_rows.append([f"{class_name}/{number}.jpg", class_name, source_name, original_id])

        filled = {name: count for name, count in sorted(saved_per_class.items())}
        print(f"  saved so far: {filled}")

    with open(OUTPUT_DIR / "SOURCES.csv", "w", newline="") as sources_file:
        writer = csv.writer(sources_file)
        writer.writerow(["file", "class", "source", "original_id"])
        writer.writerows(source_rows)

    print("\nImages per class:")
    for class_name in CLASS_NAMES:
        flag = "" if saved_per_class[class_name] >= args.per_class else "  <-- fewer than requested"
        print(f"  {class_name:<20} {saved_per_class[class_name]}{flag}")
    print(f"Total: {sum(saved_per_class.values())} images in {OUTPUT_DIR.relative_to(ROOT)}/")


if __name__ == "__main__":
    main()
