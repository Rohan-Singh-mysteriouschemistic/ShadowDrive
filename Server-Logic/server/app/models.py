from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, DateTime, BigInteger, UniqueConstraint, Enum as SAEnum
import enum
from sqlalchemy.sql import func
from .database import Base

class User(Base):
    __tablename__ = "users"
    id = Column(BigInteger, primary_key=True, index=True)
    username = Column(String(50), unique=True, nullable=False)
    email = Column(String(255), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class Device(Base):
    __tablename__ = "devices"
    id = Column(BigInteger, primary_key=True, index=True)
    user_id = Column(BigInteger, ForeignKey("users.id"), nullable=False)
    device_name = Column(String(100), nullable=False)
    is_online = Column(Boolean, default=False)
    last_seen_at = Column(DateTime(timezone=True), nullable=True)
    __table_args__ = (UniqueConstraint('user_id', 'device_name', name='unique_device_per_user'),)

class File(Base):
    __tablename__ = "files"
    id = Column(BigInteger, primary_key=True, index=True)
    user_id = Column(BigInteger, ForeignKey("users.id"), nullable=False)
    file_path = Column(String(1000), nullable=False)
    is_deleted = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    __table_args__ = (UniqueConstraint('user_id', 'file_path', name='unique_path_per_user'),)

class UploadStatus(str, enum.Enum):
    """Upload lifecycle states for a Version record (Week 8).

    pending    → /announce created the row; no bytes received yet.
    uploading  → At least one chunk has arrived; transfer in progress.
    processing → All bytes received; background worker is verifying hash /
                 generating thumbnail.
    complete   → Worker finished successfully; version is ready for sync.
    failed     → Worker detected a hash mismatch or an unrecoverable error.
    """
    pending    = "pending"
    uploading  = "uploading"
    processing = "processing"
    complete   = "complete"
    failed     = "failed"


class Version(Base):
    __tablename__ = "versions"
    id = Column(BigInteger, primary_key=True, index=True)
    file_id = Column(BigInteger, ForeignKey("files.id"), nullable=False)
    version_num = Column(Integer, nullable=False)
    hash = Column(String(64), nullable=False)
    size_bytes = Column(BigInteger, nullable=False)
    storage_path = Column(String(500), nullable=False) #path to MinIO
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # ─── Week 8: Async Upload Tracking ────────────────────────────────────
    upload_status = Column(
        SAEnum(UploadStatus, name="upload_status_enum", create_constraint=True),
        nullable=False,
        server_default="pending"
    )
    # RQ job ID — allows polling /sync/upload/status/<version_id> to check
    # whether the background worker has finished.
    job_id = Column(String(64), nullable=True)

    # ─── Week 7: Conflict Resolution ─────────────────────────────────────
    # Self-referential FK: which version was this edit based on?
    # NULL for the first version of a file, or for conflict copies.
    parent_version_id = Column(BigInteger, ForeignKey("versions.id"), nullable=True)

    # True if this version was auto-created as a conflict copy (the "loser"
    # in a Last-Write-Wins comparison).  The original file_path is renamed
    # to "<name> (Conflicted copy).<ext>" for these records.
    is_conflict_copy = Column(Boolean, default=False)

    # Client-reported timestamp of when the edit was made.  Used as the
    # tiebreaker for LWW.  Falls back to server's created_at if absent.
    announced_at = Column(DateTime(timezone=True), nullable=True)

class FileDeviceMap(Base):
    __tablename__ = "file_device_map"
    device_id = Column(BigInteger, ForeignKey("devices.id"), primary_key=True)
    file_id = Column(BigInteger, ForeignKey("files.id"), primary_key=True)
    version_id = Column(BigInteger, ForeignKey("versions.id"), nullable=False)
    synced_at = Column(DateTime(timezone=True), server_default=func.now())


class ChunkUpload(Base):
    """Tracks individual chunk uploads for a chunked file transfer (Week 5).

    When a client uploads a large file, it splits the file into fixed-size
    chunks (default 4 MB) and sends each chunk to /sync/upload_chunk.
    This table records which chunks have been received for a given version_id.

    Once total_chunks == the number of rows for that version_id, the server
    triggers assembly: all chunks are concatenated in order and stored as a
    single object in MinIO.
    """
    __tablename__ = "chunk_uploads"
    id = Column(BigInteger, primary_key=True, index=True)
    version_id = Column(BigInteger, ForeignKey("versions.id"), nullable=False)
    chunk_index = Column(Integer, nullable=False)       # 0-based index
    total_chunks = Column(Integer, nullable=False)       # total expected chunks
    chunk_storage_key = Column(String(500), nullable=False)  # MinIO key for this chunk
    size_bytes = Column(BigInteger, nullable=False)
    received_at = Column(DateTime(timezone=True), server_default=func.now())
    __table_args__ = (
        UniqueConstraint('version_id', 'chunk_index', name='unique_chunk_per_version'),
    )


class StoredChunk(Base):
    """Tracks unique chunks stored globally in MinIO (Week 1 / Phase 1 Enhancement).

    Chunks are stored in MinIO using the chunk's SHA256 hash as the key.
    Any file version that contains this chunk can refer to it.
    """
    __tablename__ = "stored_chunks"
    chunk_hash = Column(String(64), primary_key=True, index=True)
    user_id = Column(BigInteger, ForeignKey("users.id"), nullable=True)
    storage_path = Column(String(500), nullable=False)  # e.g. chunks/{chunk_hash}
    size_bytes = Column(BigInteger, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class VersionChunk(Base):
    """Maps version files to their constituent chunks in order (Week 1 / Phase 1 Enhancement)."""
    __tablename__ = "version_chunks"
    id = Column(BigInteger, primary_key=True, index=True)
    version_id = Column(BigInteger, ForeignKey("versions.id"), nullable=False)
    chunk_index = Column(Integer, nullable=False)       # 0-based index
    chunk_hash = Column(String(64), ForeignKey("stored_chunks.chunk_hash"), nullable=False)
    __table_args__ = (
        UniqueConstraint('version_id', 'chunk_index', name='unique_chunk_index_per_version'),
    )