import os
import shutil
import logging
import hashlib
from fastapi import status, HTTPException, Depends, APIRouter, UploadFile, File, Form
from fastapi.responses import JSONResponse, Response
from sqlalchemy.orm import Session
from sqlalchemy.sql import func
from sqlalchemy import text
from typing import List
from .. import models, schemas
from ..database import get_db
from .. import storage
from ..models import UploadStatus
from ..worker import enqueue_verify, enqueue_assemble_and_verify
from ..services.metadata import process_metadata_sync, _fire_event
from ..dependencies import get_current_user

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
# NOTE: DEFAULT_USER_ID and EMPTY_FILE_SHA256 are now owned by
#       services/metadata.py.  Keep this reference only for the
#       remaining endpoints in this router that still use them directly.
from ..services.metadata import DEFAULT_USER_ID, EMPTY_FILE_SHA256


@router.post(
    "/announce",
    status_code=status.HTTP_201_CREATED,
    response_model=schemas.MetadataResponse,
)
def announce_metadata(
    payload: schemas.MetadataAnnounce,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
) -> schemas.MetadataResponse:
    """
    Receive a file-change announcement from a client device.

    Validates the incoming ``MetadataAnnounce`` payload and delegates all
    business logic (deduplication, conflict detection, LWW resolution,
    database writes) to ``services.metadata.process_metadata_sync``.

    The JSON input/output contract is unchanged from previous versions.
    """
    return process_metadata_sync(db=db, payload=payload, user_id=current_user.id)


@router.post("/upload", status_code=status.HTTP_202_ACCEPTED)
def upload_file(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """
    Rohan's network_client.py calls this with:
        files={"file": (remote_path, file_handle)}

    The filename from the multipart header IS the remote_path (the relative
    file path the client wants to store on the server).

    Week 8 Update: Non-blocking.  Writes bytes to MinIO, then enqueues a
    background job to verify the SHA-256 hash.  Returns 202 Accepted
    immediately — the client can poll GET /sync/upload/status/{version_id}
    to check when the version transitions to 'complete'.

    Week 5 preserved: Small files still use this endpoint.
    Week 4 Hardening preserved:
        - Wraps all DB mutations in try/except with rollback.
        - Atomic write semantics provided by MinIO's PUT (S3 PUTs are atomic).
    """
    user_id = current_user.id
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

        # ── Step 3.5: Enforce Storage Quota ──────────────────────────────
        # Lock the user record to prevent race conditions during concurrent uploads
        db.query(models.User).filter(models.User.id == current_user.id).with_for_update().first()
        
        sql = """
            SELECT COALESCE(SUM(v.size_bytes), 0)
            FROM (
                SELECT file_id, MAX(version_num) as max_v
                FROM versions
                GROUP BY file_id
            ) latest
            JOIN versions v ON v.file_id = latest.file_id AND v.version_num = latest.max_v
            JOIN files f ON f.id = v.file_id
            WHERE f.user_id = :user_id AND f.is_deleted = FALSE
        """
        current_usage = db.execute(text(sql), {"user_id": current_user.id}).scalar() or 0
        if current_usage + total_bytes > current_user.storage_quota:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"Storage quota exceeded. Used: {current_usage}, Quota: {current_user.storage_quota}"
            )

        storage_key = version_record.storage_path
        storage.put_object(storage_key, file_bytes)

        # ── Step 4: Update version record & transition to 'processing' ──
        version_record.size_bytes = total_bytes
        version_record.storage_path = storage_key
        version_record.upload_status = UploadStatus.processing

        # ── Step 5: Enqueue background hash verification ─────────────────
        job_id = enqueue_verify(version_record.id, version_record.hash)
        version_record.job_id = job_id
        db.commit()

        _fire_event(user_id, "upload_processing", {"file_path": remote_path, "version_id": version_record.id})

        return JSONResponse(
            status_code=status.HTTP_202_ACCEPTED,
            content={
                "status": "processing",
                "file": remote_path,
                "bytes": total_bytes,
                "version_id": version_record.id,
                "job_id": job_id,
                "message": "Upload received. Background verification in progress.",
            }
        )

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
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
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
    user_id = current_user.id

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

        # Verify version belongs to current_user
        file_record = db.query(models.File).filter(
            models.File.id == version_record.file_id,
            models.File.user_id == current_user.id
        ).first()

        if not file_record:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to upload chunks for this file version."
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

        # ── Step 2.5: Enforce Storage Quota ──────────────────────────────
        # Lock the user record to prevent race conditions
        db.query(models.User).filter(models.User.id == current_user.id).with_for_update().first()
        
        sql = """
            SELECT COALESCE(SUM(v.size_bytes), 0)
            FROM (
                SELECT file_id, MAX(version_num) as max_v
                FROM versions
                GROUP BY file_id
            ) latest
            JOIN versions v ON v.file_id = latest.file_id AND v.version_num = latest.max_v
            JOIN files f ON f.id = v.file_id
            WHERE f.user_id = :user_id AND f.is_deleted = FALSE
        """
        current_usage = db.execute(text(sql), {"user_id": current_user.id}).scalar() or 0
        if current_usage + chunk_size > current_user.storage_quota:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"Storage quota exceeded. Used: {current_usage}, Quota: {current_user.storage_quota}"
            )

        # Hash chunk to make it content-addressable
        chunk_hash = hashlib.sha256(chunk_bytes).hexdigest()
        chunk_key = f"chunks/{chunk_hash}"

        # Put chunk in MinIO (safe overwrite / upload)
        storage.put_object(chunk_key, chunk_bytes)

        # Record chunk in StoredChunk table
        stored_chunk = db.query(models.StoredChunk).filter(models.StoredChunk.chunk_hash == chunk_hash).first()
        if not stored_chunk:
            stored_chunk = models.StoredChunk(
                chunk_hash=chunk_hash,
                user_id=user_id,
                storage_path=chunk_key,
                size_bytes=chunk_size
            )
            db.add(stored_chunk)
            db.flush()

        # Record in VersionChunk table
        version_chunk = db.query(models.VersionChunk).filter(
            models.VersionChunk.version_id == version_id,
            models.VersionChunk.chunk_index == chunk_index
        ).first()
        if not version_chunk:
            version_chunk = models.VersionChunk(
                version_id=version_id,
                chunk_index=chunk_index,
                chunk_hash=chunk_hash
            )
            db.add(version_chunk)

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

        # ── Step 4: Mark version as 'uploading' (Week 8) ─────────────────
        if version_record.upload_status == UploadStatus.pending:
            version_record.upload_status = UploadStatus.uploading

        # ── Step 5: Check if all chunks received ────────────────────────
        received_count = db.query(models.ChunkUpload).filter(
            models.ChunkUpload.version_id == version_id
        ).count()

        assembled = False
        job_id = None

        if received_count >= total_chunks:
            # All chunks received — enqueue background assembly + verify
            # instead of doing it inline (Week 8 async upgrade).
            version_record.upload_status = UploadStatus.processing

            job_id = enqueue_assemble_and_verify(
                version_id, file_hash
            )
            version_record.job_id = job_id
            assembled = True

            logger.info(
                "All %d chunks received for version_id=%d. "
                "Enqueued assembly job=%s.",
                total_chunks, version_id, job_id
            )

        db.commit()

        response_data = {
            "status": "processing" if assembled else "chunk_received",
            "version_id": version_id,
            "chunk_index": chunk_index,
            "chunks_received": min(received_count, total_chunks),
            "total_chunks": total_chunks,
            "assembled": assembled,
        }
        if job_id:
            response_data["job_id"] = job_id

        return schemas.ChunkUploadResponse(**response_data)

    except HTTPException:
        raise
    except Exception:
        db.rollback()
        raise


@router.get("/metadata", response_model=List[schemas.FileVersionOut])
def get_metadata(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """
    Returns the latest version of every non-deleted file for the user.
    Rohan's client will eventually call this to discover what files are on the
    server that it doesn't have locally.
    """
    user_id = current_user.id

    try:
        # Get all active (non-deleted) files for this user
        files = db.query(models.File).filter(
            models.File.user_id == user_id,
            models.File.is_deleted.is_(False)
        ).all()

        result = []
        for f in files:
            latest = db.query(models.Version).filter(
                models.Version.file_id == f.id
            ).order_by(models.Version.version_num.desc()).first()

            if latest:
                result.append(schemas.FileVersionOut(
                    id=f.id,
                    file_path=f.file_path,
                    hash=latest.hash,
                    version_num=latest.version_num,
                    size_bytes=latest.size_bytes,
                    storage_path=latest.storage_path
                ))

        return result

    except Exception:
        db.rollback()
        raise


# ─── Week 8: File Delete Endpoint ──────────────────────────────────────────

@router.delete("/file/{file_id}", status_code=status.HTTP_200_OK)
def delete_file(
    file_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Soft delete a file."""
    user_id = current_user.id
    file_record = db.query(models.File).filter(
        models.File.id == file_id,
        models.File.user_id == user_id
    ).first()
    
    if not file_record:
        raise HTTPException(status_code=404, detail="File not found")
        
    file_record.is_deleted = True
    db.commit()

    _fire_event(user_id, "file_deleted", {"file_id": file_id, "file_path": file_record.file_path})

    return {"status": "deleted"}

from typing import Optional

@router.get("/versions/recent")
def get_recent_versions(
    file_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """
    Returns the version history for a specific file or globally.
    """
    query = db.query(models.Version).join(models.File).filter(
        models.File.user_id == current_user.id
    )
    
    if file_id:
        query = query.filter(models.File.id == file_id)
        
    versions = query.order_by(models.Version.created_at.desc()).limit(50).all()
    
    return [
        {
            "id": str(v.id),
            "version_number": v.version_num,
            "hash": v.hash,
            "created_at": str(v.created_at),
            "device_id": "Unknown",
            "size_bytes": v.size_bytes,
            "storage_path": v.storage_path,
            "file_name": v.file.file_path
        } for v in versions
    ]

# ─── Week 6: Metadata Diff Endpoint ─────────────────────────────────────────

@router.get(
    "/metadata/diff",
    status_code=status.HTTP_200_OK,
    response_model=schemas.DiffResponse
)
def get_metadata_diff(
    device_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """
    GET /sync/metadata/diff?device_id=<id>

    The two-way sync bridge.  Compares what a specific device has synced
    (tracked in file_device_map) against the server's canonical file list
    to return exactly which files the device is missing or needs updating.

    Algorithm:
        1. Validate the device exists.
        2. Get all non-deleted files + their latest completed version
           (size_bytes > 0 to exclude pending uploads).
        3. Get all file_device_map entries for this device.
        4. For each server file:
           a. If the device has NO map entry → missing_files.
           b. If the device's version_id < server's latest version_id
              → outdated_files.
           c. Otherwise the device is up-to-date → skip.
        5. Return the diff payload.
    """
    user_id = current_user.id

    try:
        # ── Step 1: Validate device ──────────────────────────────────────
        device = db.query(models.Device).filter(
            models.Device.id == device_id,
            models.Device.user_id == user_id
        ).first()

        if not device:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to access sync diffs for this device."
            )

        # ── Step 2: Build canonical server state ─────────────────────────
        # All non-deleted files for this user with a completed version
        server_files = db.query(models.File).filter(
            models.File.user_id == user_id,
            models.File.is_deleted.is_(False)
        ).all()

        # Map file_id → (File, latest completed Version)
        server_state = {}
        for f in server_files:
            latest = db.query(models.Version).filter(
                models.Version.file_id == f.id,
                models.Version.size_bytes > 0   # only fully-uploaded versions
            ).order_by(models.Version.version_num.desc()).first()

            if latest:
                server_state[f.id] = (f, latest)

        # ── Step 3: Get device's sync map ────────────────────────────────
        device_map_rows = db.query(models.FileDeviceMap).filter(
            models.FileDeviceMap.device_id == device_id
        ).all()

        # file_id → version_id that device last synced
        device_synced = {
            row.file_id: row.version_id
            for row in device_map_rows
        }

        # ── Step 4: Compute diff ─────────────────────────────────────────
        missing_files = []
        outdated_files = []
        deleted_files = []
        
        for file_id in device_synced.keys():
            if file_id not in server_state:
                file_rec = db.query(models.File).filter(models.File.id == file_id).first()
                if file_rec and file_rec.is_deleted:
                    deleted_files.append(file_rec.file_path)

        for file_id, (file_record, latest_version) in server_state.items():
            version_chunks = db.query(models.VersionChunk).filter(
                models.VersionChunk.version_id == latest_version.id
            ).order_by(models.VersionChunk.chunk_index.asc()).all()
            chunk_hashes = [vc.chunk_hash for vc in version_chunks]

            diff_item = schemas.DiffItem(
                file_path=file_record.file_path,
                file_id=file_record.id,
                hash=latest_version.hash,
                version_num=latest_version.version_num,
                version_id=latest_version.id,
                size_bytes=latest_version.size_bytes,
                storage_path=latest_version.storage_path,
                chunk_hashes=chunk_hashes
            )

            if file_id not in device_synced:
                # Device has never synced this file
                missing_files.append(diff_item)
            elif device_synced[file_id] < latest_version.id:
                # Device has an older version
                outdated_files.append(diff_item)
            # else: device is up-to-date, skip

        return schemas.DiffResponse(
            device_id=device_id,
            missing_files=missing_files,
            outdated_files=outdated_files,
            deleted_files=deleted_files
        )

    except HTTPException:
        raise
    except Exception:
        db.rollback()
        raise


# ─── Week 6: File Download Endpoint ─────────────────────────────────────────

@router.get("/download")
def download_file(
    storage_path: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """
    GET /sync/download?storage_path=<minio_key>

    Streams a file's bytes from MinIO back to the client.  The client
    receives the raw bytes and writes them to its watch_folder.

    The storage_path comes from the DiffItem returned by /metadata/diff.
    We validate that the storage_path corresponds to a real version record
    to prevent arbitrary MinIO key access.
    """
    try:
        # ── Validate the storage_path belongs to a real version ──────────
        version = db.query(models.Version).join(models.File).filter(
            models.Version.storage_path == storage_path,
            models.File.user_id == current_user.id
        ).first()

        if not version:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No version found for storage_path '{storage_path}'."
            )

        # ── Fetch from MinIO ─────────────────────────────────────────────
        file_bytes = storage.get_object(storage_path)

        return Response(
            content=file_bytes,
            media_type="application/octet-stream",
            headers={
                "Content-Disposition": f'attachment; filename="{version.storage_path}"',
                "X-Shadow-Hash": version.hash,
                "X-Shadow-Size": str(version.size_bytes),
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("download_file failed for '%s': %s", storage_path, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to download file: {e}"
        )


@router.get("/download_chunk")
def download_chunk(
    file_hash: str,
    chunk_index: int,
    version_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """
    GET /sync/download_chunk?file_hash=<file_hash>&chunk_index=<index>&version_id=<version_id>

    Streams a single chunk segment from MinIO back to the client.
    """
    try:
        # Verify that the version belongs to current_user
        vc = db.query(models.VersionChunk).join(models.Version).join(models.File).filter(
            models.VersionChunk.version_id == version_id,
            models.VersionChunk.chunk_index == chunk_index,
            models.File.user_id == current_user.id
        ).first()

        if not vc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Chunk index {chunk_index} not found for version {version_id} or not owned by you."
            )

        stored = db.query(models.StoredChunk).filter(
            models.StoredChunk.chunk_hash == vc.chunk_hash
        ).first()

        if not stored:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Stored chunk for hash {vc.chunk_hash} not found."
            )

        file_bytes = storage.get_object(stored.storage_path)

        return Response(
            content=file_bytes,
            media_type="application/octet-stream",
            headers={
                "X-Chunk-Hash": vc.chunk_hash,
                "X-Chunk-Index": str(chunk_index),
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("download_chunk failed for hash=%s index=%d version_id=%d: %s", file_hash, chunk_index, version_id, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to download chunk: {e}"
        )


# ─── Week 6: Sync Acknowledgment Endpoint ───────────────────────────────────

@router.post("/ack_sync", status_code=status.HTTP_200_OK)
def ack_sync(
    device_id: int = Form(...),
    file_id: int = Form(...),
    version_id: int = Form(...),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """
    POST /sync/ack_sync

    After a client downloads a file successfully, it calls this endpoint
    to update the file_device_map.  This records that device_id now has
    version_id of file_id, so subsequent /metadata/diff calls won't
    return this file as missing.

    Upsert semantics: if a row for (device_id, file_id) already exists,
    update its version_id and synced_at.  Otherwise insert a new row.
    """
    try:
        # Verify ownership of device and file
        device = db.query(models.Device).filter(
            models.Device.id == device_id,
            models.Device.user_id == current_user.id
        ).first()
        if not device:
            raise HTTPException(status_code=403, detail="Device not found or not owned by you.")

        file_record = db.query(models.File).filter(
            models.File.id == file_id,
            models.File.user_id == current_user.id
        ).first()
        if not file_record:
            raise HTTPException(status_code=403, detail="File not found or not owned by you.")

        existing = db.query(models.FileDeviceMap).filter(
            models.FileDeviceMap.device_id == device_id,
            models.FileDeviceMap.file_id == file_id
        ).first()

        if existing:
            existing.version_id = version_id
            existing.synced_at = func.now()
        else:
            new_map = models.FileDeviceMap(
                device_id=device_id,
                file_id=file_id,
                version_id=version_id
            )
            db.add(new_map)

        db.commit()

        return {
            "status": "ack_recorded",
            "device_id": device_id,
            "file_id": file_id,
            "version_id": version_id
        }

    except Exception:
        db.rollback()
        raise


# ─── Week 8: Upload Status Polling Endpoint ─────────────────────────────────

@router.get("/upload/status/{version_id}", status_code=status.HTTP_200_OK)
def get_upload_status(
    version_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """
    GET /sync/upload/status/{version_id}

    Allows clients to poll the processing state of an upload.  After
    POST /sync/upload returns 202 Accepted, the client can call this
    endpoint to check whether the background worker has finished
    verifying the file hash.

    Returns:
        upload_status: pending | uploading | processing | complete | failed
        version_id:    The version being tracked.
        job_id:        The RQ job ID (if a job was enqueued).
        size_bytes:    Final file size (populated once assembly/upload finishes).
    """
    version = db.query(models.Version).join(models.File).filter(
        models.Version.id == version_id,
        models.File.user_id == current_user.id
    ).first()

    if not version:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Version {version_id} not found."
        )

    return {
        "version_id": version.id,
        "upload_status": version.upload_status.value if version.upload_status else "unknown",
        "job_id": version.job_id,
        "size_bytes": version.size_bytes,
        "hash": version.hash,
        "storage_path": version.storage_path,
    }


# ─── Week 8: Conflict Resolution API ────────────────────────────────────────

from pydantic import BaseModel
import os
import re

class ResolveConflictRequest(BaseModel):
    original_file_id: int
    conflict_file_id: int
    resolution_choice: str

@router.get("/conflicts", status_code=status.HTTP_200_OK)
def get_conflicts(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Returns a list of all unresolved file conflicts."""
    conflict_files = db.query(models.File).filter(
        models.File.user_id == current_user.id,
        models.File.is_deleted.is_(False),
        models.File.file_path.like("%(Conflicted copy)%")
    ).all()
    
    result = []
    for c_file in conflict_files:
        original_path = re.sub(r' \(Conflicted copy\)', '', c_file.file_path)
        o_file = db.query(models.File).filter(
            models.File.user_id == current_user.id,
            models.File.is_deleted.is_(False),
            models.File.file_path == original_path
        ).first()
        
        if o_file:
            c_latest = db.query(models.Version).filter(models.Version.file_id == c_file.id).order_by(models.Version.created_at.desc()).first()
            o_latest = db.query(models.Version).filter(models.Version.file_id == o_file.id).order_by(models.Version.created_at.desc()).first()
            
            result.append({
                "id": str(c_file.id),
                "filename": os.path.basename(original_path),
                "path": original_path,
                "timeDetected": c_latest.created_at.isoformat() if c_latest else "",
                "status": "Needs Resolution",
                "original_file_id": o_file.id,
                "conflict_file_id": c_file.id,
                "optionA": {
                    "device": "Original",
                    "timestamp": o_latest.client_modified_at.isoformat() if o_latest and o_latest.client_modified_at else "",
                    "size": f"{o_latest.size_bytes} B" if o_latest else "0 B",
                    "hash": o_latest.hash if o_latest else ""
                },
                "optionB": {
                    "device": "Conflicted",
                    "timestamp": c_latest.client_modified_at.isoformat() if c_latest and c_latest.client_modified_at else "",
                    "size": f"{c_latest.size_bytes} B" if c_latest else "0 B",
                    "hash": c_latest.hash if c_latest else ""
                }
            })
            
    return result

@router.post("/resolve_conflict", status_code=status.HTTP_200_OK)
def resolve_conflict(
    req: ResolveConflictRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    from app.services.metadata import _fire_event
    
    o_file = db.query(models.File).filter(models.File.id == req.original_file_id, models.File.user_id == current_user.id).first()
    c_file = db.query(models.File).filter(models.File.id == req.conflict_file_id, models.File.user_id == current_user.id).first()
    
    if not o_file or not c_file:
        raise HTTPException(status_code=404, detail="File not found")
        
    if req.resolution_choice == 'keep_original':
        c_file.is_deleted = True
        _fire_event(current_user.id, "file_deleted", {"file_id": c_file.id, "file_path": c_file.file_path})
    elif req.resolution_choice == 'keep_conflict':
        o_file.is_deleted = True
        c_file.file_path = o_file.file_path
        _fire_event(current_user.id, "file_deleted", {"file_id": o_file.id, "file_path": o_file.file_path})
        _fire_event(current_user.id, "file_created", {"file_id": c_file.id, "file_path": c_file.file_path})
    elif req.resolution_choice == 'keep_both':
        c_file.file_path = c_file.file_path.replace("(Conflicted copy)", "(Resolved copy)")
        _fire_event(current_user.id, "file_created", {"file_id": c_file.id, "file_path": c_file.file_path})
    else:
        raise HTTPException(status_code=400, detail="Invalid resolution choice")
        
    db.commit()
    return {"status": "resolved"}
