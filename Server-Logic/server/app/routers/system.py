from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from ..database import get_db
from ..dependencies import get_current_user
from .. import models
import random

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
    
    # Only count nodes that are currently online
    online_nodes = db.query(models.Device).filter(
        models.Device.user_id == current_user.id,
        models.Device.is_online == True
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

    return {
        "totalNodes": online_nodes,
        "syncRate": 100.00,
        "metrics": [
            {
                "id": "db",
                "name": "Database Load",
                "value": "Low",
                "status": "Healthy",
                "history": [1, 2, 1, 3, 2, 1, 1, 2, 1, 1]
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
