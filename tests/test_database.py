from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

import app.core.database as database
from app.core.database import build_engine


def test_sqlite_pragmas(tmp_path: Path) -> None:
    database_path = tmp_path / "test.db"
    engine = build_engine(database_path)
    try:
        with engine.connect() as connection:
            assert connection.exec_driver_sql("PRAGMA journal_mode").scalar() == "wal"
            assert connection.exec_driver_sql("PRAGMA synchronous").scalar() == 1
            assert connection.exec_driver_sql("PRAGMA foreign_keys").scalar() == 1
            assert connection.exec_driver_sql("PRAGMA busy_timeout").scalar() == 5000
        assert database_path.exists()
    finally:
        engine.dispose()


def test_session_can_execute_query(tmp_path: Path) -> None:
    engine = build_engine(tmp_path / "test.db")
    session_factory = sessionmaker(bind=engine)
    try:
        with session_factory() as session:
            assert session.execute(text("SELECT 1")).scalar() == 1
    finally:
        engine.dispose()


def test_foreign_keys_are_enforced(tmp_path: Path) -> None:
    engine = build_engine(tmp_path / "test.db")
    try:
        with engine.begin() as connection:
            connection.exec_driver_sql("CREATE TABLE parent (id INTEGER PRIMARY KEY)")
            connection.exec_driver_sql(
                "CREATE TABLE child ("
                "id INTEGER PRIMARY KEY, "
                "parent_id INTEGER REFERENCES parent(id)"
                ")"
            )
        with pytest.raises(IntegrityError):
            with engine.begin() as connection:
                connection.exec_driver_sql(
                    "INSERT INTO child (parent_id) VALUES (999)"
                )
    finally:
        engine.dispose()


class TrackingSession(Session):
    closed = False

    def close(self) -> None:
        self.closed = True
        super().close()


def test_get_db_yields_and_closes_session(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = build_engine(tmp_path / "get_db.db")
    factory = sessionmaker(bind=engine, class_=TrackingSession)
    monkeypatch.setattr(database, "SessionLocal", factory)
    generator = database.get_db()
    try:
        session = next(generator)
        assert isinstance(session, TrackingSession)
        assert session.execute(text("SELECT 1")).scalar() == 1
        with pytest.raises(StopIteration):
            next(generator)
        assert session.closed
    finally:
        generator.close()
        engine.dispose()
