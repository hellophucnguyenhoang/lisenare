from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import settings

from .database import delete_db, init_db
from .http_client import close_client, init_client
from .routers import (
    account_router,
    audio_router,
    auth_router,
    brick_router,
    chat_router,
    collection_router,
    context_search_router,
    learner_router,
    learning_card_router,
    snippet_interaction_router,
    snippet_router,
    test_router,
    text_router,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup code
    init_db()
    await init_client()
    yield
    # Shutdown code
    delete_db()
    await close_client()


app = FastAPI(title="Lisenare API", lifespan=lifespan)

# Allow requests from the frontend
origins = ["http://localhost:5173"]  # Vite default port 5173

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],  # allow all HTTP methods (GET, POST, etc.)
    allow_headers=["*"],  # allow all headers
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
app.include_router(snippet_interaction_router.router)
app.include_router(snippet_router.router)
app.include_router(text_router.router)

app.mount(
    f"/{settings.snippets_folder}",
    StaticFiles(directory=settings.snippets_folder),
    name=settings.snippets_folder,
)

app.mount(
    f"/{settings.brick_audios_folder}",
    StaticFiles(directory=settings.brick_audios_folder),
    name=settings.brick_audios_folder,
)
