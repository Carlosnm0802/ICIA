from collections.abc import Iterator
from datetime import date, timedelta
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import Engine, func, select, text
from sqlalchemy.orm import Session, sessionmaker

from app.core.database import build_engine, get_db
from app.core.security import requiere_sesion
from app.main import app
from app.models import Alumno, Asistencia, Grupo, Pago, Sesion, Sucursal
from app.services.seed import seed_database

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PASSWORD = "aceptacion-fase3-2026"


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
    database_path = tmp_path / "aceptacion_fase3.db"
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
def aceptacion_fase3_app(
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


def _preparar_entorno(
    factory: sessionmaker[Session],
) -> tuple[int, int, list[int], int, int]:
    with factory.begin() as session:
        sucursal_ref = session.scalar(
            select(Sucursal).where(Sucursal.prefijo_folio == "REF")
        )
        assert sucursal_ref is not None
        grupo_ref = session.scalar(
            select(Grupo).where(Grupo.sucursal_id == sucursal_ref.id)
        )
        assert grupo_ref is not None

        sucursal_tot = session.scalar(
            select(Sucursal).where(Sucursal.prefijo_folio == "TOT")
        )
        assert sucursal_tot is not None
        grupo_tot = Grupo(
            sucursal_id=sucursal_tot.id,
            nombre="Robótica Sábados",
            dias_semana="Sábado",
            hora_inicio="09:00",
            hora_fin="11:00",
            precio_centavos=15000,
            activo=1,
        )
        session.add(grupo_tot)
        session.flush()

        sesion_tot = Sesion(
            grupo_id=grupo_tot.id,
            fecha=(date.today() + timedelta(days=2)).isoformat(),
            estado="programada",
        )
        session.add(sesion_tot)
        session.flush()

        alumnos = list(
            session.scalars(
                select(Alumno.id).order_by(Alumno.id).limit(4)
            )
        )
        return (
            sucursal_ref.id,
            grupo_ref.id,
            alumnos,
            grupo_tot.id,
            sesion_tot.id,
        )


def test_criterio_aceptacion_fase3_completo(
    aceptacion_fase3_app: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, factory = aceptacion_fase3_app
    (
        sucursal_ref_id,
        grupo_ref_id,
        alumnos,
        grupo_tot_id,
        sesion_tot_id,
    ) = _preparar_entorno(factory)

    setup = client.post(
        "/setup",
        data={"password": PASSWORD, "password_confirm": PASSWORD},
        follow_redirects=False,
    )
    assert setup.status_code == 303

    abrir = client.post(
        f"/pos/sesiones?grupo_id={grupo_ref_id}",
        follow_redirects=False,
    )
    assert abrir.status_code == 303
    with factory() as session:
        sesion_hoy = session.scalar(
            select(Sesion).where(
                Sesion.grupo_id == grupo_ref_id,
                Sesion.fecha == date.today().isoformat(),
            )
        )
        assert sesion_hoy is not None
        sesion_hoy_id = sesion_hoy.id

    c1 = client.post(
        "/pos/cobrar",
        json={
            "sesion_id": sesion_hoy_id,
            "alumno_id": alumnos[0],
            "metodo": "efectivo",
        },
    )
    assert c1.status_code == 200

    c2 = client.post(
        "/pos/cobrar",
        json={
            "sesion_id": sesion_hoy_id,
            "alumno_id": alumnos[1],
            "metodo": "transferencia",
        },
    )
    assert c2.status_code == 200

    falta_resp = client.post(
        "/pos/marcar-falta",
        json={"sesion_id": sesion_hoy_id, "alumno_id": alumnos[1]},
    )
    assert falta_resp.status_code == 200
    falta_asistencia_id = falta_resp.json()["falta"]["asistencia_id"]

    deuda_resp = client.post(
        "/pos/asistio-sin-pagar",
        json={"sesion_id": sesion_hoy_id, "alumno_id": alumnos[2]},
    )
    assert deuda_resp.status_code == 200
    deuda_asistencia_id = deuda_resp.json()["deuda"]["asistencia_id"]

    dash1 = client.get("/dashboard")
    assert dash1.status_code == 200
    assert dash1.text.count("$280.00") >= 2
    assert "2 tickets vigentes" in dash1.text
    assert "1 asistencia sin pago" in dash1.text
    assert "$140.00" in dash1.text

    recaudacion1 = client.get("/dashboard/recaudacion").json()
    assert recaudacion1["total_centavos"] == 28000
    ref1 = next(
        s for s in recaudacion1["sucursales"] if s["id"] == sucursal_ref_id
    )
    assert ref1["total_centavos"] == 28000
    assert ref1["tickets"] == 2

    deudas1 = client.get("/deudas")
    assert deudas1.status_code == 200
    assert "1 asistencia sin pago" in deudas1.text
    assert "Alumno 03" in deudas1.text

    repos1 = client.get("/reposiciones")
    assert repos1.status_code == 200
    assert "1 clase pagada por reponer" in repos1.text
    assert "Alumno 02" in repos1.text
    assert "Robótica Sábados" in repos1.text

    rep_post = client.post(
        f"/reposiciones/{falta_asistencia_id}/registrar",
        data={"sesion_id": sesion_tot_id},
        follow_redirects=False,
    )
    assert rep_post.status_code == 303
    assert rep_post.headers["location"] == "/reposiciones?registrada=1"

    repos2 = client.get("/reposiciones")
    assert repos2.status_code == 200
    assert "Sin reposiciones pendientes" in repos2.text

    dash2 = client.get("/dashboard")
    assert dash2.status_code == 200
    assert dash2.text.count("$280.00") >= 2
    assert "2 tickets vigentes" in dash2.text
    assert "1 asistencia sin pago" in dash2.text

    recaudacion2 = client.get("/dashboard/recaudacion").json()
    assert recaudacion2["total_centavos"] == 28000

    cobro_deuda_resp = client.post(
        f"/deudas/{deuda_asistencia_id}/cobrar",
        data={"metodo": "efectivo"},
        follow_redirects=False,
    )
    assert cobro_deuda_resp.status_code == 303
    assert "cobrado=" in cobro_deuda_resp.headers["location"]
    deuda_redirect = cobro_deuda_resp.headers["location"]

    deudas2 = client.get(deuda_redirect)
    assert deudas2.status_code == 200
    assert "Deuda cobrada" in deudas2.text
    assert "Sin deudas pendientes" in deudas2.text
    assert "REF-0003" in deudas2.text

    dash3 = client.get("/dashboard")
    assert dash3.status_code == 200
    assert dash3.text.count("$420.00") >= 2
    assert "3 tickets vigentes" in dash3.text
    assert "0 asistencias sin pago" in dash3.text
    assert "$0.00" in dash3.text

    recaudacion3 = client.get("/dashboard/recaudacion").json()
    assert recaudacion3["total_centavos"] == 42000
    ref3 = next(
        s for s in recaudacion3["sucursales"] if s["id"] == sucursal_ref_id
    )
    assert ref3["total_centavos"] == 42000
    assert ref3["tickets"] == 3

    with factory() as session:
        assert (
            session.scalar(
                select(func.count())
                .select_from(Pago)
                .where(Pago.estado == "vigente")
            )
            == 3
        )
        assert (
            session.scalar(
                select(func.count())
                .select_from(Asistencia)
                .where(Asistencia.estado == "asistio")
            )
            == 3
        )
        assert (
            session.scalar(
                select(func.count())
                .select_from(Asistencia)
                .where(Asistencia.estado == "falto")
            )
            == 1
        )
        assert (
            session.scalar(
                select(func.count())
                .select_from(Asistencia)
                .where(Asistencia.es_reposicion == 1)
            )
            == 1
        )
        deudas_restantes = session.execute(
            text("SELECT COUNT(*) FROM v_deudas")
        ).scalar_one()
        assert deudas_restantes == 0
        repos_restantes = session.execute(
            text("SELECT COUNT(*) FROM v_reposiciones_pendientes")
        ).scalar_one()
        assert repos_restantes == 0
