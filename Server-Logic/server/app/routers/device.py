from fastapi import status, HTTPException, Depends, APIRouter
from sqlalchemy.orm import Session
from sqlalchemy.sql import func
from typing import List
from .. import models, schemas
from ..database import get_db
from ..dependencies import get_current_user

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

@router.post("/{device_id}/heartbeat", response_model=List[schemas.DeviceCommandOut])
def device_heartbeat(
    device_id: int, 
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Client calls this every 30s. Updates online status and returns pending commands."""
    device = db.query(models.Device).filter(
        models.Device.id == device_id,
        models.Device.user_id == current_user.id
    ).first()
    
    if not device:
        # Auto-create if it doesn't exist
        device = models.Device(id=device_id, user_id=current_user.id, device_name=f"Device-{device_id}")
        db.add(device)
    
    device.is_online = True
    device.last_seen_at = func.now()
    db.commit()

    # Fetch pending commands
    pending_commands = db.query(models.DeviceCommand).filter(
        models.DeviceCommand.device_id == device_id,
        models.DeviceCommand.status == 'pending'
    ).all()
    
    return pending_commands

@router.put("/{device_id}", response_model=schemas.DeviceOut)
def update_device(
    device_id: int,
    device_update: schemas.DeviceUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    device = db.query(models.Device).filter(
        models.Device.id == device_id,
        models.Device.user_id == current_user.id
    ).first()
    
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
        
    device.device_name = device_update.device_name
    db.commit()
    db.refresh(device)
    return device

@router.post("/{device_id}/command", response_model=schemas.DeviceCommandOut)
def queue_device_command(
    device_id: int,
    command: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Queues a command (e.g. 'WAKE', 'REVOKE') for a device from the UI."""
    device = db.query(models.Device).filter(
        models.Device.id == device_id,
        models.Device.user_id == current_user.id
    ).first()
    
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
        
    new_cmd = models.DeviceCommand(
        device_id=device_id,
        command=command,
        status='pending'
    )
    db.add(new_cmd)
    db.commit()
    db.refresh(new_cmd)
    return new_cmd

@router.post("/{device_id}/command/{command_id}/ack")
def ack_device_command(
    device_id: int,
    command_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Client calls this after executing a command."""
    cmd = db.query(models.DeviceCommand).filter(
        models.DeviceCommand.id == command_id,
        models.DeviceCommand.device_id == device_id
    ).first()
    
    if not cmd:
        raise HTTPException(status_code=404, detail="Command not found")
        
    cmd.status = 'completed'
    db.commit()
    return {"status": "ok"}
