from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .database import create_db_and_tables
from .config import settings
import os

if not os.path.exists(settings.db_url):
    print(f"{settings.db_url} not found, create a new one.")
    create_db_and_tables()

app = FastAPI(title="Lisenare API")

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
