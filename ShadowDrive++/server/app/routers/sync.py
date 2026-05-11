import os
import shutil
from fastapi import status, HTTPException, Depends, APIRouter, UploadFile, File
from sqlalchemy.orm import Session
from sqlalchemy.sql import func
from typing import List
from .. import models, schemas
from ..database import get_db

router = APIRouter(
    prefix="/sync",
    tags=['Sync']
)

# ─── Storage Config ──────────────────────────────────────────────────────────
# Local file storage for Week 3. Will be replaced by MinIO in Week 5.
UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

# ─── Hardcoded user_id for Week 3 ────────────────────────────────────────────
# Rohan's client does not send auth headers or user_id yet.
# Until auth is implemented, we assume a single user (id=1).
DEFAULT_USER_ID = 1


@router.post(
    "/announce",
    status_code=status.HTTP_201_CREATED,
    response_model=schemas.MetadataResponse
)
def announce_metadata(payload: schemas.MetadataAnnounce, db: Session = Depends(get_db)):
    """
    Rohan's sync_engine.py calls this with:
        {"path": "filename.txt", "hash": "abc...", "event": "new|modified|deleted"}

    Logic:
        1. Find-or-create the File record.
        2. If event is "deleted", mark the file as soft-deleted.
        3. If event is "new" or "modified", check if a Version with this hash
           already exists (deduplication).  Return 200 if so, 201 if the
           server needs the actual file bytes uploaded.
    """
    user_id = DEFAULT_USER_ID

    # ── Step 1: Find or create the File record ──────────────────────────────
    file_record = db.query(models.File).filter(
        models.File.user_id == user_id,
        models.File.file_path == payload.path
    ).first()

    if not file_record:
        file_record = models.File(
            user_id=user_id,
            file_path=payload.path,
            is_deleted=False
        )
        db.add(file_record)
        db.flush()  # generate file_record.id without committing

    # ── Step 2: Handle deletion events ───────────────────────────────────────
    if payload.event == "deleted":
        file_record.is_deleted = True
        file_record.updated_at = func.now()
        db.commit()

        return schemas.MetadataResponse(
            status="deleted_acknowledged",
            file_id=file_record.id,
            version_id=None,
            upload_required=False
        )

    # ── Step 3: Un-delete if file reappears ──────────────────────────────────
    if file_record.is_deleted:
        file_record.is_deleted = False

    # ── Step 4: Hash deduplication check ─────────────────────────────────────
    existing_version = db.query(models.Version).filter(
        models.Version.file_id == file_record.id,
        models.Version.hash == payload.hash
    ).first()

    if existing_version:
        # Server already has this exact version — no upload needed
        file_record.updated_at = func.now()
        db.commit()

        return schemas.MetadataResponse(
            status="already_synced",
            file_id=file_record.id,
            version_id=existing_version.id,
            upload_required=False
        )

    # ── Step 5: Create a new pending version ─────────────────────────────────
    # Determine next version number
    latest_version = db.query(models.Version).filter(
        models.Version.file_id == file_record.id
    ).order_by(models.Version.version_num.desc()).first()

    next_version_num = (latest_version.version_num + 1) if latest_version else 1

    # Storage path is a placeholder until the actual upload arrives
    storage_path = f"uploads/{user_id}/{payload.path}/v{next_version_num}"

    new_version = models.Version(
        file_id=file_record.id,
        version_num=next_version_num,
        hash=payload.hash or "",
        size_bytes=0,  # Will be updated when the actual file is uploaded
        storage_path=storage_path
    )
    db.add(new_version)
    file_record.updated_at = func.now()
    db.commit()
    db.refresh(new_version)

    return schemas.MetadataResponse(
        status="accepted",
        file_id=file_record.id,
        version_id=new_version.id,
        upload_required=True
    )


@router.post("/upload", status_code=status.HTTP_200_OK)
def upload_file(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """
    Rohan's network_client.py calls this with:
        files={"file": (remote_path, file_handle)}

    The filename from the multipart header IS the remote_path (the relative
    file path the client wants to store on the server).

    Logic:
        1. Locate the File record by path.
        2. Find the latest Version record (the pending one created by /announce).
        3. Write the bytes to local disk (MinIO replacement in Week 5).
        4. Update the Version's size_bytes.
    """
    user_id = DEFAULT_USER_ID
    remote_path = file.filename

    if not remote_path:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Filename missing from upload"
        )

    # ── Step 1: Locate the file record ───────────────────────────────────────
    file_record = db.query(models.File).filter(
        models.File.user_id == user_id,
        models.File.file_path == remote_path
    ).first()

    if not file_record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No metadata announced for '{remote_path}'. Call /sync/announce first."
        )

    # ── Step 2: Get the latest version (created by /announce) ────────────────
    version_record = db.query(models.Version).filter(
        models.Version.file_id == file_record.id
    ).order_by(models.Version.version_num.desc()).first()

    if not version_record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No version record found. Call /sync/announce first."
        )

    # ── Step 3: Write file to local disk ─────────────────────────────────────
    dest_dir = os.path.join(UPLOAD_DIR, str(user_id), remote_path)
    os.makedirs(os.path.dirname(dest_dir) if os.path.dirname(dest_dir) else dest_dir, exist_ok=True)

    dest_path = os.path.join(
        UPLOAD_DIR, str(user_id), f"{remote_path}_v{version_record.version_num}"
    )
    os.makedirs(os.path.dirname(dest_path), exist_ok=True)

    total_bytes = 0
    with open(dest_path, "wb") as out:
        while True:
            chunk = file.file.read(4 * 1024 * 1024)  # 4MB chunks
            if not chunk:
                break
            out.write(chunk)
            total_bytes += len(chunk)

    # ── Step 4: Update version record ────────────────────────────────────────
    version_record.size_bytes = total_bytes
    version_record.storage_path = dest_path
    db.commit()

    return {"status": "uploaded", "file": remote_path, "bytes": total_bytes}


@router.get("/metadata", response_model=List[schemas.FileVersionOut])
def get_metadata(db: Session = Depends(get_db)):
    """
    Returns the latest version of every non-deleted file for the default user.
    Rohan's client will eventually call this to discover what files are on the
    server that it doesn't have locally.
    """
    user_id = DEFAULT_USER_ID

    # Get all active (non-deleted) files for this user
    files = db.query(models.File).filter(
        models.File.user_id == user_id,
        models.File.is_deleted == False
    ).all()

    result = []
    for f in files:
        latest = db.query(models.Version).filter(
            models.Version.file_id == f.id
        ).order_by(models.Version.version_num.desc()).first()

        if latest:
            result.append(schemas.FileVersionOut(
                file_path=f.file_path,
                hash=latest.hash,
                version_num=latest.version_num,
                size_bytes=latest.size_bytes
            ))

    return result
