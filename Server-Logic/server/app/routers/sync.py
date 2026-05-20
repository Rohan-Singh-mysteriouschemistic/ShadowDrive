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
        {"path": "filename.txt", "hash": "abc...", "event": "new|modified|deleted",
         "base_version_id": 42, "client_modified_at": "2026-05-20T10:00:00Z"}

    Week 7 Conflict Resolution Logic:
        When a client announces a "modified" or "new" event with a
        base_version_id, the server checks if that base matches the
        current latest completed version for the file.

        - MATCH (or first version): No conflict → normal accept flow.
        - MISMATCH: Split-brain detected.  Two devices edited the same
          file from different bases.  Resolution:
            1. Compare timestamps (LWW): client_modified_at vs the
               server's latest version's created_at.
            2. The WINNER keeps the original file_path and becomes
               the new canonical version.
            3. The LOSER's version is saved under a conflict-copy path:
               "report (Conflicted copy).pdf"
            4. Both versions require upload.  The response tells the
               client which version is the winner and provides the
               conflict copy's metadata.

    Preserved from Weeks 3-5:
        - Hash deduplication
        - 0-byte file handling
        - Interrupted upload recovery
        - try/except with db.rollback()
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
            # ── Interrupted Upload Recovery (Week 4, Scenario B) ─────────
            is_empty_file = (incoming_hash == EMPTY_FILE_SHA256)

            if existing_version.size_bytes == 0 and not is_empty_file:
                # Stale pending version from an interrupted sync cycle.
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
                storage_path=storage_key,
                parent_version_id=payload.base_version_id,
                announced_at=payload.client_modified_at
            )
            db.add(new_version)
            file_record.updated_at = func.now()
            db.commit()
            db.refresh(new_version)

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

        # ── Step 6: CONFLICT DETECTION (Week 7) ─────────────────────────
        # Get the server's latest COMPLETED version for this file
        server_latest = db.query(models.Version).filter(
            models.Version.file_id == file_record.id,
            models.Version.size_bytes > 0
        ).order_by(models.Version.version_num.desc()).first()

        # Determine next version number (from ANY version, including pending)
        any_latest = db.query(models.Version).filter(
            models.Version.file_id == file_record.id
        ).order_by(models.Version.version_num.desc()).first()
        next_version_num = (any_latest.version_num + 1) if any_latest else 1

        # ── Check for split-brain ────────────────────────────────────────
        # A conflict exists when ALL of these are true:
        #   1. The file already has a completed version on the server.
        #   2. The client provided a base_version_id.
        #   3. The client's base does NOT match the server's latest.
        # This means two devices forked from different points.

        is_conflict = (
            server_latest is not None
            and payload.base_version_id is not None
            and payload.base_version_id != server_latest.id
        )

        if is_conflict:
            # ── LAST-WRITE-WINS (LWW) Resolution ────────────────────────
            # Compare the incoming client timestamp against the server's
            # latest version timestamp.  The later one wins.
            from datetime import datetime, timezone

            client_ts = payload.client_modified_at
            server_ts = server_latest.announced_at or server_latest.created_at

            # Normalize: if client didn't send a timestamp, use "now" (server arrival)
            if client_ts is None:
                client_ts = datetime.now(timezone.utc)
            # Ensure both are offset-aware for comparison
            if client_ts.tzinfo is None:
                client_ts = client_ts.replace(tzinfo=timezone.utc)
            if server_ts.tzinfo is None:
                server_ts = server_ts.replace(tzinfo=timezone.utc)

            client_wins = client_ts >= server_ts

            # ── Build the conflict copy path ─────────────────────────────
            # "report.pdf" → "report (Conflicted copy).pdf"
            conflict_path = _make_conflict_path(payload.path)

            # Ensure a File record exists for the conflict copy
            conflict_file = db.query(models.File).filter(
                models.File.user_id == user_id,
                models.File.file_path == conflict_path
            ).first()
            if not conflict_file:
                conflict_file = models.File(
                    user_id=user_id,
                    file_path=conflict_path,
                    is_deleted=False
                )
                db.add(conflict_file)
                db.flush()

            if client_wins:
                # CLIENT WINS: the incoming version takes the original path.
                # The server's current latest becomes the conflict copy.
                #
                # Create a new version under the CONFLICT file pointing
                # to the server's existing bytes (same storage_path).
                conflict_version = models.Version(
                    file_id=conflict_file.id,
                    version_num=1,
                    hash=server_latest.hash,
                    size_bytes=server_latest.size_bytes,
                    storage_path=server_latest.storage_path,
                    parent_version_id=server_latest.parent_version_id,
                    is_conflict_copy=True,
                    announced_at=server_ts
                )
                db.add(conflict_version)
                db.flush()
                db.refresh(conflict_version)

                # Now create the WINNER version on the original file
                winner_storage_key = f"{user_id}/{payload.path}/v{next_version_num}"
                winner_version = models.Version(
                    file_id=file_record.id,
                    version_num=next_version_num,
                    hash=incoming_hash,
                    size_bytes=0,  # Pending upload
                    storage_path=winner_storage_key,
                    parent_version_id=payload.base_version_id,
                    is_conflict_copy=False,
                    announced_at=client_ts
                )
                db.add(winner_version)
                file_record.updated_at = func.now()
                db.commit()
                db.refresh(winner_version)

                logger.info(
                    "CONFLICT RESOLVED (LWW): client wins for '%s'. "
                    "Server version saved as conflict copy '%s'.",
                    payload.path, conflict_path
                )

                return schemas.MetadataResponse(
                    status="conflict_resolved",
                    file_id=file_record.id,
                    version_id=winner_version.id,
                    upload_required=True,
                    conflict_info=schemas.ConflictInfo(
                        conflict_file_path=conflict_path,
                        conflict_version_id=conflict_version.id,
                        winner_version_id=winner_version.id,
                        resolution="lww"
                    )
                )

            else:
                # SERVER WINS: the server's latest stays as the canonical.
                # The incoming client version becomes the conflict copy.
                conflict_storage_key = f"{user_id}/{conflict_path}/v1"
                conflict_version = models.Version(
                    file_id=conflict_file.id,
                    version_num=1,
                    hash=incoming_hash,
                    size_bytes=0,  # Pending upload
                    storage_path=conflict_storage_key,
                    parent_version_id=payload.base_version_id,
                    is_conflict_copy=True,
                    announced_at=client_ts
                )
                db.add(conflict_version)
                file_record.updated_at = func.now()
                db.commit()
                db.refresh(conflict_version)

                logger.info(
                    "CONFLICT RESOLVED (LWW): server wins for '%s'. "
                    "Client version saved as conflict copy '%s'.",
                    payload.path, conflict_path
                )

                return schemas.MetadataResponse(
                    status="conflict_resolved",
                    file_id=file_record.id,
                    version_id=conflict_version.id,
                    upload_required=True,
                    conflict_info=schemas.ConflictInfo(
                        conflict_file_path=conflict_path,
                        conflict_version_id=conflict_version.id,
                        winner_version_id=server_latest.id,
                        resolution="lww"
                    )
                )

        # ── Step 7: No conflict — normal accept ─────────────────────────
        storage_key = f"{user_id}/{payload.path}/v{next_version_num}"

        new_version = models.Version(
            file_id=file_record.id,
            version_num=next_version_num,
            hash=incoming_hash,
            size_bytes=0,  # Will be updated when the actual file is uploaded
            storage_path=storage_key,
            parent_version_id=payload.base_version_id,
            announced_at=payload.client_modified_at
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
        # ── Clean rollback on any error ──────────────────────────────────
        db.rollback()
        raise


def _make_conflict_path(original_path: str) -> str:
    """Convert 'docs/report.pdf' → 'docs/report (Conflicted copy).pdf'

    If the path has no extension: 'README' → 'README (Conflicted copy)'
    If a conflict copy already exists, subsequent conflicts will overwrite
    it (the old conflict copy is already versioned in MinIO).
    """
    import os
    base, ext = os.path.splitext(original_path)
    return f"{base} (Conflicted copy){ext}"


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


# ─── Week 6: Metadata Diff Endpoint ─────────────────────────────────────────

@router.get(
    "/metadata/diff",
    status_code=status.HTTP_200_OK,
    response_model=schemas.DiffResponse
)
def get_metadata_diff(device_id: int, db: Session = Depends(get_db)):
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
    user_id = DEFAULT_USER_ID

    try:
        # ── Step 1: Validate device ──────────────────────────────────────
        device = db.query(models.Device).filter(
            models.Device.id == device_id
        ).first()

        if not device:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Device {device_id} not found."
            )

        # ── Step 2: Build canonical server state ─────────────────────────
        # All non-deleted files for this user with a completed version
        server_files = db.query(models.File).filter(
            models.File.user_id == user_id,
            models.File.is_deleted == False
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
            diff_item = schemas.DiffItem(
                file_path=file_record.file_path,
                file_id=file_record.id,
                hash=latest_version.hash,
                version_num=latest_version.version_num,
                version_id=latest_version.id,
                size_bytes=latest_version.size_bytes,
                storage_path=latest_version.storage_path
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
def download_file(storage_path: str, db: Session = Depends(get_db)):
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
        version = db.query(models.Version).filter(
            models.Version.storage_path == storage_path
        ).first()

        if not version:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No version found for storage_path '{storage_path}'."
            )

        # ── Fetch from MinIO ─────────────────────────────────────────────
        file_bytes = storage.get_object(storage_path)

        from fastapi.responses import Response
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


# ─── Week 6: Sync Acknowledgment Endpoint ───────────────────────────────────

@router.post("/ack_sync", status_code=status.HTTP_200_OK)
def ack_sync(
    device_id: int = Form(...),
    file_id: int = Form(...),
    version_id: int = Form(...),
    db: Session = Depends(get_db)
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
