import httpx

from .config import logger, settings

client: httpx.AsyncClient | None = None


async def init_client():
    global client
    client = httpx.AsyncClient(base_url=settings.inference_url, timeout=30.0)
    logger.info(f"Done initialize HTTP client {client.base_url}")


async def close_client():
    global client
    if client:
        await client.aclose()
    logger.info("HTTP client closed.")


def get_client() -> httpx.AsyncClient:
    if client is None:
        raise RuntimeError("HTTP client not initialized")
    return client
