import bcrypt
import jwt
import os
from datetime import datetime, timedelta, timezone
from typing import Optional
from passlib.context import CryptContext

# CryptContext for passlib bcrypt hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# JWT configuration
SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    raise RuntimeError(
        "FATAL: SECRET_KEY environment variable is not set. "
        "Generate one with: openssl rand -hex 32"
    )
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # 1 week expiration

def hash(password: str) -> str:
    """Hash a password using bcrypt via passlib."""
    return pwd_context.hash(password)

def verify(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain password against the hashed password."""
    try:
        return pwd_context.verify(plain_password, hashed_password)
    except Exception:
        # Fallback to direct bcrypt checkpw in case legacy hash format is stored
        try:
            return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))
        except Exception:
            return False

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Generate a signed JWT access token."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)