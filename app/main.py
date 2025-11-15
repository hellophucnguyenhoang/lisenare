from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api import auth, recommendations, users, study_sessions, readings

app = FastAPI(title="Learning Platform API")

# Allow requests from the frontend (Vite default port 5173)
origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",  # in case of using 127.0.0.1 instead of localhost
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],          # list of allowed origins
    allow_credentials=True,
    allow_methods=["*"],            # allow all HTTP methods (GET, POST, etc.)
    allow_headers=["*"],            # allow all headers
)

# Include routers
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(recommendations.router)
app.include_router(study_sessions.router)
app.include_router(readings.router)
