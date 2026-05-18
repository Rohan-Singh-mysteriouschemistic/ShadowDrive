import os
import shutil
import logging
from fastapi import status, HTTPException, Depends, APIRouter, UploadFile, File, Form
from sqlalchemy.orm import Session
from sqlalchemy.sql import func
from typing import List
from .. import models, schemas
from ..database import get_db
from .. import storage

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/sync",
    tags=['Sync']
)

# ─── Legacy Storage Config (kept for backward compatibility) ─────────────────
# Local file storage from Weeks 3-4.  The /upload endpoint now writes to MinIO
# instead, but we keep the dir reference for any residual code paths.
UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

# ─── Hardcoded user_id for Week 3-5 ──────────────────────────────────────────
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
                # Also clean up any orphaned chunk records for this version.
                db.query(models.ChunkUpload).filter(
                    models.ChunkUpload.version_id == existing_version.id
                ).delete()
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
            storage_key = f"{user_id}/{payload.path}/v{next_version_num}"

            new_version = models.Version(
                file_id=file_record.id,
                version_num=next_version_num,
                hash=incoming_hash,
                size_bytes=0,
                storage_path=storage_key
            )
            db.add(new_version)
            file_record.updated_at = func.now()
            db.commit()
            db.refresh(new_version)

            # Write an empty object to MinIO for consistency
            try:
                storage.put_object(storage_key, b"")
            except Exception as e:
                logger.warning("Failed to write empty object to MinIO: %s", e)

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

        # Storage path is now a MinIO key
        storage_key = f"{user_id}/{payload.path}/v{next_version_num}"

        new_version = models.Version(
            file_id=file_record.id,
            version_num=next_version_num,
            hash=incoming_hash,
            size_bytes=0,  # Will be updated when the actual file is uploaded
            storage_path=storage_key
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

    Week 5 Update: Writes to MinIO instead of local disk.
    Small files (single-shot upload) still use this endpoint.
    Large files should use /upload_chunk instead.

    Week 4 Hardening preserved:
        - Wraps all DB mutations in try/except with rollback.
        - Atomic write semantics provided by MinIO's PUT (S3 PUTs are atomic).
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

        # ── Step 3: Read all bytes and upload to MinIO ───────────────────
        file_bytes = file.file.read()
        total_bytes = len(file_bytes)

        storage_key = version_record.storage_path
        storage.put_object(storage_key, file_bytes)

        # ── Step 4: Update version record ────────────────────────────────
        version_record.size_bytes = total_bytes
        version_record.storage_path = storage_key
        db.commit()

        return {"status": "uploaded", "file": remote_path, "bytes": total_bytes}

    except HTTPException:
        raise  # Re-raise HTTP exceptions as-is
    except Exception:
        db.rollback()
        raise


# ─── Week 5: Chunked Upload Endpoint ─────────────────────────────────────────

@router.post(
    "/upload_chunk",
    status_code=status.HTTP_200_OK,
    response_model=schemas.ChunkUploadResponse
)
def upload_chunk(
    chunk: UploadFile = File(...),
    version_id: int = Form(...),
    chunk_index: int = Form(...),
    total_chunks: int = Form(...),
    file_hash: str = Form(...),
    db: Session = Depends(get_db)
):
    """
    Chunked upload endpoint for large files (Week 5).

    Rohan's upload worker calls this once per chunk:
        POST /sync/upload_chunk
        Form fields: version_id, chunk_index, total_chunks, file_hash
        File field:  chunk (the binary chunk data)

    Flow:
        1. Validate that the version_id exists and is pending (size_bytes == 0).
        2. Store the chunk bytes in MinIO under a chunk-specific key.
        3. Record the chunk in the chunk_uploads table.
        4. If all chunks have been received, trigger assembly:
           a. Concatenate all chunks in order into a single object.
           b. Update the version record with the final size and storage path.
           c. Delete the individual chunk records and objects.
        5. Return the current progress to the client.

    Idempotency:
        If the same (version_id, chunk_index) is uploaded again (e.g. after a
        network retry), the existing chunk record is updated in place—no
        duplicate rows are created.  This preserves Week 4's idempotent
        recovery guarantees.
    """
    user_id = DEFAULT_USER_ID

    try:
        # ── Step 1: Validate version exists ──────────────────────────────
        version_record = db.query(models.Version).filter(
            models.Version.id == version_id
        ).first()

        if not version_record:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Version {version_id} not found. Call /sync/announce first."
            )

        # Validate chunk_index bounds
        if chunk_index < 0 or chunk_index >= total_chunks:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"chunk_index {chunk_index} out of range [0, {total_chunks})."
            )

        # ── Step 2: Store chunk bytes in MinIO ───────────────────────────
        chunk_bytes = chunk.file.read()
        chunk_size = len(chunk_bytes)

        # Key format: {user_id}/{file_path}/v{version}/chunks/{index}
        file_record = db.query(models.File).filter(
            models.File.id == version_record.file_id
        ).first()

        chunk_key = (
            f"{user_id}/{file_record.file_path}"
            f"/v{version_record.version_num}"
            f"/chunks/{chunk_index}"
        )

        storage.put_object(chunk_key, chunk_bytes)

        # ── Step 3: Record chunk in DB (upsert for idempotency) ──────────
        existing_chunk = db.query(models.ChunkUpload).filter(
            models.ChunkUpload.version_id == version_id,
            models.ChunkUpload.chunk_index == chunk_index
        ).first()

        if existing_chunk:
            # Idempotent retry — update the existing record
            existing_chunk.chunk_storage_key = chunk_key
            existing_chunk.size_bytes = chunk_size
            existing_chunk.received_at = func.now()
        else:
            new_chunk = models.ChunkUpload(
                version_id=version_id,
                chunk_index=chunk_index,
                total_chunks=total_chunks,
                chunk_storage_key=chunk_key,
                size_bytes=chunk_size
            )
            db.add(new_chunk)

        db.flush()

        # ── Step 4: Check if all chunks received ────────────────────────
        received_count = db.query(models.ChunkUpload).filter(
            models.ChunkUpload.version_id == version_id
        ).count()

        assembled = False

        if received_count >= total_chunks:
            # All chunks received — trigger assembly
            all_chunks = db.query(models.ChunkUpload).filter(
                models.ChunkUpload.version_id == version_id
            ).order_by(models.ChunkUpload.chunk_index.asc()).all()

            chunk_keys = [c.chunk_storage_key for c in all_chunks]
            final_key = version_record.storage_path  # e.g. "1/docs/readme.txt/v2"

            total_bytes = storage.assemble_chunks(chunk_keys, final_key)

            # Update version record with final assembled size
            version_record.size_bytes = total_bytes
            assembled = True

            # Clean up chunk records from the database
            db.query(models.ChunkUpload).filter(
                models.ChunkUpload.version_id == version_id
            ).delete()

            logger.info(
                "Assembled file version_id=%d (%d chunks, %d bytes)",
                version_id, total_chunks, total_bytes
            )

        db.commit()

        return schemas.ChunkUploadResponse(
            status="assembled" if assembled else "chunk_received",
            version_id=version_id,
            chunk_index=chunk_index,
            chunks_received=min(received_count, total_chunks),
            total_chunks=total_chunks,
            assembled=assembled
        )

    except HTTPException:
        raise
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
