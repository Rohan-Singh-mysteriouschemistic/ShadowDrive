import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

#username, password, hostname, DB
SQLALCHEMY_DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:SDrive516477%23@localhost/shadowdrive")

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    pool_pre_ping=True,
    pool_recycle=1800
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """Yield a database session for dependency injection, then auto-close.

    Week 4 Hardening (Scenario C): If an unhandled exception occurs during
    request processing, any uncommitted work is rolled back before the
    session is closed. This prevents "zombie" transactions that hold
    PostgreSQL locks forever.
    """
    db = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()