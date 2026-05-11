from fastapi import FastAPI, Depends, status, HTTPException
from sqlalchemy.orm import Session
from . import models, schemas, utils
from .database import engine, SessionLocal

models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="ShadowDrive++ Server", version="0.3.0")

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
from .routers import user, device, sync

app.include_router(user.router)
app.include_router(device.router)
app.include_router(sync.router)
