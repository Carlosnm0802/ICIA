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
from app.models import Alumno, Grupo, Pago, Sesion, Sucursal
from app.services.seed import seed_database

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PASSWORD = "aceptacion-fase5-2026"
TOTAL_ESPERADO = 35 * 14000


def _config(database_path: Path) -> Config:
    config = Config(str(PROJECT_ROOT / "alembic.ini"))
    config.set_main_option("prepend_sys_path", str(PROJECT_ROOT))
    config.set_main_option(
        "sqlalchemy.url",
        f"sqlite:///{database_path.as_posix()}",
    )
    return config


def _build_factory(
    tmp_path: Path,
) -> tuple[sessionmaker[Session], Engine]:
    database_path = tmp_path / "aceptacion_fase5.db"
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
def aceptacion_fase5(
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


def _grupo_ref(factory: sessionmaker[Session]) -> tuple[int, int]:
    with factory() as session:
        sucursal = session.scalar(
            select(Sucursal).where(Sucursal.prefijo_folio == "REF")
        )
        assert sucursal is not None
        grupo = session.scalar(
            select(Grupo).where(Grupo.sucursal_id == sucursal.id)
        )
        assert grupo is not None
        return sucursal.id, grupo.id


def _sesion_de_hoy(
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


def _alumnos_ref(factory: sessionmaker[Session]) -> list[int]:
    with factory() as session:
        return list(
            session.scalars(select(Alumno.id).order_by(Alumno.id))
        )


def test_aceptacion_fase5_el_refugio_35_alumnos(
    aceptacion_fase5: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, factory = aceptacion_fase5
    sucursal_id, grupo_id = _grupo_ref(factory)
    alumnos = _alumnos_ref(factory)
    assert len(alumnos) == 35

    setup = client.post(
        "/setup",
        data={"password": PASSWORD, "password_confirm": PASSWORD},
        follow_redirects=False,
    )
    assert setup.status_code == 303

    sesion_id = _sesion_de_hoy(client, factory, grupo_id)
    inicio = time.perf_counter()
    folios = []
    for alumno_id in alumnos:
        response = client.post(
            "/pos/cobrar",
            json={
                "sesion_id": sesion_id,
                "alumno_id": alumno_id,
                "metodo": "efectivo",
            },
        )
        assert response.status_code == 200, response.text
        pago = response.json()["pago"]
        assert pago["monto_centavos"] == 14000
        folios.append(pago["folio"])
    transcurrido = time.perf_counter() - inicio

    assert folios == [f"REF-{numero:04d}" for numero in range(1, 36)]
    assert len(set(folios)) == 35
    assert transcurrido < 60

    with factory() as session:
        total = session.scalar(
            select(func.sum(Pago.monto_centavos)).where(
                Pago.estado == "vigente",
                Pago.sucursal_id == sucursal_id,
            )
        )
        assert total == TOTAL_ESPERADO

    roster = client.get(
        f"/pos?sucursal_id={sucursal_id}"
        f"&grupo_id={grupo_id}"
        f"&sesion_id={sesion_id}"
    )
    assert roster.status_code == 200
    assert "35 pagados" in roster.text

    ultimo = client.get(f"/pos/tickets/folio?folio={folios[-1]}")
    assert ultimo.status_code == 200
    assert folios[-1] in ultimo.text
    assert "$140.00" in ultimo.text
    assert "ICIA" in ultimo.text
