from pydantic import BaseModel, EmailStr
from datetime import datetime

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
    """
    path: str
    hash: str | None = None
    event: str


class MetadataResponse(BaseModel):
    """Response telling the client what happened."""
    status: str          # "accepted" | "already_synced" | "deleted_acknowledged"
    file_id: int
    version_id: int | None = None
    upload_required: bool


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

