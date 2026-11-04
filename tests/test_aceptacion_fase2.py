import time
from collections.abc import Iterator
from datetime import date
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session, sessionmaker

from app.core.database import build_engine, get_db
from app.core.security import requiere_sesion
from app.main import app
from app.models import Alumno, Asistencia, Grupo, Pago, Sesion, Sucursal
from app.services.seed import seed_database

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PASSWORD = "aceptacion-icia-2026"


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
    database_path = tmp_path / "aceptacion_fase2.db"
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
def aceptacion_app(
    tmp_path: Path,
) -> Iterator[tuple[TestClient, sessionmaker[Session]]]:
    factory, engine = _build_factory(tmp_path)

    def override_get_db() -> Iterator[Session]:
        with factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides.pop(requiere_sesion, None)
    try:
        with TestClient(app) as client:
            yield client, factory
    finally:
        app.dependency_overrides.clear()
        engine.dispose()


def _ref_ids(
    factory: sessionmaker[Session],
) -> tuple[int, int, list[int]]:
    with factory() as session:
        sucursal = session.scalar(
            select(Sucursal).where(Sucursal.prefijo_folio == "REF")
        )
        assert sucursal is not None
        grupo = session.scalar(
            select(Grupo).where(Grupo.sucursal_id == sucursal.id)
        )
        assert grupo is not None
        alumnos = list(
            session.scalars(
                select(Alumno.id).order_by(Alumno.id).limit(15)
            )
        )
        return sucursal.id, grupo.id, alumnos


def _abrir_sesion(
    client: TestClient,
    factory: sessionmaker[Session],
    grupo_id: int,
) -> int:
    response = client.post(
        f"/pos/sesiones?grupo_id={grupo_id}",
        follow_redirects=False,
    )
    assert response.status_code == 303

    with factory() as session:
        sesion = session.scalar(
            select(Sesion).where(
                Sesion.grupo_id == grupo_id,
                Sesion.fecha == date.today().isoformat(),
            )
        )
        assert sesion is not None
        return sesion.id


def _cobrar(
    client: TestClient,
    sesion_id: int,
    alumno_id: int,
    metodo: str = "efectivo",
) -> dict:
    response = client.post(
        "/pos/cobrar",
        json={
            "sesion_id": sesion_id,
            "alumno_id": alumno_id,
            "metodo": metodo,
        },
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["ok"] is True
    return data


def test_aceptacion_fase2_completa(
    aceptacion_app: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, factory = aceptacion_app
    sucursal_id, grupo_id, alumnos = _ref_ids(factory)

    login = client.get("/login")
    assert login.status_code == 200
    assert "ICIA" in login.text
    assert "Crea la contraseña de acceso" in login.text

    setup = client.post(
        "/setup",
        data={"password": PASSWORD, "password_confirm": PASSWORD},
        follow_redirects=False,
    )
    assert setup.status_code == 303
    assert setup.headers["location"] == "/dashboard"

    sesion_id = _abrir_sesion(client, factory, grupo_id)

    inicio = time.perf_counter()
    cobros = [
        _cobrar(client, sesion_id, alumno_id)
        for alumno_id in alumnos[:10]
    ]
    transcurrido = time.perf_counter() - inicio

    assert transcurrido < 30
    folios = [cobro["pago"]["folio"] for cobro in cobros]
    assert folios == [f"REF-{numero:04d}" for numero in range(1, 11)]
    assert len(set(folios)) == 10
    for cobro, alumno_id in zip(cobros, alumnos[:10], strict=True):
        pago = cobro["pago"]
        assert pago["alumno_id"] == alumno_id
        assert pago["monto_centavos"] == 14000
        assert pago["monto"] == "$140.00"

    for cobro in cobros:
        pago = cobro["pago"]
        ticket = client.get(f"/pos/tickets/{pago['id']}")
        assert ticket.status_code == 200
        assert "ICIA" in ticket.text
        assert pago["folio"] in ticket.text
        assert pago["alumno"] in ticket.text
        assert "$140.00" in ticket.text
        assert "Vigente" in ticket.text

    descarga = client.get(
        f"/pos/tickets/{cobros[0]['pago']['id']}",
        params={"descargar": "1"},
    )
    assert descarga.status_code == 200
    assert descarga.headers["content-disposition"] == (
        'attachment; filename="ICIA-REF-0001.html"'
    )
    assert ".ticket__brand" in descarga.text
    assert "/static/css/ticket.css" not in descarga.text

    descarga_folio = client.get(
        "/pos/tickets/folio",
        params={"folio": folios[0], "descargar": "1"},
    )
    assert descarga_folio.status_code == 200
    assert descarga_folio.headers["content-disposition"] == (
        'attachment; filename="ICIA-REF-0001.html"'
    )

    with factory() as session:
        total = session.scalar(
            select(func.sum(Pago.monto_centavos)).where(
                Pago.estado == "vigente"
            )
        )
        assert total == 140000

    alumno_deuda = alumnos[10]
    deuda_response = client.post(
        "/pos/asistio-sin-pagar",
        json={"sesion_id": sesion_id, "alumno_id": alumno_deuda},
    )
    assert deuda_response.status_code == 200
    deuda = deuda_response.json()["deuda"]
    assert deuda["monto_centavos"] == 14000
    with factory() as session:
        asistencia_deuda = session.get(Asistencia, deuda["asistencia_id"])
        assert asistencia_deuda is not None
        assert asistencia_deuda.pago_id is None

    roster = client.get(
        f"/pos?sucursal_id={sucursal_id}"
        f"&grupo_id={grupo_id}"
        f"&sesion_id={sesion_id}"
    )
    assert roster.status_code == 200
    assert "10 pagados" in roster.text
    assert "1 deudas" in roster.text

    primer_pago = cobros[0]["pago"]
    deshacer = client.post(
        "/pos/deshacer-asistencia",
        json={
            "sesion_id": sesion_id,
            "alumno_id": primer_pago["alumno_id"],
        },
    )
    assert deshacer.status_code == 200
    deshecho = deshacer.json()["deshecho"]
    assert deshecho["tipo"] == "pago"
    assert deshecho["folio"] == primer_pago["folio"]

    with factory() as session:
        pago_cancelado = session.get(Pago, primer_pago["id"])
        assert pago_cancelado is not None
        assert pago_cancelado.folio == primer_pago["folio"]
        assert pago_cancelado.estado == "cancelado"
        assert pago_cancelado.cancelado_en is not None
        asistencia_pago = session.scalar(
            select(Asistencia).where(
                Asistencia.pago_id == primer_pago["id"]
            )
        )
        assert asistencia_pago is None
        total_tras_anular = session.scalar(
            select(func.sum(Pago.monto_centavos)).where(
                Pago.estado == "vigente"
            )
        )
        assert total_tras_anular == 126000

    ticket_cancelado = client.get(
        "/pos/tickets/folio",
        params={"folio": primer_pago["folio"]},
    )
    assert ticket_cancelado.status_code == 200
    assert "Cancelado" in ticket_cancelado.text

    nuevo_cobro = _cobrar(client, sesion_id, alumnos[11])
    assert nuevo_cobro["pago"]["folio"] == "REF-0011"
    assert len(set(folios) | {nuevo_cobro["pago"]["folio"]}) == 11

    deshacer_deuda = client.post(
        "/pos/deshacer-asistencia",
        json={"sesion_id": sesion_id, "alumno_id": alumno_deuda},
    )
    assert deshacer_deuda.status_code == 200
    deuda_deshecha = deshacer_deuda.json()["deshecho"]
    assert deuda_deshecha["tipo"] == "deuda"
    assert deuda_deshecha["folio"] is None
    with factory() as session:
        assert session.get(Asistencia, deuda["asistencia_id"]) is None
