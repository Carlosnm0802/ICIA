from collections.abc import Iterator
from pathlib import Path
from urllib.parse import unquote

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.core.database import build_engine, get_db
from app.core.security import requiere_sesion
from app.main import app
from app.models import Configuracion
from app.services import backup_service, restore_service

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _config(database_path: Path) -> Config:
    config = Config(str(PROJECT_ROOT / "alembic.ini"))
    config.set_main_option("prepend_sys_path", str(PROJECT_ROOT))
    config.set_main_option(
        "sqlalchemy.url",
        f"sqlite:///{database_path.as_posix()}",
    )
    return config


@pytest.fixture
def settings_app(
    tmp_path: Path,
) -> Iterator[tuple[TestClient, sessionmaker[Session], Path]]:
    database_path = tmp_path / "settings.db"
    command.upgrade(_config(database_path), "head")
    engine = build_engine(database_path)
    factory = sessionmaker(bind=engine, expire_on_commit=False)

    def override_get_db() -> Iterator[Session]:
        with factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[requiere_sesion] = lambda: None
    try:
        with TestClient(app) as client:
            yield client, factory, database_path
    finally:
        app.dependency_overrides.clear()
        engine.dispose()


def _valor(factory: sessionmaker[Session], clave: str) -> str | None:
    with factory() as session:
        registro = session.get(Configuracion, clave)
        return registro.valor if registro is not None else None


def test_configuracion_muestra_estado(
    settings_app: tuple[TestClient, sessionmaker[Session], Path],
) -> None:
    client, _factory, _database = settings_app

    response = client.get("/configuracion")

    assert response.status_code == 200
    assert "Configuración" in response.text
    assert "Respaldar ahora" in response.text
    assert "Imprimir ticket de prueba" in response.text


def test_configuracion_guarda_ancho_y_rechaza_invalido(
    settings_app: tuple[TestClient, sessionmaker[Session], Path],
) -> None:
    client, factory, _database = settings_app

    guardado = client.post(
        "/configuracion/impresion",
        data={"ancho_mm": "58"},
        follow_redirects=False,
    )
    assert guardado.status_code == 303
    assert guardado.headers["location"] == "/configuracion?guardado=1"
    assert _valor(factory, "ticket_ancho_mm") == "58"

    invalido = client.post(
        "/configuracion/impresion",
        data={"ancho_mm": "60"},
        follow_redirects=False,
    )
    assert invalido.status_code == 303
    assert "error=" in invalido.headers["location"]
    assert _valor(factory, "ticket_ancho_mm") == "58"


def test_configuracion_guarda_y_limpia_ruta_de_respaldo(
    settings_app: tuple[TestClient, sessionmaker[Session], Path],
    tmp_path: Path,
) -> None:
    client, factory, _database = settings_app
    destino = tmp_path / "usb"

    guardado = client.post(
        "/configuracion/respaldo/ruta",
        data={"ruta_respaldo": str(destino)},
        follow_redirects=False,
    )
    assert guardado.status_code == 303
    assert _valor(factory, "ruta_respaldo") == str(destino)

    limpiado = client.post(
        "/configuracion/respaldo/ruta",
        data={"ruta_respaldo": ""},
        follow_redirects=False,
    )
    assert limpiado.status_code == 303
    assert _valor(factory, "ruta_respaldo") is None


def test_configuracion_crea_respaldo_con_servicio(
    settings_app: tuple[TestClient, sessionmaker[Session], Path],
    tmp_path: Path,
    monkeypatch,
) -> None:
    client, _factory, _database = settings_app
    destino = tmp_path / "backups" / "icia_completo_prueba.zip"

    class _Resultado:
        destination_path = destino

    monkeypatch.setattr(
        backup_service,
        "backup_completo_database",
        lambda _session, _ruta: _Resultado(),
    )

    response = client.post("/configuracion/respaldo", follow_redirects=False)

    assert response.status_code == 303
    assert "respaldo=icia_completo_prueba.zip" in response.headers["location"]


def test_configuracion_prepara_restauracion_zip(
    settings_app: tuple[TestClient, sessionmaker[Session], Path],
    monkeypatch,
) -> None:
    client, _factory, _database = settings_app
    capturado = []

    def _stage(backup_path: Path, **_kwargs) -> Path:
        capturado.append(backup_path)
        return backup_path

    monkeypatch.setattr(restore_service, "stage_restore", _stage)

    response = client.post(
        "/configuracion/restaurar",
        files={"archivo": ("respaldo.zip", b"contenido", "application/zip")},
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert "restauracion=1" in response.headers["location"]
    assert len(capturado) == 1
    assert capturado[0].suffix == ".zip"
    assert not capturado[0].exists()

    invalido = client.post(
        "/configuracion/restaurar",
        files={"archivo": ("respaldo.db", b"contenido", "application/octet")},
        follow_redirects=False,
    )
    assert invalido.status_code == 303
    assert "error=" in invalido.headers["location"]
    assert "ZIP" in unquote(invalido.headers["location"])


def test_ticket_prueba_usa_ancho_guardado_y_no_muestra_descarga(
    settings_app: tuple[TestClient, sessionmaker[Session], Path],
) -> None:
    client, _factory, _database = settings_app
    client.post(
        "/configuracion/impresion",
        data={"ancho_mm": "58"},
        follow_redirects=False,
    )

    response = client.get("/configuracion/ticket-prueba")

    assert response.status_code == 200
    assert "PRUEBA" in response.text
    assert "ticket--58" in response.text
    assert "ticket-auto-print" in response.text
    assert "Descargar" not in response.text
