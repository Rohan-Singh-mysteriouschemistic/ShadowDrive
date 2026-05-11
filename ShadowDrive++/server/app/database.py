from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

#username, password, hostname, DB
SQLALCHEMY_DATABASE_URL = "postgresql://user:SDrive516477%23@localhost/shadowdrive"

# ─── Engine Configuration (Week 4 Hardening) ─────────────────────────────────
# pool_pre_ping=True: Before handing a connection to our code, SQLAlchemy
#   sends a lightweight "SELECT 1" to check if the connection is alive.
#   If the database server restarted and killed our old connections, the
#   stale connection is silently replaced. Without this, we get a
#   "connection reset by peer" error on the first request after a restart.
#
# pool_recycle=1800: Connections older than 30 minutes are automatically
#   replaced. This prevents "idle connection timeout" errors from PostgreSQL
#   or network firewalls that kill long-idle TCP sockets.
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