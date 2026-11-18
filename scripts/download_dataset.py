"""
Download the Fresh/Rotten Fruit dataset from Hugging Face into data/raw_data/.

The dataset is stored on Hugging Face as 4 Parquet files (~2.86 GB, 3,200 images).
This script:
  1. Downloads each Parquet file (with a byte progress bar), skipping files already downloaded.
  2. Extracts every image into a class folder, e.g.
         data/raw_data/images/fresh_apple/00012_xxx.jpg
         data/raw_data/images/rotten_banana/01544_xxx.jpg
  3. Logs every file it downloads/saves, plus overall progress, to the console
     and to logs/download_dataset.log.

Resuming: if the script is interrupted (Ctrl+C, network drop, laptop sleep), just
run it again:
  - A half-downloaded Parquet file continues from the byte where it stopped.
  - Fully downloaded Parquet files and already-extracted images are skipped.
  - Once everything has finished, a marker file is written so re-running does
    nothing (use --force to download and extract again).

Usage (from the repo root):
    python scripts/download_dataset.py
    python scripts/download_dataset.py --keep-parquet   # keep the .parquet files after extracting
    python scripts/download_dataset.py --force          # redo everything
"""

from __future__ import annotations

import argparse
import io
import logging
import os
import shutil
import sys
import time
from pathlib import Path

os.environ.setdefault("HF_HUB_DISABLE_XET", "1")

import pyarrow.parquet as pq
from huggingface_hub import HfApi, hf_hub_download
from PIL import Image
from tqdm import tqdm

REPO_ID = "Project-AgML/fresh_rotten_fruit_classification"
SUBSET = "raw"  # "raw" = 3,200 original images; "augmented" = 12,335 augmented images
LABEL_NAMES = {0: "fresh", 1: "rotten"}

ROOT = Path(__file__).resolve().parent.parent
DEST = ROOT / "data" / "raw_data"
PARQUET_DIR = DEST / "parquet"
IMAGES_DIR = DEST / "images"
DONE_MARKER = DEST / ".download_complete"
LOG_FILE = ROOT / "logs" / "download_dataset.log"

log = logging.getLogger("download_dataset")


class TqdmHandler(logging.Handler):
    """Print log lines above the progress bar instead of breaking it."""

    def emit(self, record: logging.LogRecord) -> None:
        tqdm.write(self.format(record), file=sys.stdout)


def setup_logging() -> None:
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    fmt = logging.Formatter("%(asctime)s | %(levelname)-7s | %(message)s", "%H:%M:%S")

    console = TqdmHandler()
    console.setFormatter(fmt)
    file = logging.FileHandler(LOG_FILE, encoding="utf-8")
    file.setFormatter(fmt)

    log.setLevel(logging.INFO)
    log.addHandler(console)
    log.addHandler(file)


def human_size(n: float) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} TB"


# --------------------------------------------------------------------------- step 1
def partial_download_size(sibling) -> int:
    """Bytes already downloaded for an unfinished file (0 if none).

    huggingface_hub keeps unfinished downloads in
    <local_dir>/.cache/huggingface/download/<folder>/<hash>.<sha256>.incomplete
    """
    sha = getattr(getattr(sibling, "lfs", None), "sha256", None)
    folder = PARQUET_DIR / ".cache" / "huggingface" / "download" / Path(sibling.rfilename).parent
    if not sha or not folder.exists():
        return 0
    return sum(f.stat().st_size for f in folder.glob(f"*.{sha}.incomplete"))


def download_parquet_files() -> list[Path]:
    """Download every Parquet file of the chosen subset. Returns local paths."""
    info = HfApi().dataset_info(REPO_ID, files_metadata=True)
    remote = sorted(
        (s for s in info.siblings if s.rfilename.startswith(f"{SUBSET}/") and s.rfilename.endswith(".parquet")),
        key=lambda s: s.rfilename,
    )
    total_bytes = sum(s.size or 0 for s in remote)
    log.info("Found %d Parquet files to download (%s total)", len(remote), human_size(total_bytes))

    local_paths: list[Path] = []
    done_bytes = 0
    for i, sibling in enumerate(remote, start=1):
        local = PARQUET_DIR / sibling.rfilename
        size = sibling.size or 0

        if local.exists() and local.stat().st_size == size:
            log.info("[%d/%d] SKIP (already downloaded) %s", i, len(remote), sibling.rfilename)
        else:
            partial = partial_download_size(sibling)
            if partial:
                log.info("[%d/%d] Resuming %s from %s of %s...", i, len(remote), sibling.rfilename,
                         human_size(partial), human_size(size))
            else:
                log.info("[%d/%d] Downloading %s (%s)...", i, len(remote), sibling.rfilename, human_size(size))
            start = time.time()
            # hf_hub_download shows its own byte-level progress bar
            hf_hub_download(REPO_ID, sibling.rfilename, repo_type="dataset", local_dir=PARQUET_DIR)
            log.info("[%d/%d] Downloaded %s in %.1fs", i, len(remote), sibling.rfilename, time.time() - start)

        done_bytes += size
        pct = 100 * done_bytes / total_bytes if total_bytes else 100
        log.info("Download progress: %s / %s (%.1f%%)", human_size(done_bytes), human_size(total_bytes), pct)
        local_paths.append(local)

    return local_paths


# --------------------------------------------------------------------------- step 2
def image_extension(data: bytes, original_path: str | None) -> str:
    if original_path and Path(original_path).suffix:
        return Path(original_path).suffix.lower()
    try:
        fmt = Image.open(io.BytesIO(data)).format or "JPEG"
    except Exception:
        fmt = "JPEG"
    return ".jpg" if fmt.upper() == "JPEG" else f".{fmt.lower()}"


def extract_images(parquet_files: list[Path]) -> dict[str, int]:
    """Write every image to IMAGES_DIR/<label>_<fruit>/. Returns per-class counts."""
    total = sum(pq.ParquetFile(p).metadata.num_rows for p in parquet_files)
    log.info("Extracting %d images into %s", total, IMAGES_DIR.relative_to(ROOT))

    counts: dict[str, int] = {}
    saved = skipped = 0
    index = 0  # global running index -> stable, unique filenames across shards

    with tqdm(total=total, unit="img", desc="Extracting", file=sys.stdout) as bar:
        for p in parquet_files:
            pf = pq.ParquetFile(p)
            for batch in pf.iter_batches(batch_size=64, columns=["image", "label", "fruit_type"]):
                for row in batch.to_pylist():
                    index += 1
                    label = LABEL_NAMES.get(row["label"], str(row["label"]))
                    fruit = (row["fruit_type"] or "unknown").strip().lower().replace(" ", "_")
                    class_name = f"{label}_{fruit}"

                    data = row["image"]["bytes"]
                    orig = row["image"].get("path")
                    stem = Path(orig).stem if orig else "img"
                    out = IMAGES_DIR / class_name / f"{index:05d}_{stem}{image_extension(data, orig)}"

                    if out.exists():
                        skipped += 1
                        status = "SKIP"
                    else:
                        out.parent.mkdir(parents=True, exist_ok=True)
                        # Write to a temp file then rename: if the script is killed
                        # mid-write, no half-written image is left behind under the
                        # real name (which would otherwise be skipped on resume).
                        tmp = out.with_name(out.name + ".part")
                        tmp.write_bytes(data)
                        tmp.replace(out)
                        saved += 1
                        status = "SAVED"

                    counts[class_name] = counts.get(class_name, 0) + 1
                    pct = 100 * index / total
                    log.info("[%d/%d %5.1f%%] %s %s", index, total, pct, status, out.relative_to(ROOT))
                    bar.update(1)

    log.info("Extraction done: %d saved, %d already existed", saved, skipped)
    return counts


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--keep-parquet", action="store_true", help="keep the downloaded .parquet files after extraction")
    parser.add_argument("--force", action="store_true", help="download and extract again even if already complete")
    args = parser.parse_args()

    setup_logging()

    if DONE_MARKER.exists() and not args.force:
        log.info("Dataset already downloaded and extracted (%s). Nothing to do.", IMAGES_DIR.relative_to(ROOT))
        log.info("Use --force to download it again.")
        return
    DONE_MARKER.unlink(missing_ok=True)

    log.info("=== Downloading %s (%s) into %s ===", REPO_ID, SUBSET, DEST.relative_to(ROOT))
    start = time.time()

    parquet_files = download_parquet_files()
    counts = extract_images(parquet_files)

    log.info("Images per class:")
    for name in sorted(counts):
        log.info("  %-20s %d", name, counts[name])
    log.info("Total: %d images in %d classes", sum(counts.values()), len(counts))

    DONE_MARKER.write_text(f"{sum(counts.values())} images\n")

    if not args.keep_parquet:
        shutil.rmtree(PARQUET_DIR, ignore_errors=True)
        log.info("Removed temporary Parquet files (use --keep-parquet to keep them)")

    log.info("=== Finished in %.1f min. Log saved to %s ===", (time.time() - start) / 60, LOG_FILE.relative_to(ROOT))


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log.warning("Interrupted. Run the script again to resume; finished files are skipped.")
        sys.exit(1)
