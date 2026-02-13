from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .database import init_db, delete_db
from .http_client import init_client, close_client
from .routers import (
    accounts,
    audios,
    auth,
    bricks, 
    collections, 
    context_search,
    learners,
    texts
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup code
    init_db()
    await init_client()
    yield
    # Shutdown code
    # delete_db()
    await close_client()

app = FastAPI(title="Lisenare API", lifespan=lifespan)

# Allow requests from the frontend
origins = [
    "http://localhost:5173" # Vite default port 5173
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],            # allow all HTTP methods (GET, POST, etc.)
    allow_headers=["*"],            # allow all headers
)

app.include_router(accounts.router)
app.include_router(audios.router)
app.include_router(auth.router)
app.include_router(bricks.router)
app.include_router(collections.router)
app.include_router(context_search.router)
app.include_router(learners.router)
app.include_router(texts.router)
