from collections.abc import Iterator
from datetime import date
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session, sessionmaker

from app.core import config
from app.core.database import build_engine, get_db
from app.core.format import formato_fecha_hora
from app.main import app
from app.models import Alumno, Configuracion, Grupo, Pago, Sesion, Sucursal
from app.services.cashier import cobrar_sesion
from app.services.seed import seed_database

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _config(database_path: Path) -> Config:
    configuracion = Config(str(PROJECT_ROOT / "alembic.ini"))
    configuracion.set_main_option("prepend_sys_path", str(PROJECT_ROOT))
    configuracion.set_main_option(
        "sqlalchemy.url",
        f"sqlite:///{database_path.as_posix()}",
    )
    return configuracion


def _build_factory(
    tmp_path: Path,
) -> tuple[sessionmaker[Session], Engine]:
    database_path = tmp_path / "tickets.db"
    command.upgrade(_config(database_path), "head")
    engine = build_engine(database_path)
    factory = sessionmaker(
        bind=engine,
        autoflush=False,
        expire_on_commit=False,
    )
    with factory.begin() as session:
        seed_database(session)
    return factory, engine


@pytest.fixture
def ticket_app(
    tmp_path: Path,
) -> Iterator[tuple[TestClient, sessionmaker[Session]]]:
    factory, engine = _build_factory(tmp_path)

    def override_get_db() -> Iterator[Session]:
        with factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app) as client:
            yield client, factory
    finally:
        app.dependency_overrides.clear()
        engine.dispose()


def _ref_ids(
    factory: sessionmaker[Session],
) -> tuple[int, int, int]:
    with factory() as session:
        sucursal = session.scalar(
            select(Sucursal).where(Sucursal.prefijo_folio == "REF")
        )
        assert sucursal is not None
        grupo = session.scalar(
            select(Grupo).where(Grupo.sucursal_id == sucursal.id)
        )
        assert grupo is not None
        alumno = session.scalar(select(Alumno).order_by(Alumno.id))
        assert alumno is not None
        return sucursal.id, grupo.id, alumno.id


def _create_session(
    factory: sessionmaker[Session],
    grupo_id: int,
    estado: str = "programada",
) -> int:
    with factory.begin() as session:
        sesion = Sesion(
            grupo_id=grupo_id,
            fecha=date.today().isoformat(),
            estado=estado,
        )
        session.add(sesion)
        session.flush()
        return sesion.id


def _cobrar(
    factory: sessionmaker[Session],
    grupo_id: int,
    alumno_id: int,
    metodo: str = "efectivo",
):
    sesion_id = _create_session(factory, grupo_id)
    with factory() as session:
        return cobrar_sesion(
            session,
            sesion_id=sesion_id,
            alumno_id=alumno_id,
            metodo=metodo,
        )


def test_ticket_muestra_datos_completos(
    ticket_app: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, factory = ticket_app
    _, grupo_id, alumno_id = _ref_ids(factory)
    resultado = _cobrar(factory, grupo_id, alumno_id)

    response = client.get(f"/pos/tickets/{resultado.pago_id}")

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    text = response.text
    assert "ICIA" in text
    assert "El Refugio" in text
    assert resultado.folio in text
    assert resultado.alumno in text
    assert "Jueves 3-5 PM" in text
    assert "Inglés + Robótica" in text
    assert date.today().strftime("%d/%m/%Y") in text
    assert "$140.00" in text
    assert "Efectivo" in text
    assert "Vigente" in text
    assert f"ticket--{config.TICKET_ANCHO_MM}" in text
    assert "@page" in text
    assert f"size: {config.TICKET_ANCHO_MM}mm auto" in text


def test_ticket_auto_impresion_solo_con_parametro(
    ticket_app: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, factory = ticket_app
    _, grupo_id, alumno_id = _ref_ids(factory)
    resultado = _cobrar(factory, grupo_id, alumno_id)

    automatico = client.get(f"/pos/tickets/{resultado.pago_id}?auto=1")
    manual = client.get(f"/pos/tickets/{resultado.pago_id}")

    assert automatico.status_code == 200
    assert 'id="ticket-auto-print"' in automatico.text
    assert 'id="ticket-auto-print"' not in manual.text


def test_ticket_inexistente_devuelve_404(
    ticket_app: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, _ = ticket_app

    response = client.get("/pos/tickets/999999")

    assert response.status_code == 404
    assert response.json()["detail"] == "Ticket no encontrado."


def test_ticket_respeta_ancho_configurado(
    ticket_app: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, factory = ticket_app
    _, grupo_id, alumno_id = _ref_ids(factory)
    resultado = _cobrar(factory, grupo_id, alumno_id)

    with factory.begin() as session:
        session.add(Configuracion(clave="ticket_ancho_mm", valor="58"))

    response = client.get(f"/pos/tickets/{resultado.pago_id}")

    assert response.status_code == 200
    assert "ticket--58" in response.text
    assert "size: 58mm auto" in response.text

    with factory.begin() as session:
        registro = session.get(Configuracion, "ticket_ancho_mm")
        assert registro is not None
        registro.valor = "80"

    response = client.get(f"/pos/tickets/{resultado.pago_id}")

    assert response.status_code == 200
    assert "ticket--80" in response.text
    assert "size: 80mm auto" in response.text


def test_ticket_ancho_invalido_usa_default(
    ticket_app: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, factory = ticket_app
    _, grupo_id, alumno_id = _ref_ids(factory)
    resultado = _cobrar(factory, grupo_id, alumno_id)

    with factory.begin() as session:
        session.add(Configuracion(clave="ticket_ancho_mm", valor="70"))

    response = client.get(f"/pos/tickets/{resultado.pago_id}")

    assert response.status_code == 200
    assert f"ticket--{config.TICKET_ANCHO_MM}" in response.text


def test_ticket_muestra_estado_cancelado(
    ticket_app: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, factory = ticket_app
    _, grupo_id, alumno_id = _ref_ids(factory)
    resultado = _cobrar(factory, grupo_id, alumno_id)

    with factory.begin() as session:
        pago = session.get(Pago, resultado.pago_id)
        assert pago is not None
        pago.estado = "cancelado"
        pago.cancelado_en = "2026-10-29 12:00:00"

    response = client.get(f"/pos/tickets/{resultado.pago_id}")

    assert response.status_code == 200
    assert "Cancelado" in response.text


def test_ticket_css_se_sirve(
    ticket_app: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, _ = ticket_app

    response = client.get("/static/css/ticket.css")

    assert response.status_code == 200
    assert "@media print" in response.text
    assert ".ticket--58" in response.text
    assert ".ticket--80" in response.text
    assert ".ticket-actions" in response.text


def test_pos_incluye_iframe_de_ticket(
    ticket_app: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, factory = ticket_app
    sucursal_id, grupo_id, _ = _ref_ids(factory)
    sesion_id = _create_session(factory, grupo_id)

    response = client.get(
        f"/pos?sucursal_id={sucursal_id}"
        f"&grupo_id={grupo_id}"
        f"&sesion_id={sesion_id}"
    )

    assert response.status_code == 200
    assert 'id="ticket-frame"' in response.text
    assert 'class="ticket-frame"' in response.text


def test_pos_cancelado_no_incluye_iframe_de_ticket(
    ticket_app: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, factory = ticket_app
    sucursal_id, grupo_id, _ = _ref_ids(factory)
    sesion_id = _create_session(factory, grupo_id, estado="cancelada")

    response = client.get(
        f"/pos?sucursal_id={sucursal_id}"
        f"&grupo_id={grupo_id}"
        f"&sesion_id={sesion_id}"
    )

    assert response.status_code == 200
    assert 'id="ticket-frame"' not in response.text


def test_pos_js_dispara_ticket(
    ticket_app: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, _ = ticket_app

    response = client.get("/static/js/pos.js")

    assert response.status_code == 200
    assert "ticketFrame" in response.text
    assert "/pos/tickets/" in response.text
    assert "auto=1" in response.text


def test_formato_fecha_hora() -> None:
    assert formato_fecha_hora("2026-10-29 15:04:05") == "29/10/2026 15:04"
    assert formato_fecha_hora("sin fecha") == "sin fecha"
