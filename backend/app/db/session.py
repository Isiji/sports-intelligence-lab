# backend/app/db/session.py

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import normalized_database_url, settings


engine = create_engine(
    normalized_database_url(settings.database_url),
    future=True,
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    future=True,
)


def get_session() -> Generator[Session, None, None]:
    session = SessionLocal()

    try:
        yield session

    finally:
        session.close()


# ADD THIS
def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()

    try:
        yield db

    finally:
        db.close()


def get_cli_session() -> Session:
    return SessionLocal()