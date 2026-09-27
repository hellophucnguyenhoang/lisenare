from pathlib import Path
import boto3

from config import logger, settings

s3_client = None


def init_s3_client():
    """Initializes the Boto3 S3 client once on startup."""
    global s3_client
    if s3_client is None:
        kwargs = {"service_name": "s3"}
        if settings.aws_endpoint_url:
            kwargs["endpoint_url"] = settings.aws_endpoint_url
        if settings.aws_access_key_id:
            kwargs["aws_access_key_id"] = settings.aws_access_key_id
        if settings.aws_secret_access_key:
            kwargs["aws_secret_access_key"] = settings.aws_secret_access_key
        s3_client = boto3.client(**kwargs)
        logger.info("Initialized S3 cloud storage client")
    return s3_client


def get_s3_client():
    """Returns the singleton S3 client."""
    global s3_client
    if s3_client is None:
        return init_s3_client()
    return s3_client


def download_file(s3_key: str, local_path: Path):
    """Download a file from cloud storage to local_path."""
    s3 = get_s3_client()
    local_path.parent.mkdir(parents=True, exist_ok=True)
    s3.download_file(settings.bucket_name, s3_key, str(local_path))
    logger.info(f"Downloaded '{s3_key}' to '{local_path}'")


def upload_bytes(
    content: bytes,
    s3_key: str,
    content_type: str = "audio/wav",
):
    """Upload bytes directly to cloud storage at s3_key."""
    s3 = get_s3_client()
    s3.put_object(
        Bucket=settings.bucket_name,
        Key=s3_key,
        Body=content,
        ContentType=content_type,
    )
    logger.info(f"Uploaded bytes to cloud storage '{s3_key}'")


def upload_file(
    local_path: Path,
    s3_key: str,
    content_type: str = "audio/wav",
):
    """Upload a local file to cloud storage at s3_key."""
    s3 = get_s3_client()
    s3.upload_file(
        str(local_path),
        settings.bucket_name,
        s3_key,
        ExtraArgs={"ContentType": content_type},
    )
    logger.info(f"Uploaded '{local_path}' to '{s3_key}'")
