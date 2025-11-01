from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.database import create_db_and_tables, get_session
from seed_data import seed_topics, seed_readings, seed_users
from app.api import users, topics, readings, study_sessions, interactions
import os 
from app.config import settings

app = FastAPI(title="Learning Platform API")

# Allow requests from the frontend (Vite default port 5173)
origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",  # in case of using 127.0.0.1 instead of localhost
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,          # list of allowed origins
    allow_credentials=True,
    allow_methods=["*"],            # allow all HTTP methods (GET, POST, etc.)
    allow_headers=["*"],            # allow all headers
)

# Create DB tables
@app.on_event("startup")
def on_startup():
    db_file = settings.database_file

    if not os.path.exists(db_file):
        print(f"Database {db_file} not found. Creating and seeding...")
        create_db_and_tables()
        if settings.seed_on_startup:
            with next(get_session()) as session:
                topics = seed_topics(session)
                readings = seed_readings(session, topics)
                seed_users(session)
                print("Seeding complete!")
    else:
        print(f"Database {db_file} exists. Skipping creation & seeding.")

# Include routers
app.include_router(users.router)
app.include_router(topics.router)
app.include_router(readings.router)
app.include_router(study_sessions.router)
app.include_router(interactions.router)