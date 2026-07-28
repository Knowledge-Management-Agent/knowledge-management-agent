import logging
import time

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.api import auth, generate, health, ingest, query
from app.config import get_settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("kb-agent")

settings = get_settings()

app = FastAPI(title="Knowledge Management Agent PoC")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    elapsed_ms = (time.perf_counter() - start) * 1000
    logger.info(
        "%s %s -> %s (%.1fms)",
        request.method,
        request.url.path,
        response.status_code,
        elapsed_ms,
    )
    return response


app.include_router(health.router)
app.include_router(auth.router)
app.include_router(ingest.router)
app.include_router(query.router)
app.include_router(generate.router)
