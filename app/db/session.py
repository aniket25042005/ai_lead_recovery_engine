import logging
from typing import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from app.core.config import settings
from app.db.models import Base

logger = logging.getLogger("zizzet.db")

def create_db_engine():
    db_url = settings.DATABASE_URL
    try:
        if db_url.startswith("postgresql"):
            engine = create_engine(
                db_url,
                pool_pre_ping=settings.DB_POOL_PRE_PING,
                pool_size=settings.DB_POOL_SIZE,
                max_overflow=settings.DB_MAX_OVERFLOW,
            )
            # Test connection
            with engine.connect():
                pass
            logger.info("Successfully connected to PostgreSQL database at %s", db_url.split("@")[-1])
            return engine
        else:
            # SQLite or other DB
            return create_engine(
                db_url,
                connect_args={"check_same_thread": False} if "sqlite" in db_url else {},
            )
    except Exception as exc:
        if settings.FALLBACK_TO_SQLITE_ON_DB_ERROR:
            logger.warning(
                "Could not connect to configured database (%s): %s. "
                "Falling back to local SQLite at %s for local development/testing.",
                db_url, exc, settings.SQLITE_FALLBACK_URL
            )
            return create_engine(
                settings.SQLITE_FALLBACK_URL,
                connect_args={"check_same_thread": False},
            )
        raise exc


engine = create_db_engine()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables initialized successfully.")
