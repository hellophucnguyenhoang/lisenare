import redis

from .config import settings

_client: redis.Redis | None = None


def get_redis() -> redis.Redis:
    """FastAPI dependency that returns a singleton sync Redis client.

    Tests override this dependency with a fakeredis instance.
    """
    global _client
    if _client is None:
        _client = redis.Redis.from_url(
            settings.redis_url, decode_responses=True
        )
    return _client
