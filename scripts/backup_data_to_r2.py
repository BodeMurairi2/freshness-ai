"""
Backs up the image folders of data/ to the R2 bucket, under the same paths:
    data/train/fresh_apple/x.jpg  ->  <bucket>/data/train/fresh_apple/x.jpg

Files already in the bucket with the same size are skipped, so it is safe to re-run.

Usage (from the repo root):
    python scripts/backup_data_to_r2.py
    python scripts/backup_data_to_r2.py --folders uploads
"""
import argparse
import mimetypes
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))  # so `api` can be imported when run as a script

from api.config.settings import app_settings  # noqa: E402
from api.services.file_storage import storage_client  # noqa: E402

DATA_DIR = ROOT / "data"
DEFAULT_FOLDERS = ["samples", "test", "train", "uploads", "validation"]
SKIPPED_NAMES = {".gitkeep"}

settings = app_settings()


def files_in_bucket(prefix: str) -> dict[str, int]:
    """Key -> size of everything already stored under a prefix"""
    stored_files = {}
    paginator = storage_client().get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=settings.R2_BUCKET, Prefix=prefix):
        for stored_file in page.get("Contents", []):
            stored_files[stored_file["Key"]] = stored_file["Size"]
    return stored_files


def upload_file(local_path: Path, storage_key: str):
    content_type = mimetypes.guess_type(local_path.name)[0] or "application/octet-stream"
    storage_client().upload_file(
        str(local_path), settings.R2_BUCKET, storage_key, ExtraArgs={"ContentType": content_type}
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--folders", nargs="+", default=DEFAULT_FOLDERS)
    parser.add_argument("--workers", type=int, default=16)
    args = parser.parse_args()

    already_stored = files_in_bucket("data/")
    to_upload = []
    for folder in args.folders:
        for local_path in sorted((DATA_DIR / folder).rglob("*")):
            if not local_path.is_file() or local_path.name in SKIPPED_NAMES:
                continue
            storage_key = local_path.relative_to(ROOT).as_posix()
            if already_stored.get(storage_key) != local_path.stat().st_size:
                to_upload.append((local_path, storage_key))

    print(f"{len(to_upload)} files to upload to {settings.R2_BUCKET} "
          f"({sum(1 for _ in already_stored)} already there)")

    failed = []
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        uploads = {executor.submit(upload_file, local_path, key): key for local_path, key in to_upload}
        for finished, upload in enumerate(as_completed(uploads), start=1):
            try:
                upload.result()
            except Exception as error:
                failed.append((uploads[upload], f"{type(error).__name__}: {error}"))
            if finished % 250 == 0 or finished == len(to_upload):
                print(f"  {finished}/{len(to_upload)} done")

    for key, error in failed:
        print(f"  FAILED {key}: {error}")
    print(f"Backup finished: {len(to_upload) - len(failed)} uploaded, {len(failed)} failed")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
