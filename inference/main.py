from fastapi import FastAPI, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from config import logger
from routers import audio_router, fsrs_router, text_router

app = FastAPI(title="Lisenare Inference API")


# The exception structure stays consistent
@app.exception_handler(Exception)
async def unexpected_exception_handler(request, exc: Exception):
    # Use exception to record ERROR traceback
    logger.exception(
        "Unhandled exception on %s %s",
        request.method,
        request.url.path,
    )
    # FastAPI's native HTTP/Validation error envelope default
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal Server Error"},
    )


origins = ["http://127.0.0.1:8000"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(audio_router.router)
app.include_router(text_router.router)
app.include_router(fsrs_router.router)
