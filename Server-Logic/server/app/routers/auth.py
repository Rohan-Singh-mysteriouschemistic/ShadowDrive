import os
import time
import logging
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, status, HTTPException, Request
from sqlalchemy.orm import Session
import redis.asyncio as aioredis
from .. import database, models, utils, schemas

logger = logging.getLogger(__name__)

class RateLimiter:
    def __init__(self):
        self.redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        self._redis = None
        self._local_history = {}

    async def get_redis(self):
        if self._redis is None:
            try:
                self._redis = aioredis.from_url(self.redis_url, decode_responses=True)
            except Exception as e:
                logger.warning("Failed to create Redis client for RateLimiter: %s", e)
        return self._redis

    async def check_rate_limit(self, ip: str) -> bool:
        now = time.time()
        window = 60
        limit = 5

        redis = await self.get_redis()
        if redis:
            try:
                key = f"rate_limit:{ip}"
                pipe = redis.pipeline()
                pipe.zremrangebyscore(key, "-inf", now - window)
                pipe.zadd(key, {f"{now}_{time.perf_counter()}": now})
                pipe.zcard(key)
                pipe.expire(key, window)
                results = await pipe.execute()
                count = results[2]
                if count > limit:
                    return False
                return True
            except Exception as e:
                logger.warning("Redis rate limiter execution failed, falling back to local memory: %s", e)

        # In-memory dict sliding window fallback
        history = self._local_history.get(ip, [])
        history = [t for t in history if t > now - window]
        history.append(now)
        self._local_history[ip] = history
        
        if len(history) > limit:
            return False
        return True

rate_limiter = RateLimiter()

router = APIRouter(
    prefix="/auth",
    tags=['Authentication']
)

@router.post('/login')
async def login(request: Request, user_credentials: schemas.UserLogin, db: Session = Depends(database.get_db)):
    client_ip = request.headers.get("x-forwarded-for")
    if client_ip:
        client_ip = client_ip.split(",")[0].strip()
    else:
        client_ip = request.client.host if request.client else "127.0.0.1"

    if not await rate_limiter.check_rate_limit(client_ip):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many requests. Please try again later."
        )

    user = db.query(models.User).filter(models.User.email == user_credentials.email).first()

    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid Credentials")

    if not utils.verify(user_credentials.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid Credentials")

    # Generate a signed JWT token
    access_token = utils.create_access_token(data={"user_id": user.id})
    return {"access_token": access_token, "token_type": "bearer"}

from ..dependencies import get_current_user
from ..dependencies import oauth2_scheme
import jwt

@router.post('/refresh')
def refresh_token(db: Session = Depends(database.get_db), token: str = Depends(oauth2_scheme)):
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    try:
        # Decode the token, explicitly ignoring the expiration claim
        payload = jwt.decode(token, utils.SECRET_KEY, algorithms=[utils.ALGORITHM], options={"verify_exp": False})
        user_id: int = payload.get("user_id")
        if user_id is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload")

        # Verify expiration with 24-hour grace window
        exp = payload.get("exp")
        if exp is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing expiration claim")
        try:
            exp_datetime = datetime.fromtimestamp(exp, tz=timezone.utc)
        except (ValueError, TypeError, OverflowError):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid expiration claim")

        now = datetime.now(timezone.utc)
        if not (exp_datetime + timedelta(hours=24) > now):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token has expired past the 24-hour grace period")

    except jwt.PyJWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid signature")

    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    # Issue a fresh token
    new_token = utils.create_access_token(data={"user_id": user.id})
    return {"access_token": new_token, "token_type": "bearer"}

@router.get('/me')
def get_me(current_user: models.User = Depends(get_current_user)):
    return {
        "id": current_user.id,
        "username": current_user.username,
        "email": current_user.email,
        "storage_quota": current_user.storage_quota
    }
