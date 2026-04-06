import httpx

from .config import settings

client: httpx.AsyncClient | None = None


async def init_client():
    global client
    client = httpx.AsyncClient(
        base_url=settings.ai_model_server_url, timeout=30.0
    )
    print(f"Done initialize http client {client.base_url}")


async def close_client():
    global client
    if client:
        await client.aclose()
    print("http client closed.")


def get_client() -> httpx.AsyncClient:
    if client is None:
        raise RuntimeError("HTTP client not initialized")
    return client
