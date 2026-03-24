from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routers import audios, texts

app = FastAPI(title="Lisenare API")

origins = ["http://127.0.0.1:8000"]  # API Gateway default port

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(audios.router)
app.include_router(texts.router)
