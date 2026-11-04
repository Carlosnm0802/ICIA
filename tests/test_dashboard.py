from collections.abc import Iterator
from datetime import date, timedelta
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.core.database import build_engine, get_db
from app.core.security import requiere_sesion
from app.main import app
from app.models import Alumno, Asistencia, Grupo, Pago, Sesion, Sucursal
from app.services import cashier as cashier_service
from app.services import reports
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
def dashboard_app(
    tmp_path: Path,
) -> Iterator[tuple[TestClient, sessionmaker[Session]]]:
    database_path = tmp_path / "dashboard.db"
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


def _ref_ids(factory: sessionmaker[Session]) -> tuple[int, int]:
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


def _create_today_session(
    factory: sessionmaker[Session],
    grupo_id: int,
) -> int:
    with factory.begin() as session:
        sesion = Sesion(
            grupo_id=grupo_id,
            fecha=date.today().isoformat(),
            estado="programada",
        )
        session.add(sesion)
        session.flush()
        return sesion.id


def _student_ids(
    factory: sessionmaker[Session],
    cantidad: int,
) -> list[int]:
    with factory() as session:
        return list(
            session.scalars(
                select(Alumno.id).order_by(Alumno.id).limit(cantidad)
            )
        )


def test_dashboard_shows_empty_kpis(
    dashboard_app: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, _ = dashboard_app

    response = client.get("/dashboard")

    assert response.status_code == 200
    assert "ICIA" in response.text
    assert "Cobrado hoy" in response.text
    assert "Deudas" in response.text
    assert "Alumnos activos" in response.text
    assert "$0.00" in response.text
    assert "35" in response.text
    assert response.headers["cache-control"] == "no-store"


def test_dashboard_reflects_cobros_y_deuda(
    dashboard_app: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, factory = dashboard_app
    _, grupo_id = _ref_ids(factory)
    sesion_id = _create_today_session(factory, grupo_id)
    alumno_a, alumno_b, alumno_c = _student_ids(factory, 3)

    with factory() as session:
        cashier_service.cobrar_sesion(
            session,
            sesion_id=sesion_id,
            alumno_id=alumno_a,
            metodo="efectivo",
        )
    with factory() as session:
        cashier_service.cobrar_sesion(
            session,
            sesion_id=sesion_id,
            alumno_id=alumno_b,
            metodo="transferencia",
        )
    with factory() as session:
        cashier_service.registrar_deuda(
            session,
            sesion_id=sesion_id,
            alumno_id=alumno_c,
        )

    response = client.get("/dashboard")

    assert response.status_code == 200
    assert response.text.count("$280.00") >= 2
    assert "$140.00" in response.text
    assert "2 tickets vigentes" in response.text
    assert "1 asistencia sin pago" in response.text


def test_dashboard_ignora_pagos_cancelados_y_de_otra_semana(
    dashboard_app: tuple[TestClient, sessionmaker[Session]],
) -> None:
    _, factory = dashboard_app
    sucursal_id, grupo_id = _ref_ids(factory)
    alumno_id = _student_ids(factory, 1)[0]
    hoy = date(2026, 3, 11)
    inicio_semana = hoy - timedelta(days=hoy.weekday())

    with factory.begin() as session:
        pagos = (
            ("REF-9001", 10000, hoy.isoformat(), "vigente", None),
            ("REF-9002", 5000, inicio_semana.isoformat(), "vigente", None),
            (
                "REF-9003",
                2500,
                (inicio_semana + timedelta(days=1)).isoformat(),
                "vigente",
                None,
            ),
            (
                "REF-9004",
                7000,
                (inicio_semana - timedelta(days=1)).isoformat(),
                "vigente",
                None,
            ),
            (
                "REF-9005",
                9000,
                hoy.isoformat(),
                "cancelado",
                f"{hoy.isoformat()} 10:00:00",
            ),
        )
        for folio, monto, fecha, estado, cancelado_en in pagos:
            session.add(
                Pago(
                    folio=folio,
                    alumno_id=alumno_id,
                    sucursal_id=sucursal_id,
                    tipo="sesion",
                    monto_centavos=monto,
                    metodo="efectivo",
                    fecha=f"{fecha} 09:00:00",
                    estado=estado,
                    cancelado_en=cancelado_en,
                )
            )

        sesion = Sesion(
            grupo_id=grupo_id,
            fecha=hoy.isoformat(),
            estado="programada",
        )
        session.add(sesion)
        session.flush()
        session.add(
            Asistencia(
                sesion_id=sesion.id,
                alumno_id=alumno_id,
                estado="asistio",
                es_reposicion=0,
                pago_id=None,
                precio_aplicado_centavos=12500,
            )
        )

    with factory() as session:
        resumen = reports.resumen_dashboard(session, hoy=hoy)

    assert resumen.cobrado_hoy_centavos == 10000
    assert resumen.tickets_hoy == 1
    assert resumen.cobrado_semana_centavos == 17500
    assert resumen.tickets_semana == 3
    assert resumen.deudas_asistencias == 1
    assert resumen.deudas_centavos == 12500
    assert resumen.alumnos_activos == 35


def test_root_redirects_to_dashboard(
    dashboard_app: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, _ = dashboard_app

    response = client.get("/", follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"] == "/dashboard"
