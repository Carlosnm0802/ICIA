from __future__ import annotations

import json
import shutil
import sqlite3
import tempfile
import zipfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path, PurePosixPath

from alembic import command
from alembic.script import ScriptDirectory

from app.bootstrap import alembic_config
from app.core.config import (
    BACKUP_DIR,
    DATA_DIR,
    DATABASE_PATH,
    PHOTOS_DIR,
)
from app.services import backup_service

TABLAS_REQUERIDAS = {
    "alumnos",
    "pagos",
    "asistencias",
    "sesiones",
    "grupos",
    "folio_contadores",
    "alembic_version",
}


class RestoreError(RuntimeError):
    pass


@dataclass(frozen=True)
class RestoreResult:
    restored_at: datetime
    safety_backup: Path | None
    photos: int
    schema_revision: str | None


def _validar_miembro(info: zipfile.ZipInfo) -> PurePosixPath:
    nombre = info.filename
    if nombre.startswith("/") or "\\" in nombre:
        raise RestoreError("El respaldo contiene rutas no válidas.")
    ruta = PurePosixPath(nombre)
    if ruta.is_absolute() or ".." in ruta.parts:
        raise RestoreError("El respaldo contiene rutas no válidas.")
    if any(":" in part for part in ruta.parts):
        raise RestoreError("El respaldo contiene rutas no válidas.")
    if not (
        nombre in {"icia.db", "manifest.json", "photos/"}
        or nombre.startswith("photos/")
    ):
        raise RestoreError("El respaldo contiene archivos no permitidos.")
    if (info.external_attr >> 16) & 0o170000 == 0o120000:
        raise RestoreError("El respaldo contiene enlaces no permitidos.")
    return ruta


def _extraer(backup_path: Path, destino: Path) -> tuple[Path, Path]:
    try:
        with zipfile.ZipFile(backup_path) as archivo:
            for info in archivo.infolist():
                ruta = _validar_miembro(info)
                if info.is_dir():
                    continue
                objetivo = destino / ruta
                objetivo.parent.mkdir(parents=True, exist_ok=True)
                with archivo.open(info) as origen, objetivo.open(
                    "wb"
                ) as salida:
                    shutil.copyfileobj(origen, salida)
    except (OSError, zipfile.BadZipFile) as exc:
        raise RestoreError(f"No se pudo leer el respaldo: {exc}") from exc

    database = destino / "icia.db"
    if not database.is_file():
        raise RestoreError("El respaldo no contiene la base de datos.")
    photos = destino / "photos"
    photos.mkdir(parents=True, exist_ok=True)
    return database, photos


def _revision(database_path: Path) -> str | None:
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


def _validar_base(database_path: Path) -> str:
    connection = sqlite3.connect(database_path)
    try:
        integridad = connection.execute(
            "PRAGMA integrity_check"
        ).fetchone()
        tablas = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
    except sqlite3.Error as exc:
        raise RestoreError(f"La base del respaldo no es válida: {exc}") from exc
    finally:
        connection.close()

    if integridad is None or integridad[0] != "ok":
        raise RestoreError("La verificación de integridad del respaldo falló.")
    faltantes = TABLAS_REQUERIDAS - tablas
    if faltantes:
        raise RestoreError(
            "El respaldo no tiene el esquema de ICIA: "
            + ", ".join(sorted(faltantes))
        )
    revision = _revision(database_path)
    if revision is None:
        raise RestoreError("El respaldo no tiene versión de esquema.")
    return revision


def _migrar_si_es_necesario(database_path: Path) -> str:
    config = alembic_config(database_path)
    encabezado = ScriptDirectory.from_config(config).get_current_head()
    revision = _revision(database_path)
    if revision != encabezado:
        try:
            command.upgrade(config, "head")
        except Exception as exc:
            raise RestoreError(
                "No se pudo actualizar el esquema del respaldo: "
                f"{exc}"
            ) from exc
    revision = _revision(database_path)
    if revision is None:
        raise RestoreError("No se pudo determinar la versión del respaldo.")
    return revision


def _quitar_wal(database_path: Path) -> None:
    for candidate in (
        database_path,
        Path(f"{database_path}-wal"),
        Path(f"{database_path}-shm"),
    ):
        candidate.unlink(missing_ok=True)


def _aplicar_fotos(origen: Path, destino: Path, marca: str) -> None:
    destino.parent.mkdir(parents=True, exist_ok=True)
    respaldo_anterior = None
    if destino.exists():
        respaldo_anterior = destino.with_name(
            f"{destino.name}.antes_{marca}"
        )
        if respaldo_anterior.exists():
            shutil.rmtree(respaldo_anterior)
        destino.replace(respaldo_anterior)
    try:
        shutil.copytree(origen, destino)
    except OSError:
        if destino.exists():
            shutil.rmtree(destino)
        if respaldo_anterior is not None and respaldo_anterior.exists():
            respaldo_anterior.replace(destino)
        raise
    if respaldo_anterior is not None:
        shutil.rmtree(respaldo_anterior, ignore_errors=True)


def restore_full_backup(
    backup_path: Path,
    *,
    database_path: Path = DATABASE_PATH,
    photos_dir: Path = PHOTOS_DIR,
    safety_dir: Path = BACKUP_DIR,
    now: datetime | None = None,
) -> RestoreResult:
    origen = Path(backup_path).expanduser().resolve()
    if not origen.is_file():
        raise RestoreError(f"No existe el respaldo: {origen}")
    fecha = (now or datetime.now()).replace(microsecond=0)
    marca = fecha.strftime("%Y%m%d_%H%M%S")

    with tempfile.TemporaryDirectory(prefix=".icia_restore_") as temp_dir:
        staging = Path(temp_dir)
        database, photos = _extraer(origen, staging)
        _validar_base(database)
        revision = _migrar_si_es_necesario(database)

        safety = None
        if Path(database_path).is_file():
            safety = backup_service.create_full_backup(
                safety_dir,
                source_path=database_path,
                photos_dir=photos_dir,
                now=fecha,
            ).destination_path

        db_destino = Path(database_path).expanduser().resolve()
        db_destino.parent.mkdir(parents=True, exist_ok=True)
        temporal = db_destino.with_name(f".{db_destino.name}.restore")
        shutil.copy2(database, temporal)
        _quitar_wal(db_destino)
        temporal.replace(db_destino)

        try:
            _aplicar_fotos(photos, Path(photos_dir).resolve(), marca)
        except OSError as exc:
            raise RestoreError(
                "La base se restauró, pero no se pudieron restaurar las "
                f"fotos. El respaldo de seguridad está en {safety}. {exc}"
            ) from exc
        fotos_restauradas = sum(
            1 for item in photos.rglob("*") if item.is_file()
        )

    return RestoreResult(
        restored_at=fecha,
        safety_backup=safety,
        photos=fotos_restauradas,
        schema_revision=revision,
    )


def stage_restore(
    backup_path: Path,
    *,
    data_dir: Path | None = None,
) -> Path:
    pendiente = Path(data_dir or DATA_DIR) / "restore"
    pendiente.mkdir(parents=True, exist_ok=True)
    destino_zip = pendiente / "pendiente.zip"
    destino_marker = pendiente / "pendiente.json"
    origen = Path(backup_path).expanduser().resolve()
    if not origen.is_file():
        raise RestoreError(f"No existe el respaldo: {origen}")

    with tempfile.TemporaryDirectory(prefix=".icia_stage_") as temp_dir:
        staging = Path(temp_dir)
        database, _ = _extraer(origen, staging)
        _validar_base(database)

    shutil.copy2(origen, destino_zip)
    destino_marker.write_text(
        json.dumps(
            {
                "archivo": origen.name,
                "preparado_en": datetime.now().strftime(
                    "%Y-%m-%d %H:%M:%S"
                ),
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return destino_zip


def pending_restore(data_dir: Path | None = None) -> Path | None:
    pendiente = (
        Path(data_dir or DATA_DIR) / "restore" / "pendiente.zip"
    )
    return pendiente if pendiente.is_file() else None


def apply_pending_restore(
    *,
    data_dir: Path | None = None,
    database_path: Path = DATABASE_PATH,
    photos_dir: Path = PHOTOS_DIR,
    safety_dir: Path = BACKUP_DIR,
) -> RestoreResult | None:
    base = Path(data_dir or DATA_DIR)
    pendiente = pending_restore(base)
    if pendiente is None:
        return None
    try:
        return restore_full_backup(
            pendiente,
            database_path=database_path,
            photos_dir=photos_dir,
            safety_dir=safety_dir,
        )
    except Exception:
        fallido = pendiente.with_name(
            "fallido_"
            f"{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
        )
        pendiente.replace(fallido)
        raise
    finally:
        pendiente.unlink(missing_ok=True)
        (base / "restore" / "pendiente.json").unlink(missing_ok=True)
