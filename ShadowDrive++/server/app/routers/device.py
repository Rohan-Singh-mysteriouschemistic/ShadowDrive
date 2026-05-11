from fastapi import status, HTTPException, Depends, APIRouter
from sqlalchemy.orm import Session
from sqlalchemy.sql import func
from typing import List
from .. import models, schemas
from ..database import get_db

router = APIRouter(
    prefix="/devices",
    tags=['Devices']
)

@router.post("/register", status_code=status.HTTP_201_CREATED, response_model=schemas.DeviceOut)
def register_device(device: schemas.DeviceCreate, db: Session = Depends(get_db)):
    
    # Check if user exists
    user = db.query(models.User).filter(models.User.id == device.user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
        
    # Check if device already exists for this user
    existing_device = db.query(models.Device).filter(
        models.Device.user_id == device.user_id,
        models.Device.device_name == device.device_name
    ).first()
    
    if existing_device:
        existing_device.is_online = True
        existing_device.last_seen_at = func.now()
        db.commit()
        db.refresh(existing_device)
        return existing_device
        
    # Create new device
    new_device = models.Device(
        user_id=device.user_id,
        device_name=device.device_name,
        is_online=True,
        last_seen_at=func.now()
    )
    
    db.add(new_device)
    db.commit()
    db.refresh(new_device)
    
    return new_device
