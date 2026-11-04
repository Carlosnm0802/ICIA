from collections.abc import Iterator
from datetime import date
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from app.core.database import build_engine, get_db
from app.core.security import requiere_sesion
from app.main import app
from app.models import Alumno, Asistencia, Grupo, Pago, Sesion, Sucursal
from app.services import cashier as cashier_service
from app.services.seed import seed_database

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
def debts_app(
    tmp_path: Path,
) -> Iterator[tuple[TestClient, sessionmaker[Session]]]:
    database_path = tmp_path / "debts.db"
    command.upgrade(_config(database_path), "head")
    engine = build_engine(database_path)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory.begin() as session:
        seed_database(session)

    def override_get_db() -> Iterator[Session]:
        with factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[requiere_sesion] = lambda: None
    try:
        with TestClient(app) as client:
            yield client, factory
    finally:
        app.dependency_overrides.clear()
        engine.dispose()


def _ref_ids(factory: sessionmaker[Session]) -> tuple[int, int, int]:
    with factory() as session:
        sucursal = session.scalar(
            select(Sucursal).where(Sucursal.prefijo_folio == "REF")
        )
        assert sucursal is not None
        grupo = session.scalar(
            select(Grupo).where(Grupo.sucursal_id == sucursal.id)
        )
        assert grupo is not None
        alumno_id = session.scalar(
            select(Alumno.id).order_by(Alumno.id).limit(1)
        )
        assert alumno_id is not None
        return sucursal.id, grupo.id, alumno_id


def _create_debt(
    factory: sessionmaker[Session],
    grupo_id: int,
    alumno_id: int,
) -> int:
    with factory.begin() as session:
        sesion = Sesion(
            grupo_id=grupo_id,
            fecha=date.today().isoformat(),
            estado="programada",
        )
        session.add(sesion)
        session.flush()
        sesion_id = sesion.id

    with factory() as session:
        resultado = cashier_service.registrar_deuda(
            session,
            sesion_id=sesion_id,
            alumno_id=alumno_id,
        )
    return resultado.asistencia_id


def _pago_id(location: str) -> int:
    parametros = parse_qs(urlsplit(location).query)
    return int(parametros["cobrado"][0])


def test_deudas_lista_pendientes(
    debts_app: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, factory = debts_app
    _, grupo_id, alumno_id = _ref_ids(factory)
    _create_debt(factory, grupo_id, alumno_id)

    response = client.get("/deudas")

    assert response.status_code == 200
    assert "Deudas pendientes" in response.text
    assert "Alumno 01" in response.text
    assert "$140.00" in response.text
    assert "1 asistencia sin pago" in response.text
    assert "Efectivo" in response.text
    assert "Transferencia" in response.text
    assert response.headers["cache-control"] == "no-store"


def test_deudas_muestra_estado_vacio(
    debts_app: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, _ = debts_app

    response = client.get("/deudas")

    assert response.status_code == 200
    assert "Sin deudas pendientes" in response.text
    assert "$0.00" in response.text


def test_cobrar_deuda_genera_ticket_y_actualiza_totales(
    debts_app: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, factory = debts_app
    _, grupo_id, alumno_id = _ref_ids(factory)
    asistencia_id = _create_debt(factory, grupo_id, alumno_id)

    response = client.post(
        f"/deudas/{asistencia_id}/cobrar",
        data={"metodo": "transferencia"},
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"].startswith("/deudas?cobrado=")
    pago_id = _pago_id(response.headers["location"])

    pagina = client.get(response.headers["location"])
    assert pagina.status_code == 200
    assert "Deuda cobrada" in pagina.text
    assert "REF-0001" in pagina.text
    assert "Alumno 01" in pagina.text
    assert f"/pos/tickets/{pago_id}?auto=1" in pagina.text
    assert "Sin deudas pendientes" in pagina.text

    ticket = client.get(f"/pos/tickets/{pago_id}")
    assert ticket.status_code == 200
    assert "REF-0001" in ticket.text
    assert "Alumno 01" in ticket.text
    assert "$140.00" in ticket.text
    assert "Transferencia" in ticket.text

    dashboard = client.get("/dashboard")
    assert "$140.00" in dashboard.text
    assert "0 asistencias sin pago" in dashboard.text

    recaudacion = client.get("/dashboard/recaudacion").json()
    assert recaudacion["total_centavos"] == 14000
    ref = next(
        sucursal
        for sucursal in recaudacion["sucursales"]
        if sucursal["prefijo_folio"] == "REF"
    )
    assert ref["total_centavos"] == 14000
    assert ref["tickets"] == 1

    with factory() as session:
        pago = session.get(Pago, pago_id)
        assert pago is not None
        assert pago.estado == "vigente"
        assert pago.metodo == "transferencia"
        asistencia = session.get(Asistencia, asistencia_id)
        assert asistencia is not None
        assert asistencia.pago_id == pago_id


def test_cobrar_deuda_duplicada_no_genera_otro_pago(
    debts_app: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, factory = debts_app
    _, grupo_id, alumno_id = _ref_ids(factory)
    asistencia_id = _create_debt(factory, grupo_id, alumno_id)

    primera = client.post(
        f"/deudas/{asistencia_id}/cobrar",
        data={"metodo": "efectivo"},
        follow_redirects=False,
    )
    assert primera.status_code == 303

    segunda = client.post(
        f"/deudas/{asistencia_id}/cobrar",
        data={"metodo": "efectivo"},
        follow_redirects=False,
    )

    assert segunda.status_code == 303
    assert segunda.headers["location"].startswith("/deudas?error=")
    pagina = client.get(segunda.headers["location"])
    assert "ya fue cobrada" in pagina.text

    with factory() as session:
        assert (
            session.scalar(select(func.count()).select_from(Pago)) == 1
        )
