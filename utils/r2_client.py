"""Client R2 (Cloudflare, tương thích S3) cho việc lưu/đọc/xóa object JSON.

R2 dùng giao thức S3 nên ta dùng ``boto3``. Cấu hình lấy từ ``settings``:
``r2_endpoint_url``, ``r2_access_key_id``, ``r2_secret_access_key``,
``r2_bucket_name`` (region cố định là ``"auto"``).
"""

import json
from typing import Any

try:
    import boto3
    from botocore.exceptions import ClientError
except ImportError:  # pragma: no cover - chỉ chạy khi chưa cài boto3
    boto3 = None
    ClientError = Exception

from app.config import settings

_r2_client: Any | None = None


def get_r2_client() -> Any:
    """Trả về (và cache) client boto3 trỏ tới endpoint R2."""
    global _r2_client
    if boto3 is None:
        raise RuntimeError(
            "Cần lưu trữ trên R2 nhưng chưa cài boto3. Chạy `uv add boto3` "
            "hoặc đặt USE_CLOUD_STORAGE=false để dùng file local."
        )
    if not settings.r2_endpoint_url or not settings.r2_bucket_name:
        raise RuntimeError(
            "Thiếu cấu hình R2: cần R2_ENDPOINT_URL và R2_BUCKET_NAME trong .env."
        )
    if _r2_client is None:
        _r2_client = boto3.client(
            "s3",
            endpoint_url=settings.r2_endpoint_url,
            aws_access_key_id=settings.r2_access_key_id,
            aws_secret_access_key=settings.r2_secret_access_key,
            region_name="auto",
        )
    return _r2_client


def put_json(key: str, data: dict) -> None:
    """Ghi (ghi đè) một object JSON lên R2 tại ``key``."""
    body = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
    get_r2_client().put_object(
        Bucket=settings.r2_bucket_name,
        Key=key,
        Body=body,
        ContentType="application/json; charset=utf-8",
    )


def get_json(key: str) -> dict:
    """Đọc object JSON từ R2. Trả về ``{}`` nếu object không tồn tại."""
    try:
        resp = get_r2_client().get_object(
            Bucket=settings.r2_bucket_name, Key=key
        )
    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code", "")
        if code in ("NoSuchKey", "404", "NoSuchBucket"):
            return {}
        raise
    try:
        return json.loads(resp["Body"].read().decode("utf-8"))
    except (json.JSONDecodeError, KeyError):
        return {}


def delete_object(key: str) -> None:
    """Xóa object trên R2 tại ``key`` (không lỗi nếu object không tồn tại)."""
    get_r2_client().delete_object(Bucket=settings.r2_bucket_name, Key=key)
