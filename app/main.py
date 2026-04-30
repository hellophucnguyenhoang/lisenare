from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import database
from .http_client import close_client, init_client
from .routers import (
    account_router,
    audio_router,
    auth_router,
    brick_router,
    chat_router,
    collection_router,
    context_search_router,
    grammar_router,
    learner_router,
    learning_card_router,
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

# Allow requests from the frontend
origins = [
    "http://localhost:8000",
    "http://127.0.0.1:8000",
    "http://0.0.0.0:8000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=[
        "GET",
        "POST",
        "PUT",
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
app.include_router(learner_router.router)
app.include_router(learning_card_router.router)
app.include_router(push_token_router.router)
app.include_router(snippet_interaction_router.router)
app.include_router(snippet_router.router)
app.include_router(text_router.router)
app.include_router(grammar_router.router)
