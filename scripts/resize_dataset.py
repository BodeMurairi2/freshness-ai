from __future__ import annotations

import argparse
import sys
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.preprocessing import ImageProcessing, STORAGE_MAX_SIDE

DEFAULT_DATA_DIR = ROOT / "data"
DEFAULT_FOLDERS = ["train", "validation", "test", "sample"]
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".heic", ".heif"}

image_processor = ImageProcessing()


def human_size(number_of_bytes: float) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if number_of_bytes < 1024:
            return f"{number_of_bytes:.1f} {unit}"
        number_of_bytes /= 1024
    return f"{number_of_bytes:.1f} TB"


def folder_size(folder: Path) -> int:
    return sum(file.stat().st_size for file in folder.rglob("*") if file.is_file())


def find_images(folder: Path) -> list[Path]:
    return sorted(file for file in folder.rglob("*") if file.suffix.lower() in IMAGE_EXTENSIONS)


def is_already_converted(image_path: Path) -> bool:
    """True if the image is a JPEG whose longest side is already within the storage size."""
    with Image.open(image_path) as image:
        return image.format == "JPEG" and max(image.size) <= STORAGE_MAX_SIDE


def convert_image(image_path: Path, force: bool) -> str:
    """
    Converts one image in place. Returns "converted" or "skipped".
    Non-JPEG files (e.g. .png) are replaced by a .jpg file with the same name.
    """
    if not force and is_already_converted(image_path):
        return "skipped"

    with open(image_path, "rb") as image_file:
        jpeg_bytes = image_processor.prepare_for_storage(image_file)

    final_path = image_path.with_suffix(".jpg")
    temporary_path = final_path.with_name(final_path.name + ".part")
    temporary_path.write_bytes(jpeg_bytes)
    temporary_path.replace(final_path)
    if final_path != image_path:
        image_path.unlink()
    return "converted"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR, help="folder that contains the dataset folders")
    parser.add_argument("--folders", nargs="+", default=DEFAULT_FOLDERS, help="dataset folders to convert")
    parser.add_argument("--force", action="store_true", help="convert images even if they are already <= 512 px JPEGs")
    parser.add_argument("--workers", type=int, default=8, help="number of images converted in parallel")
    args = parser.parse_args()

    for folder_name in args.folders:
        folder = args.data_dir / folder_name
        if not folder.exists():
            print(f"[{folder_name}] not found, skipped")
            continue

        images = find_images(folder)
        size_before = folder_size(folder)
        counts = {"converted": 0, "skipped": 0}

        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            convert_with_options = partial(convert_image, force=args.force)
            for number, outcome in enumerate(pool.map(convert_with_options, images), start=1):
                counts[outcome] += 1
                if number % 200 == 0 or number == len(images):
                    print(f"[{folder_name}] {number}/{len(images)} images processed", flush=True)

        print(
            f"[{folder_name}] {counts['converted']} converted, {counts['skipped']} already converted | "
            f"{human_size(size_before)} -> {human_size(folder_size(folder))}"
        )


if __name__ == "__main__":
    main()
