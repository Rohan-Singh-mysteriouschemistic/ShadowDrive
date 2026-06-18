import logging
import asyncio
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, status, HTTPException
from sqlalchemy.orm import Session
from . import models, schemas, utils, storage
from .database import engine, SessionLocal
from .routers.events import listen_to_redis

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

models.Base.metadata.create_all(bind=engine)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup/shutdown lifecycle for the FastAPI application.

    On startup:
        - Starts the Redis event bridge listener (RQ -> SSE).
        - Ensures the MinIO 'shadowdrive' bucket exists.
    """
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    redis_task = asyncio.create_task(listen_to_redis(redis_url))

    try:
        storage.ensure_bucket_exists()
        logger.info("MinIO bucket initialized successfully.")
    except Exception as e:
        logger.warning("MinIO not reachable at startup: %s (will retry on first upload)", e)
    
    yield

    # Cleanup
    redis_task.cancel()
    try:
        await redis_task
    except asyncio.CancelledError:
        pass


from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="ShadowDrive++ Server", version="0.5.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:8001", "http://127.0.0.1:5173", "http://127.0.0.1:8001"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ─── Health Check (Rohan's client pings this before every sync cycle) ────────
@app.get("/health")
def health_check():
    return {"status": "ok"}


# ─── Router Registration ────────────────────────────────────────────────────
from .routers import user, device, sync, auth, system, events

app.include_router(user.router)
app.include_router(device.router)
app.include_router(sync.router)
app.include_router(auth.router)
app.include_router(system.router)
app.include_router(events.router)
