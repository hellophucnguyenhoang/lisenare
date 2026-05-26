from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routers import audio_router, text_router

app = FastAPI(title="Lisenare API")

origins = ["http://127.0.0.1:8000"]  # API Gateway default port

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(audio_router.router)
app.include_router(text_router.router)
