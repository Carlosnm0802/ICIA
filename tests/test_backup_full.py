import sqlite3
import zipfile
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy.orm import sessionmaker

from app.core.database import build_engine
from app.services import backup_service, restore_service

PROJECT_ROOT = Path(__file__).resolve().parents[1]
NOW = datetime(2026, 11, 7, 12, 0, 0)


def _config(database_path: Path) -> Config:
    config = Config(str(PROJECT_ROOT / "alembic.ini"))
    config.set_main_option("prepend_sys_path", str(PROJECT_ROOT))
    config.set_main_option(
        "sqlalchemy.url",
        f"sqlite:///{database_path.as_posix()}",
    )
    return config


def _crear_base(path: Path) -> Path:
    command.upgrade(_config(path), "head")
    return path


def _insertar_sucursal(path: Path, nombre: str, prefijo: str) -> None:
    connection = sqlite3.connect(path)
    try:
        connection.execute(
            "INSERT INTO sucursales (nombre, prefijo_folio) VALUES (?, ?)",
            (nombre, prefijo),
        )
        connection.commit()
    finally:
        connection.close()


def _sucursales(path: Path) -> list[str]:
    connection = sqlite3.connect(path)
    try:
        return [
            row[0]
            for row in connection.execute(
                "SELECT nombre FROM sucursales ORDER BY id"
            )
        ]
    finally:
        connection.close()


def test_full_backup_incluye_base_fotos_y_manifiesto(
    tmp_path: Path,
) -> None:
    database_path = _crear_base(tmp_path / "source.db")
    _insertar_sucursal(database_path, "El Refugio", "REF")
    photos = tmp_path / "photos"
    (photos / "sub").mkdir(parents=True)
    (photos / "alumno.jpg").write_bytes(b"foto")
    (photos / "sub" / "tutor.png").write_bytes(b"tutor")

    result = backup_service.create_full_backup(
        tmp_path / "backups",
        source_path=database_path,
        photos_dir=photos,
        now=NOW,
    )

    assert result.destination_path.name == "icia_completo_20261107_120000.zip"
    assert result.destination_path.exists()
    assert result.photos == 2
    assert result.schema_revision
    assert result.database_size_bytes > 0

    with zipfile.ZipFile(result.destination_path) as archivo:
        assert archivo.namelist() == [
            "icia.db",
            "manifest.json",
            "photos/alumno.jpg",
            "photos/sub/tutor.png",
        ]
        manifest = archivo.read("manifest.json").decode("utf-8")
        assert '"app": "ICIA"' in manifest
        assert '"fotos": 2' in manifest


def test_backup_completo_registra_y_guarda_ruta(tmp_path: Path) -> None:
    database_path = _crear_base(tmp_path / "source.db")
    photos = tmp_path / "photos"
    photos.mkdir()
    engine = build_engine(database_path)
    session = sessionmaker(bind=engine, expire_on_commit=False)()

    try:
        result = backup_service.backup_completo_database(
            session,
            tmp_path / "backups",
            source_path=database_path,
            photos_dir=photos,
            now=NOW,
        )
        session.commit()

        assert backup_service.ultimo_respaldo(session) == NOW
        assert backup_service.recordatorio_respaldo(
            session, ahora=NOW + timedelta(days=3)
        ) is None
        assert "8 días" in (
            backup_service.recordatorio_respaldo(
                session, ahora=NOW + timedelta(days=8)
            )
            or ""
        )

        destino = tmp_path / "usb"
        backup_service.guardar_ruta_respaldo(session, str(destino))
        session.commit()
        assert backup_service.ruta_respaldo(session) == destino

        backup_service.guardar_ruta_respaldo(session, "")
        session.commit()
        assert backup_service.ruta_respaldo(session) == backup_service.BACKUP_DIR
        assert result.destination_path.exists()
    finally:
        session.close()
        engine.dispose()


def test_restore_reemplaza_base_y_fotos_y_crea_respaldo_seguridad(
    tmp_path: Path,
) -> None:
    database_path = _crear_base(tmp_path / "source.db")
    _insertar_sucursal(database_path, "Original", "ORI")
    photos = tmp_path / "photos"
    photos.mkdir()
    (photos / "original.jpg").write_bytes(b"original")

    backup = backup_service.create_full_backup(
        tmp_path / "backups",
        source_path=database_path,
        photos_dir=photos,
        now=NOW,
    )

    _insertar_sucursal(database_path, "Cambio", "CAM")
    (photos / "original.jpg").unlink()
    (photos / "cambio.jpg").write_bytes(b"cambio")

    result = restore_service.restore_full_backup(
        backup.destination_path,
        database_path=database_path,
        photos_dir=photos,
        safety_dir=tmp_path / "safety",
        now=NOW + timedelta(hours=1),
    )

    assert _sucursales(database_path) == ["Original"]
    assert (photos / "original.jpg").read_bytes() == b"original"
    assert not (photos / "cambio.jpg").exists()
    assert result.photos == 1
    assert result.safety_backup is not None
    assert result.safety_backup.exists()
    with zipfile.ZipFile(result.safety_backup) as archivo:
        assert "icia.db" in archivo.namelist()


def test_restore_rechaza_rutas_peligrosas(tmp_path: Path) -> None:
    backup = tmp_path / "malicioso.zip"
    with zipfile.ZipFile(backup, "w") as archivo:
        archivo.writestr("../fuera.txt", b"x")
        archivo.writestr("icia.db", b"x")

    with pytest.raises(restore_service.RestoreError, match="rutas"):
        restore_service.restore_full_backup(
            backup,
            database_path=tmp_path / "destino.db",
            photos_dir=tmp_path / "photos",
        )


def test_restore_rechaza_base_sin_esquema(tmp_path: Path) -> None:
    backup = tmp_path / "invalido.zip"
    with zipfile.ZipFile(backup, "w") as archivo:
        archivo.writestr("icia.db", b"no es sqlite")

    with pytest.raises(restore_service.RestoreError):
        restore_service.stage_restore(backup, data_dir=tmp_path / "data")


def test_stage_y_apply_pending_restore(tmp_path: Path) -> None:
    database_path = _crear_base(tmp_path / "source.db")
    _insertar_sucursal(database_path, "Original", "ORI")
    photos = tmp_path / "photos"
    photos.mkdir()
    (photos / "original.jpg").write_bytes(b"original")
    backup = backup_service.create_full_backup(
        tmp_path / "backups",
        source_path=database_path,
        photos_dir=photos,
        now=NOW,
    )
    data_dir = tmp_path / "data"

    pendiente = restore_service.stage_restore(
        backup.destination_path,
        data_dir=data_dir,
    )
    assert pendiente.exists()
    assert restore_service.pending_restore(data_dir) == pendiente

    _insertar_sucursal(database_path, "Cambio", "CAM")
    result = restore_service.apply_pending_restore(
        data_dir=data_dir,
        database_path=database_path,
        photos_dir=photos,
        safety_dir=tmp_path / "safety",
    )

    assert result is not None
    assert _sucursales(database_path) == ["Original"]
    assert restore_service.pending_restore(data_dir) is None
