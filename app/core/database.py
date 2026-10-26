from collections.abc import Generator
from pathlib import Path
from typing import Any

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.engine import URL
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import DATABASE_PATH, ensure_directories


class Base(DeclarativeBase):
    pass


def _set_sqlite_pragmas(dbapi_connection: Any, _connection_record: Any) -> None:
    cursor = dbapi_connection.cursor()
    try:
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA busy_timeout=5000")
    finally:
        cursor.close()


def build_engine(database_path: Path) -> Engine:
    resolved_path = Path(database_path).expanduser().resolve()
    resolved_path.parent.mkdir(parents=True, exist_ok=True)
    url = URL.create("sqlite", database=resolved_path.as_posix())
    engine = create_engine(
        url,
        connect_args={"check_same_thread": False, "timeout": 5},
    )
    event.listen(engine, "connect", _set_sqlite_pragmas)
    return engine


ensure_directories()
engine = build_engine(DATABASE_PATH)
SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    expire_on_commit=False,
)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
