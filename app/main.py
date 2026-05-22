from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from . import database
from .exceptions import RequestException
from .http_client import close_client, init_client
from .routers import (
    account_router,
    audio_router,
    auth_router,
    brick_router,
    chat_router,
    collection_router,
    context_search_router,
    explanation_router,
    grammar_router,
    learner_router,
    learning_card_router,
    practice_router,
    push_token_router,
    snippet_interaction_router,
    snippet_router,
    test_router,
    text_router,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup code
    database.init_db()
    await init_client()
    yield
    # Shutdown code
    # database.delete_db()
    await close_client()


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
    "http://localhost:8000",
    "http://127.0.0.1:8000",
    "http://0.0.0.0:8000",
    "http://192.168.100.109:8000"
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

app.include_router(test_router.router)
app.include_router(account_router.router)
app.include_router(audio_router.router)
app.include_router(auth_router.router)
app.include_router(chat_router.router)
app.include_router(brick_router.router)
app.include_router(collection_router.router)
app.include_router(context_search_router.router)
app.include_router(explanation_router.router)
app.include_router(learner_router.router)
app.include_router(learning_card_router.router)
app.include_router(push_token_router.router)
app.include_router(snippet_interaction_router.router)
app.include_router(snippet_router.router)
app.include_router(text_router.router)
app.include_router(grammar_router.router)
app.include_router(practice_router.router)
