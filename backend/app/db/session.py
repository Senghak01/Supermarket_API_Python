from typing import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from app.core.config import settings

# Engine configuration
# Note: SQLite in tests will need different pool args, so we handle sqlite vs mysql
is_sqlite = settings.DATABASE_URL.startswith("sqlite")
connect_args = {"check_same_thread": False} if is_sqlite else {}
pool_kwargs = {} if is_sqlite else {
    "pool_size": settings.DATABASE_POOL_SIZE,
    "max_overflow": settings.DATABASE_MAX_OVERFLOW,
    "pool_pre_ping": True,
    "pool_recycle": 3600,
}

engine = create_engine(
    settings.DATABASE_URL,
    connect_args=connect_args,
    **pool_kwargs
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    """Dependency providing a transactional database session per request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

