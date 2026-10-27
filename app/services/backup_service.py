from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from sqlalchemy.orm import Session

from app.core.config import BACKUP_DIR, DATABASE_PATH
from app.models import Configuracion

BACKUP_PREFIX = "icia"
FILENAME_TIMESTAMP_FORMAT = "%Y%m%d_%H%M%S"
CONFIG_TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M:%S"
LAST_BACKUP_KEY = "ultimo_respaldo"
LAST_BACKUP_PATH_KEY = "ultimo_respaldo_ruta"


class BackupError(RuntimeError):
    pass


@dataclass(frozen=True)
class BackupResult:
    source_path: Path
    destination_path: Path
    created_at: datetime
    size_bytes: int


def _open_database(path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(path, timeout=5.0, isolation_level=None)
    connection.execute("PRAGMA busy_timeout=5000")
    return connection


def _remove_database_files(path: Path) -> None:
    for candidate in (path, Path(f"{path}-wal"), Path(f"{path}-shm")):
        candidate.unlink(missing_ok=True)


def _prepare_destination(destination_dir: Path) -> Path:
    destination = Path(destination_dir).expanduser().resolve()
    if destination.exists() and not destination.is_dir():
        raise BackupError(
            f"La ruta de respaldo no es una carpeta: {destination}"
        )
    try:
        destination.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise BackupError(
            f"No se pudo preparar la carpeta de respaldo: {destination}"
        ) from exc
    return destination


def create_backup(
    destination_dir: Path = BACKUP_DIR,
    *,
    source_path: Path = DATABASE_PATH,
    now: datetime | None = None,
) -> BackupResult:
    source = Path(source_path).expanduser().resolve()
    if not source.is_file():
        raise BackupError(f"No existe la base de datos de origen: {source}")

    destination = _prepare_destination(destination_dir)
    created_at = (now or datetime.now()).replace(microsecond=0)
    filename = (
        f"{BACKUP_PREFIX}_{created_at.strftime(FILENAME_TIMESTAMP_FORMAT)}.db"
    )
    destination_path = destination / filename
    if source == destination_path:
        raise BackupError(
            "El archivo de origen y el respaldo no pueden ser el mismo"
        )
    if destination_path.exists():
        raise BackupError(
            f"Ya existe un respaldo con ese nombre: {destination_path}"
        )

    temp_path = destination_path.with_name(f".{destination_path.name}.tmp")
    _remove_database_files(temp_path)

    source_connection: sqlite3.Connection | None = None
    target_connection: sqlite3.Connection | None = None
    try:
        try:
            source_connection = _open_database(source)
            target_connection = _open_database(temp_path)
            source_connection.backup(target_connection, pages=-1, sleep=0.05)
            integrity = target_connection.execute(
                "PRAGMA integrity_check"
            ).fetchone()
            if integrity is None or integrity[0] != "ok":
                raise BackupError(
                    f"La verificación de integridad falló: {filename}"
                )
        finally:
            if target_connection is not None:
                target_connection.close()
            if source_connection is not None:
                source_connection.close()
    except BackupError:
        _remove_database_files(temp_path)
        raise
    except (sqlite3.Error, OSError) as exc:
        _remove_database_files(temp_path)
        raise BackupError(f"No se pudo crear el respaldo: {exc}") from exc

    try:
        if destination_path.exists():
            raise BackupError(
                f"Ya existe un respaldo con ese nombre: {destination_path}"
            )
        temp_path.replace(destination_path)
    except BackupError:
        _remove_database_files(temp_path)
        raise
    except OSError as exc:
        _remove_database_files(temp_path)
        raise BackupError(f"No se pudo guardar el respaldo: {exc}") from exc
    finally:
        _remove_database_files(temp_path)

    return BackupResult(
        source_path=source,
        destination_path=destination_path,
        created_at=created_at,
        size_bytes=destination_path.stat().st_size,
    )


def record_last_backup(session: Session, result: BackupResult) -> None:
    timestamp = result.created_at.strftime(CONFIG_TIMESTAMP_FORMAT)
    values = {
        LAST_BACKUP_KEY: timestamp,
        LAST_BACKUP_PATH_KEY: str(result.destination_path),
    }
    for key, value in values.items():
        config = session.get(Configuracion, key)
        if config is None:
            session.add(
                Configuracion(
                    clave=key,
                    valor=value,
                    actualizado_en=timestamp,
                )
            )
        else:
            config.valor = value
            config.actualizado_en = timestamp
    session.flush()


def backup_database(
    session: Session,
    destination_dir: Path = BACKUP_DIR,
    *,
    source_path: Path = DATABASE_PATH,
    now: datetime | None = None,
) -> BackupResult:
    result = create_backup(
        destination_dir,
        source_path=source_path,
        now=now,
    )
    record_last_backup(session, result)
    return result
