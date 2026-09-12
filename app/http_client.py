import httpx

from .config import logger, settings

client: httpx.Client | None = None
async_client: httpx.AsyncClient | None = None


def init_client() -> httpx.Client:
    """Initialize the primary synchronous HTTP client."""
    global client
    if client is None:
        client = httpx.Client(base_url=settings.inference_url, timeout=30.0)
        logger.info(f"Done initialize HTTP client {client.base_url}")
    return client


def close_client():
    """Close the primary synchronous HTTP client."""
    global client
    if client:
        client.close()
        client = None
    logger.info("HTTP client closed.")


def get_client() -> httpx.Client:
    """Return the primary synchronous HTTP client."""
    global client
    if client is None:
        client = init_client()
    return client


async def init_async_client() -> httpx.AsyncClient:
    """Initialize the optional asynchronous HTTP client."""
    global async_client
    if async_client is None:
        async_client = httpx.AsyncClient(
            base_url=settings.inference_url, timeout=30.0
        )
        logger.info(
            f"Done initialize async HTTP client {async_client.base_url}"
        )
    return async_client


async def close_async_client():
    """Close the optional asynchronous HTTP client."""
    global async_client
    if async_client:
        await async_client.aclose()
        async_client = None
    logger.info("Async HTTP client closed.")


def get_async_client() -> httpx.AsyncClient:
    """Return the asynchronous HTTP client if needed."""
    if async_client is None:
        raise RuntimeError("Async HTTP client not initialized")
    return async_client
