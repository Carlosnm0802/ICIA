from __future__ import annotations

import json
import sqlite3
import tempfile
import zipfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from sqlalchemy.orm import Session

from app.core.config import BACKUP_DIR, DATABASE_PATH, PHOTOS_DIR
from app.models import Configuracion

BACKUP_PREFIX = "icia"
FULL_BACKUP_PREFIX = "icia_completo"
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


@dataclass(frozen=True)
class FullBackupResult:
    source_path: Path
    destination_path: Path
    created_at: datetime
    size_bytes: int
    database_size_bytes: int
    photos: int
    schema_revision: str | None


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


def _schema_revision(database_path: Path) -> str | None:
    connection = sqlite3.connect(database_path)
    try:
        row = connection.execute(
            "SELECT version_num FROM alembic_version"
        ).fetchone()
    except sqlite3.Error:
        return None
    finally:
        connection.close()
    return str(row[0]) if row is not None else None


def _photo_paths(photos_dir: Path) -> list[Path]:
    base = Path(photos_dir).expanduser().resolve()
    if not base.is_dir():
        return []
    return sorted(
        path
        for path in base.rglob("*")
        if path.is_file()
        and not any(
            part.startswith(".")
            for part in path.relative_to(base).parts
        )
    )


def create_full_backup(
    destination_dir: Path = BACKUP_DIR,
    *,
    source_path: Path = DATABASE_PATH,
    photos_dir: Path = PHOTOS_DIR,
    now: datetime | None = None,
) -> FullBackupResult:
    source = Path(source_path).expanduser().resolve()
    if not source.is_file():
        raise BackupError(f"No existe la base de datos de origen: {source}")

    destination = _prepare_destination(destination_dir)
    created_at = (now or datetime.now()).replace(microsecond=0)
    filename = (
        f"{FULL_BACKUP_PREFIX}_"
        f"{created_at.strftime(FILENAME_TIMESTAMP_FORMAT)}.zip"
    )
    destination_path = destination / filename
    if destination_path.exists():
        raise BackupError(
            f"Ya existe un respaldo con ese nombre: {destination_path}"
        )

    temp_zip = destination_path.with_name(f".{destination_path.name}.tmp")
    temp_zip.unlink(missing_ok=True)
    photos = _photo_paths(photos_dir)

    try:
        with tempfile.TemporaryDirectory(
            prefix=".icia_backup_",
            dir=destination,
        ) as temp_dir:
            temporal = Path(temp_dir)
            db_result = create_backup(
                temporal,
                source_path=source,
                now=created_at,
            )
            manifest = {
                "app": "ICIA",
                "creado_en": created_at.strftime(CONFIG_TIMESTAMP_FORMAT),
                "schema_revision": _schema_revision(
                    db_result.destination_path
                ),
                "fotos": len(photos),
            }
            photos_base = Path(photos_dir).expanduser().resolve()
            with zipfile.ZipFile(
                temp_zip,
                "w",
                compression=zipfile.ZIP_DEFLATED,
            ) as archivo:
                archivo.write(db_result.destination_path, "icia.db")
                archivo.writestr(
                    "manifest.json",
                    json.dumps(manifest, ensure_ascii=False, indent=2),
                )
                for foto in photos:
                    archivo.write(
                        foto,
                        Path("photos") / foto.relative_to(photos_base),
                    )
                if not photos:
                    archivo.writestr("photos/", b"")

        with zipfile.ZipFile(temp_zip) as archivo:
            if archivo.testzip() is not None:
                raise BackupError("El respaldo completo está dañado.")

        temp_zip.replace(destination_path)
    except BackupError:
        temp_zip.unlink(missing_ok=True)
        raise
    except (OSError, zipfile.BadZipFile) as exc:
        temp_zip.unlink(missing_ok=True)
        raise BackupError(f"No se pudo crear el respaldo: {exc}") from exc
    except Exception:
        temp_zip.unlink(missing_ok=True)
        raise

    return FullBackupResult(
        source_path=source,
        destination_path=destination_path,
        created_at=created_at,
        size_bytes=destination_path.stat().st_size,
        database_size_bytes=db_result.size_bytes,
        photos=len(photos),
        schema_revision=manifest["schema_revision"],
    )


def backup_completo_database(
    session: Session,
    destination_dir: Path = BACKUP_DIR,
    *,
    source_path: Path = DATABASE_PATH,
    photos_dir: Path = PHOTOS_DIR,
    now: datetime | None = None,
) -> FullBackupResult:
    result = create_full_backup(
        destination_dir,
        source_path=source_path,
        photos_dir=photos_dir,
        now=now,
    )
    record_last_backup(session, result)
    return result


def ruta_respaldo(session: Session) -> Path:
    config = session.get(Configuracion, "ruta_respaldo")
    if config is not None and config.valor.strip():
        return Path(config.valor).expanduser()
    return BACKUP_DIR


def guardar_ruta_respaldo(
    session: Session,
    ruta: str | None,
) -> Path:
    limpia = (ruta or "").strip()
    if not limpia:
        session.query(Configuracion).filter_by(clave="ruta_respaldo").delete()
        session.flush()
        return BACKUP_DIR
    destino = Path(limpia).expanduser()
    if destino.exists() and not destino.is_dir():
        raise BackupError("La ruta de respaldo debe ser una carpeta.")
    config = session.get(Configuracion, "ruta_respaldo")
    if config is None:
        session.add(
            Configuracion(
                clave="ruta_respaldo",
                valor=str(destino),
                actualizado_en=datetime.now().strftime(
                    CONFIG_TIMESTAMP_FORMAT
                ),
            )
        )
    else:
        config.valor = str(destino)
        config.actualizado_en = datetime.now().strftime(
            CONFIG_TIMESTAMP_FORMAT
        )
    session.flush()
    return destino


def ultimo_respaldo(session: Session) -> datetime | None:
    config = session.get(Configuracion, LAST_BACKUP_KEY)
    if config is None or not config.valor.strip():
        return None
    try:
        return datetime.strptime(config.valor, CONFIG_TIMESTAMP_FORMAT)
    except ValueError:
        return None


def recordatorio_respaldo(
    session: Session,
    *,
    dias: int = 7,
    ahora: datetime | None = None,
) -> str | None:
    fecha = ultimo_respaldo(session)
    if fecha is None:
        return "Todavía no se ha creado un respaldo."
    referencia = ahora or datetime.now()
    if (referencia - fecha).days < dias:
        return None
    return (
        "El último respaldo tiene "
        f"{(referencia - fecha).days} días. Conviene respaldar a la USB."
    )


def record_last_backup(
    session: Session,
    result: BackupResult | FullBackupResult,
) -> None:
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
