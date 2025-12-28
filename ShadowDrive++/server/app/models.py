from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, DateTime, BigInteger, UniqueConstraint
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

class Version(Base):
    __tablename__ = "versions"
    id = Column(BigInteger, primary_key=True, index=True)
    file_id = Column(BigInteger, ForeignKey("files.id"), nullable=False)
    version_num = Column(Integer, nullable=False)
    hash = Column(String(64), nullable=False)
    size_bytes = Column(BigInteger, nullable=False)
    storage_path = Column(String(500), nullable=False) #path to MinIO 
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class FileDeviceMap(Base):
    __tablename__ = "file_device_map"
    device_id = Column(BigInteger, ForeignKey("devices.id"), primary_key=True)
    file_id = Column(BigInteger, ForeignKey("files.id"), primary_key=True)
    version_id = Column(BigInteger, ForeignKey("versions.id"), nullable=False)
    synced_at = Column(DateTime(timezone=True), server_default=func.now())