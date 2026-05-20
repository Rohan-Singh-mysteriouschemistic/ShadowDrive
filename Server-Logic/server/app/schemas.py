from pydantic import BaseModel, EmailStr
from datetime import datetime
from typing import Optional

class UserOut(BaseModel):
    id: int
    username: str
    email: EmailStr
    created_at: datetime
    
    class Config:
        from_attributes = True


class UserCreate(BaseModel):
    username: str
    email: EmailStr
    password: str


class UserLogin(BaseModel):
    email: EmailStr
    password: str

class DeviceCreate(BaseModel):
    user_id: int
    device_name: str

class DeviceOut(BaseModel):
    id: int
    device_name: str
    is_online: bool
    last_seen_at: datetime | None = None
    
    class Config:
        from_attributes = True


# ─── Sync Schemas (matching Rohan's client payloads) ─────────────────────────

class MetadataAnnounce(BaseModel):
    """Matches the JSON payload Rohan sends from sync_engine.py:
       {"path": "filename.txt", "hash": "abc123...", "event": "new|modified|deleted"}

    Week 7 additions:
       base_version_id:   The version_id the client was editing FROM.
                          NULL for brand-new files.
       client_modified_at: Client-side timestamp of the edit.  Used for
                          Last-Write-Wins tiebreaking.
    """
    path: str
    hash: str | None = None
    event: str
    base_version_id: int | None = None
    client_modified_at: datetime | None = None


class ConflictInfo(BaseModel):
    """Returned inside MetadataResponse when a split-brain conflict was detected."""
    conflict_file_path: str      # The renamed path for the conflict copy
    conflict_version_id: int     # version_id of the conflict copy
    winner_version_id: int       # version_id of the LWW winner
    resolution: str              # "lww" (Last-Write-Wins)


class MetadataResponse(BaseModel):
    """Response telling the client what happened.

    Week 7: Added conflict_info (present only when a split-brain conflict
    was detected and resolved).  The client should download the conflict
    copy file and present it to the user.
    """
    status: str          # "accepted" | "already_synced" | "deleted_acknowledged" | "conflict_resolved"
    file_id: int
    version_id: int | None = None
    upload_required: bool
    conflict_info: Optional[ConflictInfo] = None


class FileVersionOut(BaseModel):
    """Used by GET /sync/metadata to tell a client what files exist on the server."""
    file_path: str
    hash: str
    version_num: int
    size_bytes: int

    class Config:
        from_attributes = True


# ─── Chunk Upload Schemas (Week 5) ───────────────────────────────────────────

class ChunkUploadResponse(BaseModel):
    """Response from /sync/upload_chunk."""
    status: str          # "chunk_received" | "assembled" | "error"
    version_id: int
    chunk_index: int
    chunks_received: int  # how many chunks the server now has for this version
    total_chunks: int
    assembled: bool       # True when all chunks arrived and file is assembled


# ─── Week 6: Metadata Diff & Download Schemas ────────────────────────────────

class DiffItem(BaseModel):
    """One file the client is missing or has an outdated version of.

    Returned inside DiffResponse.missing_files.  The client uses
    file_path to know WHERE to download, and hash + version_num to
    verify what it received.
    """
    file_path: str
    file_id: int
    hash: str
    version_num: int
    version_id: int
    size_bytes: int
    storage_path: str    # MinIO key — client passes this back to /sync/download

    class Config:
        from_attributes = True


class DiffResponse(BaseModel):
    """Wrapper returned by GET /sync/metadata/diff.

    device_id:     Echo back so the client can sanity-check.
    missing_files: Files the device has never synced.
    outdated_files: Files the device has, but at an older version.
    """
    device_id: int
    missing_files: list[DiffItem]
    outdated_files: list[DiffItem]
    deleted_files: list[str] = []

