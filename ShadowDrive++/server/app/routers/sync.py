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
# Local file storage for Week 3-4. Will be replaced by MinIO in Week 5.
UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

# ─── Hardcoded user_id for Week 3-4 ──────────────────────────────────────────
# Rohan's client does not send auth headers or user_id yet.
# Until auth is implemented, we assume a single user (id=1).
DEFAULT_USER_ID = 1

# ─── Constants for the 0-byte file edge case ─────────────────────────────────
EMPTY_FILE_SHA256 = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"


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

    Week 4 Hardening:
        - Scenario A: 0-byte files produce a valid SHA-256 hash (the "empty hash").
          We now accept this gracefully and create a version with size_bytes=0
          and upload_required=False (no bytes to transfer).
        - Scenario B: If announce succeeds but upload never arrives, the
          Version record is left with size_bytes=0. On the next sync cycle,
          the client re-announces. The hash dedup check finds the existing
          version. If it has size_bytes=0 AND the hash is NOT the empty-file
          hash, the server knows the upload was interrupted—it deletes the
          stale version and re-creates a fresh one with upload_required=True.
        - Scenario C: All database mutations inside a single try/except that
          calls db.rollback() on error. This guarantees clean sessions even
          if the server crashes mid-transaction.
    """
    user_id = DEFAULT_USER_ID

    try:
        # ── Step 1: Find or create the File record ───────────────────────
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

        # ── Step 2: Handle deletion events ───────────────────────────────
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

        # ── Step 3: Un-delete if file reappears ──────────────────────────
        if file_record.is_deleted:
            file_record.is_deleted = False

        # ── Step 4: Hash deduplication check ─────────────────────────────
        incoming_hash = payload.hash or EMPTY_FILE_SHA256
        existing_version = db.query(models.Version).filter(
            models.Version.file_id == file_record.id,
            models.Version.hash == incoming_hash
        ).first()

        if existing_version:
            # ── Week 4 Fix (Scenario B): Interrupted Upload Recovery ─────
            # If the hash matches but size_bytes is 0 and the hash is NOT
            # the well-known empty-file hash, then a previous /announce
            # succeeded but the /upload never completed (client dropped).
            # We must delete the stale version and let the client re-upload.
            is_empty_file = (incoming_hash == EMPTY_FILE_SHA256)

            if existing_version.size_bytes == 0 and not is_empty_file:
                # Stale pending version from an interrupted sync cycle.
                # Delete it and fall through to create a fresh one.
                db.delete(existing_version)
                db.flush()
            else:
                # Server genuinely has this version (or it's a 0-byte file).
                file_record.updated_at = func.now()
                db.commit()

                return schemas.MetadataResponse(
                    status="already_synced",
                    file_id=file_record.id,
                    version_id=existing_version.id,
                    upload_required=False
                )

        # ── Step 5: Handle 0-byte files (Scenario A) ────────────────────
        # A 0-byte file has a valid hash but zero bytes to upload.
        # We create the version record immediately as "complete".
        if incoming_hash == EMPTY_FILE_SHA256:
            latest_version = db.query(models.Version).filter(
                models.Version.file_id == file_record.id
            ).order_by(models.Version.version_num.desc()).first()

            next_version_num = (latest_version.version_num + 1) if latest_version else 1
            storage_path = f"uploads/{user_id}/{payload.path}/v{next_version_num}"

            new_version = models.Version(
                file_id=file_record.id,
                version_num=next_version_num,
                hash=incoming_hash,
                size_bytes=0,
                storage_path=storage_path
            )
            db.add(new_version)
            file_record.updated_at = func.now()
            db.commit()
            db.refresh(new_version)

            # Create an actual empty file on disk for consistency
            dest_path = os.path.join(
                UPLOAD_DIR, str(user_id), f"{payload.path}_v{next_version_num}"
            )
            os.makedirs(os.path.dirname(dest_path), exist_ok=True)
            open(dest_path, "wb").close()

            return schemas.MetadataResponse(
                status="accepted_empty",
                file_id=file_record.id,
                version_id=new_version.id,
                upload_required=False
            )

        # ── Step 6: Create a new pending version ─────────────────────────
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
            hash=incoming_hash,
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

    except Exception:
        # ── Week 4 Fix (Scenario C): Clean rollback on any error ─────────
        db.rollback()
        raise


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

    Week 4 Hardening:
        - Writes to a temporary file first, then renames atomically. If the
          server crashes mid-write, only the temp file is corrupted—never
          the final destination.
        - Wraps all DB mutations in try/except with rollback.
    """
    user_id = DEFAULT_USER_ID
    remote_path = file.filename

    if not remote_path:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Filename missing from upload"
        )

    try:
        # ── Step 1: Locate the file record ───────────────────────────────
        file_record = db.query(models.File).filter(
            models.File.user_id == user_id,
            models.File.file_path == remote_path
        ).first()

        if not file_record:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No metadata announced for '{remote_path}'. Call /sync/announce first."
            )

        # ── Step 2: Get the latest version (created by /announce) ────────
        version_record = db.query(models.Version).filter(
            models.Version.file_id == file_record.id
        ).order_by(models.Version.version_num.desc()).first()

        if not version_record:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No version record found. Call /sync/announce first."
            )

        # ── Step 3: Write file to local disk (atomic via temp file) ──────
        dest_path = os.path.join(
            UPLOAD_DIR, str(user_id), f"{remote_path}_v{version_record.version_num}"
        )
        os.makedirs(os.path.dirname(dest_path), exist_ok=True)

        # Write to a temp file first, then rename. This ensures that if the
        # server crashes mid-write, the final destination is never corrupted.
        temp_path = dest_path + ".tmp"

        total_bytes = 0
        try:
            with open(temp_path, "wb") as out:
                while True:
                    chunk = file.file.read(4 * 1024 * 1024)  # 4MB chunks
                    if not chunk:
                        break
                    out.write(chunk)
                    total_bytes += len(chunk)

            # Atomic rename: temp file → final destination
            shutil.move(temp_path, dest_path)

        except Exception:
            # Clean up the temp file if writing fails
            if os.path.exists(temp_path):
                os.remove(temp_path)
            raise

        # ── Step 4: Update version record ────────────────────────────────
        version_record.size_bytes = total_bytes
        version_record.storage_path = dest_path
        db.commit()

        return {"status": "uploaded", "file": remote_path, "bytes": total_bytes}

    except HTTPException:
        raise  # Re-raise HTTP exceptions as-is
    except Exception:
        db.rollback()
        raise


@router.get("/metadata", response_model=List[schemas.FileVersionOut])
def get_metadata(db: Session = Depends(get_db)):
    """
    Returns the latest version of every non-deleted file for the default user.
    Rohan's client will eventually call this to discover what files are on the
    server that it doesn't have locally.
    """
    user_id = DEFAULT_USER_ID

    try:
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

    except Exception:
        db.rollback()
        raise
