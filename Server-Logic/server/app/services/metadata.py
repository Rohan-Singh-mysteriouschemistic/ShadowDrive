"""
services/metadata.py
────────────────────
Domain service for the metadata-announce workflow.

All database transactions, conflict-detection logic, LWW resolution,
and hash-deduplication logic live here.  The router (sync.py) is
responsible only for HTTP transport — it calls `process_metadata_sync`
and returns whatever it gets back.

Extracted from: routers/sync.py::announce_metadata (originally ~330 lines)
"""

import os
import logging
from datetime import datetime, timezone
import asyncio
from typing import Union, Optional

from sqlalchemy.orm import Session
from sqlalchemy.sql import func
from sqlalchemy.exc import IntegrityError

from .. import models, schemas, storage
from ..routers.events import publish_event

logger = logging.getLogger(__name__)

def _fire_event(user_id: int, event_type: str, payload: dict):
    """Synchronous wrapper to publish async SSE events from sync code."""
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(publish_event(user_id, event_type, payload))
    except RuntimeError:
        pass

# ── Module-level constants (shared with the router via import) ────────────────

#: Hardcoded user until auth is implemented.
DEFAULT_USER_ID = 1

#: SHA-256 of an empty byte string — used to handle 0-byte files cleanly.
EMPTY_FILE_SHA256 = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"


# ── Public API ────────────────────────────────────────────────────────────────

def process_metadata_sync(
    db: Session,
    payload: schemas.MetadataAnnounce,
    user_id: int = DEFAULT_USER_ID,
) -> schemas.MetadataResponse:
    """Core announce-metadata business logic.

    Called by the router after HTTP validation.  Handles, in order:

    1. Dev-mode user auto-creation.
    2. File record upsert (find-or-create).
    3. Deletion events.
    4. Un-deletion when a previously deleted path reappears.
    5. Hash deduplication (already_synced / interrupted-upload recovery).
    6. 0-byte file fast-path.
    7. Conflict detection (split-brain) + Last-Write-Wins resolution.
    8. Normal accept — new version row created, upload required.

    Args:
        db:      SQLAlchemy session (managed by the caller/FastAPI DI).
        payload: The validated ``MetadataAnnounce`` payload from the client.

    Returns:
        A ``MetadataResponse`` schema instance describing what the client
        should do next (upload, skip, conflict details, etc.).

    Raises:
        Exception: Any unhandled DB or storage error is re-raised after a
                   rollback so that FastAPI's default 500 handler kicks in.
    """
    # SQLite sends 0 for "no base"; PostgreSQL expects NULL.
    if payload.base_version_id == 0:
        payload.base_version_id = None

    try:
        _ensure_user(db, user_id)

        file_record = _get_or_create_file(db, user_id, payload.path)

        # ── Step 2: Deletion events ───────────────────────────────────────────
        if payload.event == "deleted":
            return _handle_deletion(db, file_record)

        # ── Step 3: Un-delete if path reappears ──────────────────────────────
        if file_record.is_deleted:
            file_record.is_deleted = False

        # ── Step 4: Hash deduplication ───────────────────────────────────────
        incoming_hash = payload.hash or EMPTY_FILE_SHA256
        dedup_result = _check_hash_dedup(db, file_record, incoming_hash)
        if dedup_result is not None:
            return dedup_result

        # ── Step 5: 0-byte file fast-path ────────────────────────────────────
        if incoming_hash == EMPTY_FILE_SHA256:
            return _handle_empty_file(db, user_id, file_record, payload)

        # ── Step 6: Conflict detection + LWW resolution ───────────────────────
        conflict_result = _handle_conflict_if_any(
            db, user_id, file_record, payload, incoming_hash
        )
        if conflict_result is not None:
            return conflict_result

        # ── Step 7: Normal accept ─────────────────────────────────────────────
        return _accept_new_version(db, user_id, file_record, payload, incoming_hash)

    except Exception:
        db.rollback()
        raise


# ── Private helpers ───────────────────────────────────────────────────────────

def _ensure_user(db: Session, user_id: int) -> None:
    """Auto-create a stub user for development if it doesn't exist yet."""
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        user = models.User(id=user_id, username="test_user", email="test@example.com", password_hash="pwd")
        db.add(user)
        db.commit()


def _get_or_create_file(
    db: Session, user_id: int, file_path: str
) -> models.File:
    """Return the File record for (user_id, file_path), creating it if absent."""
    file_record = db.query(models.File).filter(
        models.File.user_id == user_id,
        models.File.file_path == file_path,
    ).first()

    if not file_record:
        try:
            with db.begin_nested():
                file_record = models.File(
                    user_id=user_id,
                    file_path=file_path,
                    is_deleted=False,
                )
                db.add(file_record)
                db.flush()  # Populate file_record.id without committing the transaction.
        except IntegrityError:
            # Another transaction inserted the record concurrently.
            file_record = db.query(models.File).filter(
                models.File.user_id == user_id,
                models.File.file_path == file_path,
            ).first()

    return file_record


def _handle_deletion(db: Session, file_record: models.File) -> schemas.MetadataResponse:
    """Mark the file as deleted and return an acknowledgement response."""
    file_record.is_deleted = True
    file_record.updated_at = func.now()
    db.commit()

    _fire_event(file_record.user_id, "file_deleted", {"file_id": file_record.id, "file_path": file_record.file_path})

    return schemas.MetadataResponse(
        status="deleted_acknowledged",
        file_id=file_record.id,
        version_id=None,
        upload_required=False,
    )


def _check_hash_dedup(
    db: Session,
    file_record: models.File,
    incoming_hash: str,
) -> Optional[schemas.MetadataResponse]:
    """Return a response if the server already knows this hash, else None.

    Handles two sub-cases:
    - Interrupted upload recovery: version exists but size_bytes == 0 (still
      uploading).  Tell the client to re-upload using the same version_id.
    - Already synced: server has a complete version with this hash.  Client
      can skip the upload entirely.
    """
    existing_version = db.query(models.Version).filter(
        models.Version.file_id == file_record.id,
        models.Version.hash == incoming_hash,
        models.Version.upload_status != models.UploadStatus.failed,
    ).first()

    if not existing_version:
        return None

    is_empty_file = incoming_hash == EMPTY_FILE_SHA256

    if existing_version.size_bytes == 0 and not is_empty_file:
        # Interrupted upload — return same version_id so client can resume.
        file_record.updated_at = func.now()
        db.commit()
        return schemas.MetadataResponse(
            status="accepted",
            file_id=file_record.id,
            version_id=existing_version.id,
            upload_required=True,
        )

    # Server has a fully uploaded version with this hash.
    file_record.updated_at = func.now()
    db.commit()
    return schemas.MetadataResponse(
        status="already_synced",
        file_id=file_record.id,
        version_id=existing_version.id,
        upload_required=False,
    )


def _handle_empty_file(
    db: Session,
    user_id: int,
    file_record: models.File,
    payload: schemas.MetadataAnnounce,
) -> schemas.MetadataResponse:
    """Create a version record for a 0-byte file and push an empty object to storage."""
    latest_version = db.query(models.Version).filter(
        models.Version.file_id == file_record.id,
    ).order_by(models.Version.version_num.desc()).first()

    next_version_num = (latest_version.version_num + 1) if latest_version else 1
    storage_key = f"{user_id}/{payload.path}/v{next_version_num}"

    new_version = models.Version(
        file_id=file_record.id,
        version_num=next_version_num,
        hash=EMPTY_FILE_SHA256,
        size_bytes=0,
        storage_path=storage_key,
        parent_version_id=payload.base_version_id,
        announced_at=payload.client_modified_at,
    )
    db.add(new_version)
    file_record.updated_at = func.now()
    db.commit()
    db.refresh(new_version)

    _fire_event(user_id, "file_updated", {"file_id": file_record.id, "file_path": payload.path, "version_id": new_version.id})

    try:
        storage.put_object(storage_key, b"")
    except Exception as e:
        logger.warning("Failed to write empty object to MinIO: %s", e)

    return schemas.MetadataResponse(
        status="accepted_empty",
        file_id=file_record.id,
        version_id=new_version.id,
        upload_required=False,
    )


def _handle_conflict_if_any(
    db: Session,
    user_id: int,
    file_record: models.File,
    payload: schemas.MetadataAnnounce,
    incoming_hash: str,
) -> Optional[schemas.MetadataResponse]:
    """Detect split-brain conflicts and resolve via Last-Write-Wins.

    Returns a ``MetadataResponse`` when a conflict is found and resolved,
    or ``None`` when no conflict exists (caller continues to normal accept).

    A conflict is declared when ALL three conditions hold:
      1. The file already has a completed version on the server.
      2. The client supplied a ``base_version_id``.
      3. The client's base does NOT equal the server's current latest version.

    Resolution (LWW):
      - Compare ``client_modified_at`` vs the server version's ``announced_at``
        (falling back to ``created_at``).
      - The later timestamp wins and keeps the canonical file path.
      - The earlier timestamp is saved under a ``(Conflicted copy)`` path.
    """
    # The server's latest *completed* version (size_bytes > 0).
    server_latest = db.query(models.Version).filter(
        models.Version.file_id == file_record.id,
        models.Version.size_bytes > 0,
    ).order_by(models.Version.version_num.desc()).first()

    # Next version number across ALL versions (including pending).
    any_latest = db.query(models.Version).filter(
        models.Version.file_id == file_record.id,
    ).order_by(models.Version.version_num.desc()).first()
    next_version_num = (any_latest.version_num + 1) if any_latest else 1

    is_conflict = (
        server_latest is not None
        and payload.base_version_id is not None
        and payload.base_version_id != server_latest.id
    )

    if not is_conflict:
        # Stash next_version_num so the caller can reuse it without re-querying.
        # We do this via a lightweight attribute injection — avoids a second query.
        file_record._next_version_num = next_version_num  # type: ignore[attr-defined]
        return None

    # ── LWW timestamp normalisation ───────────────────────────────────────────
    client_ts = payload.client_modified_at or datetime.now(timezone.utc)
    server_ts = server_latest.announced_at or server_latest.created_at

    if client_ts.tzinfo is None:
        client_ts = client_ts.replace(tzinfo=timezone.utc)
    if server_ts.tzinfo is None:
        server_ts = server_ts.replace(tzinfo=timezone.utc)
        
    client_ts = min(client_ts, datetime.now(timezone.utc))

    client_wins = client_ts >= server_ts

    conflict_path = _make_conflict_path(payload.path)
    conflict_file = _get_or_create_file(db, user_id, conflict_path)

    if client_wins:
        return _resolve_client_wins(
            db=db,
            user_id=user_id,
            file_record=file_record,
            conflict_file=conflict_file,
            conflict_path=conflict_path,
            server_latest=server_latest,
            payload=payload,
            incoming_hash=incoming_hash,
            next_version_num=next_version_num,
            client_ts=client_ts,
            server_ts=server_ts,
        )
    else:
        return _resolve_server_wins(
            db=db,
            user_id=user_id,
            file_record=file_record,
            conflict_file=conflict_file,
            conflict_path=conflict_path,
            server_latest=server_latest,
            payload=payload,
            incoming_hash=incoming_hash,
            client_ts=client_ts,
        )


def _resolve_client_wins(
    db: Session,
    user_id: int,
    file_record: models.File,
    conflict_file: models.File,
    conflict_path: str,
    server_latest: models.Version,
    payload: schemas.MetadataAnnounce,
    incoming_hash: str,
    next_version_num: int,
    client_ts: datetime,
    server_ts: datetime,
) -> schemas.MetadataResponse:
    """Client timestamp wins: incoming version becomes canonical.

    The server's current latest is demoted to a conflict copy, pointing at
    its existing MinIO object (no re-upload needed — same bytes).
    """
    # Demote server's latest to the conflict file.
    conflict_version = models.Version(
        file_id=conflict_file.id,
        version_num=1,
        hash=server_latest.hash,
        size_bytes=server_latest.size_bytes,
        storage_path=server_latest.storage_path,
        parent_version_id=server_latest.parent_version_id,
        is_conflict_copy=True,
        announced_at=server_ts,
    )
    db.add(conflict_version)
    db.flush()
    db.refresh(conflict_version)

    # Create the winner version on the original file path.
    winner_storage_key = f"{user_id}/{payload.path}/v{next_version_num}"
    winner_version = models.Version(
        file_id=file_record.id,
        version_num=next_version_num,
        hash=incoming_hash,
        size_bytes=0,          # Pending upload
        storage_path=winner_storage_key,
        parent_version_id=payload.base_version_id,
        is_conflict_copy=False,
        announced_at=client_ts,
    )
    db.add(winner_version)
    db.flush()

    missing_chunks = reconcile_version_chunks(db, winner_version, payload.chunk_hashes, user_id)

    file_record.updated_at = func.now()
    db.commit()
    db.refresh(winner_version)

    _fire_event(user_id, "conflict_detected", {"file_id": file_record.id, "file_path": payload.path, "conflict_path": conflict_path, "winner_version_id": winner_version.id})

    logger.info(
        "CONFLICT RESOLVED (LWW): client wins for '%s'. "
        "Server version saved as conflict copy '%s'.",
        payload.path, conflict_path,
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
            resolution="lww",
        ),
        missing_chunks=missing_chunks,
    )


def _resolve_server_wins(
    db: Session,
    user_id: int,
    file_record: models.File,
    conflict_file: models.File,
    conflict_path: str,
    server_latest: models.Version,
    payload: schemas.MetadataAnnounce,
    incoming_hash: str,
    client_ts: datetime,
) -> schemas.MetadataResponse:
    """Server timestamp wins: server version stays canonical.

    The incoming client version is saved as a conflict copy under a renamed
    path.  The client must upload its bytes to the conflict copy's storage key.
    """
    conflict_storage_key = f"{user_id}/{conflict_path}/v1"
    conflict_version = models.Version(
        file_id=conflict_file.id,
        version_num=1,
        hash=incoming_hash,
        size_bytes=0,          # Pending upload from the client
        storage_path=conflict_storage_key,
        parent_version_id=payload.base_version_id,
        is_conflict_copy=True,
        announced_at=client_ts,
    )
    db.add(conflict_version)
    db.flush()

    missing_chunks = reconcile_version_chunks(db, conflict_version, payload.chunk_hashes, user_id)

    file_record.updated_at = func.now()
    db.commit()
    db.refresh(conflict_version)

    _fire_event(user_id, "conflict_detected", {"file_id": file_record.id, "file_path": payload.path, "conflict_path": conflict_path, "winner_version_id": server_latest.id})

    logger.info(
        "CONFLICT RESOLVED (LWW): server wins for '%s'. "
        "Client version saved as conflict copy '%s'.",
        payload.path, conflict_path,
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
            resolution="lww",
        ),
        missing_chunks=missing_chunks,
    )


def _accept_new_version(
    db: Session,
    user_id: int,
    file_record: models.File,
    payload: schemas.MetadataAnnounce,
    incoming_hash: str,
) -> schemas.MetadataResponse:
    """No conflict: create a new pending version and tell the client to upload."""
    # Reuse the version number computed by _handle_conflict_if_any if available.
    next_version_num: int = getattr(file_record, "_next_version_num", None)  # type: ignore[assignment]

    if next_version_num is None:
        any_latest = db.query(models.Version).filter(
            models.Version.file_id == file_record.id,
        ).order_by(models.Version.version_num.desc()).first()
        next_version_num = (any_latest.version_num + 1) if any_latest else 1

    storage_key = f"{user_id}/{payload.path}/v{next_version_num}"

    new_version = models.Version(
        file_id=file_record.id,
        version_num=next_version_num,
        hash=incoming_hash,
        size_bytes=0,          # Will be set when the actual file bytes arrive.
        storage_path=storage_key,
        parent_version_id=payload.base_version_id,
        announced_at=payload.client_modified_at,
        is_conflict_copy="(Conflicted copy)" in payload.path,
    )
    db.add(new_version)
    db.flush()

    missing_chunks = reconcile_version_chunks(db, new_version, payload.chunk_hashes, user_id)

    file_record.updated_at = func.now()
    db.commit()
    db.refresh(new_version)

    _fire_event(user_id, "file_created", {"file_id": file_record.id, "file_path": payload.path, "version_id": new_version.id})

    return schemas.MetadataResponse(
        status="accepted",
        file_id=file_record.id,
        version_id=new_version.id,
        upload_required=True,
        missing_chunks=missing_chunks,
    )


def reconcile_version_chunks(db: Session, version_record: models.Version, chunk_hashes: Optional[list[str]], user_id: int) -> list[int]:
    """
    Reconcile the announced chunk hashes for a new version.
    1. Check which chunk hashes exist in `stored_chunks`.
    2. For those that exist:
       - Reuse them: insert into `version_chunks`
       - Insert into `chunk_uploads` so the assembly queue knows they are already there!
    3. For those that do NOT exist:
       - Add their index to `missing_chunks`.
    4. Return the list of missing chunk indices.
    """
    if not chunk_hashes:
        return []

    missing_chunks = []
    for idx, ch in enumerate(chunk_hashes):
        # Query if this chunk is already stored
        stored = db.query(models.StoredChunk).filter(models.StoredChunk.chunk_hash == ch).first()
        if stored:
            # Insert into version_chunks
            vc = models.VersionChunk(
                version_id=version_record.id,
                chunk_index=idx,
                chunk_hash=ch
            )
            db.add(vc)

            # Also insert into chunk_uploads (as a completed chunk)
            # So that the existing assembly logic is fully satisfied!
            cu = models.ChunkUpload(
                version_id=version_record.id,
                chunk_index=idx,
                total_chunks=len(chunk_hashes),
                chunk_storage_key=stored.storage_path,
                size_bytes=stored.size_bytes
            )
            db.add(cu)
        else:
            missing_chunks.append(idx)

    db.flush()

    # If all chunks are reused (none missing), trigger background assembly immediately!
    if len(missing_chunks) == 0 and len(chunk_hashes) > 0:
        from ..worker import enqueue_assemble_and_verify
        version_record.upload_status = models.UploadStatus.processing
        job_id = enqueue_assemble_and_verify(version_record.id, version_record.hash)
        version_record.job_id = job_id
        db.flush()

    return missing_chunks


# ── Utility ───────────────────────────────────────────────────────────────────

def make_conflict_path(original_path: str) -> str:
    """Convert ``'docs/report.pdf'`` → ``'docs/report (Conflicted copy).pdf'``.

    If the path has no extension: ``'README'`` → ``'README (Conflicted copy)'``.
    Subsequent conflicts overwrite the previous conflict copy (the old bytes
    are already versioned in MinIO so no data is lost).
    """
    base, ext = os.path.splitext(original_path)
    return f"{base} (Conflicted copy){ext}"


# Private alias used internally — keeps the call-sites inside this module tidy.
_make_conflict_path = make_conflict_path

