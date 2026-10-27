import sqlite3
from collections.abc import Iterator
from datetime import datetime
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy.orm import Session, sessionmaker

from app.core.database import build_engine
from app.models import Configuracion, Sucursal
from app.services.backup_service import (
    BackupError,
    backup_database,
    create_backup,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKUP_TIME = datetime(2026, 10, 27, 12, 34, 56)
BACKUP_NAME = "icia_20261027_123456.db"


def _config(database_path: Path) -> Config:
    config = Config(str(PROJECT_ROOT / "alembic.ini"))
    config.set_main_option("prepend_sys_path", str(PROJECT_ROOT))
    config.set_main_option(
        "sqlalchemy.url",
        f"sqlite:///{database_path.as_posix()}",
    )
    return config


@pytest.fixture
def database_path(tmp_path: Path) -> Path:
    path = tmp_path / "source.db"
    command.upgrade(_config(path), "head")
    return path


@pytest.fixture
def session(database_path: Path) -> Iterator[Session]:
    engine = build_engine(database_path)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    database_session = factory()
    try:
        yield database_session
    finally:
        database_session.close()
        engine.dispose()


def test_backup_creates_verified_copy_and_records_last_backup(
    session: Session,
    database_path: Path,
    tmp_path: Path,
) -> None:
    session.add(Sucursal(nombre="El Refugio", prefijo_folio="REF"))
    session.add(
        Configuracion(
            clave="ultimo_respaldo",
            valor="2020-01-01 00:00:00",
            actualizado_en="2020-01-01 00:00:00",
        )
    )
    session.add(
        Configuracion(
            clave="ultimo_respaldo_ruta",
            valor="/ruta/anterior.db",
            actualizado_en="2020-01-01 00:00:00",
        )
    )
    session.commit()

    backup_dir = tmp_path / "backups"
    result = backup_database(
        session,
        backup_dir,
        source_path=database_path,
        now=BACKUP_TIME,
    )
    session.commit()

    assert result.source_path == database_path.resolve()
    assert result.destination_path == backup_dir / BACKUP_NAME
    assert result.destination_path.exists()
    assert result.size_bytes == result.destination_path.stat().st_size
    assert result.size_bytes > 0

    with sqlite3.connect(result.destination_path) as connection:
        assert connection.execute("PRAGMA integrity_check").fetchone() == ("ok",)
        assert connection.execute(
            "SELECT nombre FROM sucursales"
        ).fetchall() == [("El Refugio",)]

    last_backup = session.get(Configuracion, "ultimo_respaldo")
    last_backup_path = session.get(Configuracion, "ultimo_respaldo_ruta")
    assert last_backup is not None
    assert last_backup.valor == "2026-10-27 12:34:56"
    assert last_backup.actualizado_en == "2026-10-27 12:34:56"
    assert last_backup_path is not None
    assert last_backup_path.valor == str(result.destination_path)
    assert last_backup_path.actualizado_en == "2026-10-27 12:34:56"


def test_backup_fails_when_source_does_not_exist(tmp_path: Path) -> None:
    with pytest.raises(BackupError):
        create_backup(
            tmp_path / "backups",
            source_path=tmp_path / "missing.db",
            now=BACKUP_TIME,
        )


def test_backup_fails_when_destination_name_exists(
    database_path: Path,
    tmp_path: Path,
) -> None:
    backup_dir = tmp_path / "backups"
    backup_dir.mkdir()
    existing = backup_dir / BACKUP_NAME
    existing.write_bytes(b"respaldo anterior")

    with pytest.raises(BackupError):
        create_backup(
            backup_dir,
            source_path=database_path,
            now=BACKUP_TIME,
        )

    assert existing.read_bytes() == b"respaldo anterior"


def test_backup_fails_when_destination_is_not_a_directory(
    database_path: Path,
    tmp_path: Path,
) -> None:
    invalid_destination = tmp_path / "no-es-carpeta"
    invalid_destination.write_text("contenido")

    with pytest.raises(BackupError):
        create_backup(
            invalid_destination,
            source_path=database_path,
            now=BACKUP_TIME,
        )


def test_backup_does_not_block_source_reads(
    session: Session,
    database_path: Path,
    tmp_path: Path,
) -> None:
    session.add(Sucursal(nombre="El Refugio", prefijo_folio="REF"))
    session.commit()

    reader = sqlite3.connect(database_path, isolation_level=None)
    try:
        reader.execute("BEGIN")
        assert reader.execute("SELECT COUNT(*) FROM sucursales").fetchone() == (1,)

        result = create_backup(
            tmp_path / "backups",
            source_path=database_path,
            now=BACKUP_TIME,
        )

        assert result.destination_path.exists()
        assert reader.execute("SELECT COUNT(*) FROM sucursales").fetchone() == (1,)
    finally:
        reader.close()


def test_backup_fails_when_source_equals_destination(tmp_path: Path) -> None:
    source = tmp_path / BACKUP_NAME
    command.upgrade(_config(source), "head")

    with pytest.raises(BackupError, match="mismo"):
        create_backup(
            tmp_path,
            source_path=source,
            now=BACKUP_TIME,
        )


def test_failed_backup_does_not_leave_temp_files_or_update_last_backup(
    session: Session,
    tmp_path: Path,
) -> None:
    session.add(
        Configuracion(
            clave="ultimo_respaldo",
            valor="2020-01-01 00:00:00",
            actualizado_en="2020-01-01 00:00:00",
        )
    )
    session.commit()

    invalid_source = tmp_path / "invalid.db"
    invalid_source.write_bytes(b"no es una base sqlite")
    backup_dir = tmp_path / "backups"

    with pytest.raises(BackupError):
        backup_database(
            session,
            backup_dir,
            source_path=invalid_source,
            now=BACKUP_TIME,
        )

    assert list(backup_dir.iterdir()) == []
    last_backup = session.get(Configuracion, "ultimo_respaldo")
    assert last_backup is not None
    assert last_backup.valor == "2020-01-01 00:00:00"
