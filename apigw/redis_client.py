import redis

from config import logger, settings

client: redis.Redis | None = None


def init_redis_client() -> redis.Redis:
    """Initialize the Redis client, falling back to FakeRedis if unavailable."""
    global client
    if client is None:
        try:
            r = redis.from_url(settings.redis_url, decode_responses=True)
            r.ping()
            client = r
            logger.info(f"Connected to Redis at {settings.redis_url}")
        except Exception as e:
            logger.warning(
                f"Could not connect to Redis at {settings.redis_url}: {e}. "
                "Falling back to FakeRedis."
            )
            import fakeredis

            client = fakeredis.FakeRedis(decode_responses=True)
    return client


def close_redis_client():
    """Close the active Redis client connection."""
    global client
    if client:
        try:
            client.close()
        except Exception as e:
            logger.warning(f"Error closing Redis client: {e}")
        client = None
    logger.info("Redis client closed.")


def get_redis_client() -> redis.Redis:
    """Return the active Redis client instance."""
    global client
    if client is None:
        client = init_redis_client()
    return client
