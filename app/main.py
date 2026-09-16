from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.config import settings
from app.schemas import BrickCreateRequest, BrickUpdate
from utils.form_utils import get_model_example_string

from . import database, http_client
from .exceptions import RequestException
from .routers import (
    account_router,
    audio_router,
    auth_router,
    brick_interaction_router,
    brick_memory_router,
    brick_router,
    chat_router,
    collection_router,
    context_search_router,
    explanation_router,
    learner_router,
    text_router,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup code
    database.init_db()
    http_client.init_client()
    await http_client.init_async_client()
    yield
    # Shutdown code
    # database.delete_db()
    http_client.close_client()
    await http_client.close_async_client()


app = FastAPI(title="Lisenare API", lifespan=lifespan)


# Unified exception response structure
@app.exception_handler(RequestException)
async def request_exception_handler(request, exc: RequestException):
    return JSONResponse(
        status_code=exc.status_code,
        content=exc.detail,
        headers=exc.headers,
    )


# Override the default system exception
# to keep the response structure consistent
@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request, exc: StarletteHTTPException):
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
    "http://192.168.1.105:5173",
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

API_PREFIX = "/api"
for router_module in [
    account_router,
    audio_router,
    auth_router,
    brick_interaction_router,
    brick_memory_router,
    brick_router,
    chat_router,
    collection_router,
    context_search_router,
    explanation_router,
    learner_router,
    text_router,
]:
    app.include_router(router_module.router, prefix=API_PREFIX)


for folder in [
    settings.brick_audios_folder,
    settings.learner_audios_folder,
    settings.generated_audios_folder,
]:
    app.mount(
        f"{API_PREFIX}/{folder}", StaticFiles(directory=folder), name=folder
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

# app.frontend("/", directory="dist")
