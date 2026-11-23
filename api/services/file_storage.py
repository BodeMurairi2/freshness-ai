"""
Images in Cloudflare R2 (S3-compatible). MongoDB keeps their public links.
"""
from functools import lru_cache

import boto3
from botocore.config import Config

from api.config.settings import app_settings

settings = app_settings()


def storage_endpoint() -> str:
    """EU buckets live on <account>.eu.r2.cloudflarestorage.com"""
    jurisdiction = f".{settings.R2_BUCKET_JURISDICTION}" if settings.R2_BUCKET_JURISDICTION else ""
    return f"https://{settings.R2_ACCOUNT_ID}{jurisdiction}.r2.cloudflarestorage.com"


@lru_cache(maxsize=1)
def storage_client():
    """One R2 client for the whole app (boto3 clients are thread safe)"""
    return boto3.client(
        "s3",
        endpoint_url=storage_endpoint(),
        aws_access_key_id=settings.R2_ACCESS_KEY_ID,
        aws_secret_access_key=settings.R2_SECRET_ACCESS_KEY,
        region_name="auto",
        config=Config(retries={"max_attempts": 3, "mode": "standard"}, max_pool_connections=32),
    )


def public_url(storage_key: str) -> str:
    return f"{settings.R2_PUBLIC_URL.rstrip('/')}/{storage_key}"


def upload_image(jpeg_bytes: bytes, storage_key: str) -> str:
    """Uploads one JPEG and returns its public link"""
    storage_client().put_object(
        Bucket=settings.R2_BUCKET,
        Key=storage_key,
        Body=jpeg_bytes,
        ContentType="image/jpeg",
    )
    return public_url(storage_key)
