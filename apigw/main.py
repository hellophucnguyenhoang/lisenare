from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

import cloud_storage_client
import database
import http_client
import redis_client
from config import logger
from constants import ASSETS_DIR
from exceptions import RequestException
from routers import (
    account_router,
    audio_router,
    auth_router,
    brick_interaction_router,
    brick_memory_router,
    brick_review_router,
    brick_router,
    chat_router,
    context_search_router,
    explanation_router,
    island_router,
    learner_router,
    text_router,
)
from schemas import BrickCreateRequest, BrickUpdate
from services import audio_cache_service
from utils.form_utils import get_model_example_string


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup code
    logger.info("Initializing Lisenare API services...")
    database.init_db()
    http_client.init_client()
    await http_client.init_async_client()
    redis_client.init_redis_client()
    cloud_storage_client.init_s3_client()
    audio_scheduler = audio_cache_service.start_audio_cleanup_scheduler()
    logger.info("Lisenare API services initialized successfully.")
    yield
    # Shutdown code
    logger.info("Shutting down Lisenare API services...")
    audio_cache_service.stop_audio_cleanup_scheduler(audio_scheduler)
    redis_client.close_redis_client()
    # database.delete_db_force()
    http_client.close_client()
    await http_client.close_async_client()
    logger.info("Lisenare API services shut down successfully.")


app = FastAPI(
    title="Lisenare API",
    lifespan=lifespan,
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)


# Unified exception response structure
@app.exception_handler(RequestException)
async def request_exception_handler(request: Request, exc: RequestException):
    if exc.status_code >= 500:
        logger.error(
            f"Server error ({exc.status_code}) on {request.method} {request.url.path}: {exc.detail}"
        )
    else:
        logger.warning(
            f"Client error ({exc.status_code}) on {request.method} {request.url.path}: {exc.detail}"
        )
    return JSONResponse(
        status_code=exc.status_code,
        content=exc.detail,
        headers=exc.headers,
    )


# Override the default system exception
# to keep the response structure consistent
@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(
    request: Request, exc: StarletteHTTPException
):
    if exc.status_code >= 500:
        logger.error(
            f"HTTP error ({exc.status_code}) on {request.method} {request.url.path}: {exc.detail}"
        )
    else:
        logger.warning(
            f"HTTP client error ({exc.status_code}) on {request.method} {request.url.path}: {exc.detail}"
        )
    return JSONResponse(
        status_code=exc.status_code,
        content={"debug_message": exc.detail, "error_code": None},
        headers=exc.headers,
    )


# @app.exception_handler(RequestValidationError)
# async def validation_exception_handler(
#     request: Request,
#     exc: RequestValidationError,
# ):
#     errors = exc.errors()

#     debug_message = "Validation errors:"
#     for error in errors:
#         debug_message += f"\nField: {error['loc']}, Error: {error['msg']}"

#     error_code = None

#     if errors:
#         first_error = errors[0]

#         field_name = first_error["loc"][-1]
#         error_type = first_error["type"]

#         error_code = VALIDATION_ERROR_MAPPING.get((field_name, error_type))

#     return JSONResponse(
#         status_code=422,
#         content={
#             "debug_message": debug_message.strip(),
#             "error_code": error_code,
#         },
#     )


# The exception structure stays consistent
# @app.exception_handler(Exception)
# async def unexpected_exception_handler(request, exc: Exception):
#     return JSONResponse(
#         status_code=500,
#         content={
#             "debug_message": "Internal server error",
#             "error_code": "INTERNAL_SERVER_ERROR",
#         },
#     )


# Allow requests from the frontend
origins = [
    "http://127.0.0.1:5173",
    # "http://192.168.1.105:5173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=[
        "GET",
        "POST",
        "PATCH",
        "DELETE",
    ],
    allow_headers=["Authorization", "Content-Type"],
)

# Only use when cloud doesn't support
# from fastapi.middleware.httpsredirect import HTTPSRedirectMiddleware
# if os.getenv("ENV") == "production":
#     app.add_middleware(HTTPSRedirectMiddleware)


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["Strict-Transport-Security"] = (
        "max-age=31536000; includeSubDomains"
    )
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

    # Allow 'self' for microphone
    response.headers["Permissions-Policy"] = (
        "geolocation=(), microphone=(self), camera=()"
    )

    # Allow loading from external secure HTTPS source
    response.headers["Content-Security-Policy"] = (
        "default-src 'self';"
        "style-src 'self' 'unsafe-inline' https:;"
        "script-src 'self' https://static.cloudflareinsights.com;"
        "media-src 'self' blob:;"
        "font-src 'self' https: data:;"
        "img-src 'self' https://placecats.com data:;"
    )

    return response


API_PREFIX = "/api"
for router_module in [
    account_router,
    audio_router,
    auth_router,
    brick_interaction_router,
    brick_memory_router,
    brick_review_router,
    brick_router,
    chat_router,
    island_router,
    context_search_router,
    explanation_router,
    learner_router,
    text_router,
]:
    app.include_router(router_module.router, prefix=API_PREFIX)


ASSETS_DIR.mkdir(parents=True, exist_ok=True)
app.mount(
    f"{API_PREFIX}/{ASSETS_DIR.name}",
    StaticFiles(directory=ASSETS_DIR.name),
    name=ASSETS_DIR.name,
)


# Extending OpenAPI
def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema

    openapi_schema = get_openapi(
        title="Lisenare API", version="0.1.1", routes=app.routes
    )

    schema_targets = {
        "Body_create_brick_bricks_post": BrickCreateRequest,
        "Body_update_brick_bricks__brick_id__patch": BrickUpdate,
    }
    schemas = openapi_schema.get("components", {}).get("schemas", {})

    for schema_key, model_class in schema_targets.items():
        if schema_key in schemas:
            properties = schemas[schema_key].get("properties", {})
            if "json_data" in properties:
                # Dynamically generate the string template using the new Field examples
                example_json_string = get_model_example_string(model_class)
                # Overwrite the Swagger example field cleanly
                properties["json_data"]["example"] = example_json_string

    app.openapi_schema = openapi_schema
    return app.openapi_schema


app.openapi = custom_openapi

app.frontend("/", directory="dist")
