from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text
from loguru import logger
import os
import redis
from ..database import get_db
from ..dependencies import get_current_user
from .. import models

router = APIRouter(prefix="/system", tags=["system"])

@router.get("/telemetry")
def get_telemetry(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """
    Returns system health telemetry for the UI.
    """
    from sqlalchemy import func
    
    # Only count nodes that are currently online (excluding the browser interface)
    online_nodes = db.query(models.Device).filter(
        models.Device.user_id == current_user.id,
        models.Device.is_online == True,
        models.Device.device_name != "Web Browser"
    ).count()

    # Calculate actual storage used by user
    storage_used_bytes = db.query(func.sum(models.Version.size_bytes)).join(
        models.File, models.Version.file_id == models.File.id
    ).filter(
        models.File.user_id == current_user.id
    ).scalar() or 0
    
    # Format storage
    def format_bytes(bytes_count):
        if bytes_count == 0: return "0 B"
        k = 1024
        sizes = ['B', 'KB', 'MB', 'GB', 'TB']
        i = 0
        while bytes_count >= k and i < len(sizes) - 1:
            bytes_count /= k
            i += 1
        return f"{bytes_count:.2f} {sizes[i]}"

    storage_str = format_bytes(storage_used_bytes)

    # Perform connection handshakes
    postgres_ok = False
    try:
        db.execute(text("SELECT 1"))
        postgres_ok = True
    except Exception as e:
        logger.error("Postgres health check failed: {}", e)

    minio_ok = False
    try:
        from .. import storage
        s3 = storage._get_s3_client()
        s3.list_buckets()
        minio_ok = True
    except Exception as e:
        logger.error("MinIO health check failed: {}", e)

    redis_ok = False
    try:
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        r = redis.Redis.from_url(redis_url, socket_timeout=1.0)
        r.ping()
        redis_ok = True
    except Exception as e:
        logger.error("Redis health check failed: {}", e)

    # Dynamic sync rate
    components = [postgres_ok, minio_ok, redis_ok]
    healthy_count = sum(1 for c in components if c)
    sync_rate = round((healthy_count / len(components)) * 100, 2)

    return {
        "totalNodes": online_nodes,
        "syncRate": sync_rate,
        "metrics": [
            {
                "id": "db",
                "name": "Database Connection",
                "value": "Connected" if postgres_ok else "Offline",
                "status": "Healthy" if postgres_ok else "Critical",
                "history": [1 if postgres_ok else 0 for _ in range(10)]
            },
            {
                "id": "minio",
                "name": "MinIO Object Storage",
                "value": "Connected" if minio_ok else "Offline",
                "status": "Healthy" if minio_ok else "Critical",
                "history": [1 if minio_ok else 0 for _ in range(10)]
            },
            {
                "id": "redis",
                "name": "Redis Event Bridge",
                "value": "Connected" if redis_ok else "Offline",
                "status": "Healthy" if redis_ok else "Critical",
                "history": [1 if redis_ok else 0 for _ in range(10)]
            },
            {
                "id": "storage",
                "name": "Storage Used",
                "value": storage_str,
                "status": "Healthy",
                "history": [storage_used_bytes for _ in range(10)]
            }
        ]
    }

@router.get("/diagnostics")
def get_diagnostics(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """
    Runs actual connection checks for PostgreSQL, MinIO, and Redis.
    """
    postgres_ok = False
    try:
        db.execute(text("SELECT 1"))
        postgres_ok = True
    except Exception:
        pass
        
    minio_ok = False
    try:
        from .. import storage
        s3 = storage._get_s3_client()
        s3.list_buckets()
        minio_ok = True
    except Exception:
        pass

    redis_ok = False
    try:
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        r = redis.Redis.from_url(redis_url, socket_timeout=1.0)
        r.ping()
        redis_ok = True
    except Exception:
        pass

    online_nodes = db.query(models.Device).filter(
        models.Device.user_id == current_user.id,
        models.Device.is_online == True,
        models.Device.device_name != "Web Browser"
    ).count()

    return {
        "postgres": "OK" if postgres_ok else "ERROR",
        "minio": "OK" if minio_ok else "ERROR",
        "redis": "OK" if redis_ok else "ERROR",
        "nodes": f"{online_nodes} Connected" if online_nodes > 0 else "None Connected"
    }

@router.get("/nodes")
def get_nodes(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """
    Returns a list of registered devices for the current user.
    """
    devices = db.query(models.Device).filter(models.Device.user_id == current_user.id).all()
    
    # Auto-register or update a "Web Browser" device since they are fetching nodes from the web UI
    from sqlalchemy.sql import func
    web_device = next((d for d in devices if d.device_name == "Web Browser"), None)
    if web_device:
        web_device.is_online = True
        web_device.last_seen_at = func.now()
    else:
        web_device = models.Device(
            user_id=current_user.id,
            device_name="Web Browser",
            is_online=True,
            last_seen_at=func.now()
        )
        db.add(web_device)
        devices.append(web_device)

    # Calculate online status dynamically
    from datetime import datetime, timezone, timedelta
    
    now = datetime.now(timezone.utc)
    for device in devices:
        if device.device_name == "Web Browser":
            device.is_online = True
            continue
            
        if device.last_seen_at:
            # Ensure last_seen_at is timezone-aware
            last_seen = device.last_seen_at
            if last_seen.tzinfo is None:
                last_seen = last_seen.replace(tzinfo=timezone.utc)
                
            if now - last_seen > timedelta(minutes=2):
                device.is_online = False
            else:
                device.is_online = True
        else:
            device.is_online = False
            
    db.commit() # Save the updated statuses
    return devices
