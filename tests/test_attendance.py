from collections.abc import Iterator
from datetime import date
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
from app.models import (
    Alumno,
    Asistencia,
    Grupo,
    Pago,
    Sesion,
    Sucursal,
)
from app.services import attendance
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
def attendance_app(
    tmp_path: Path,
) -> Iterator[tuple[TestClient, sessionmaker[Session], dict[str, int]]]:
    database_path = tmp_path / "attendance.db"
    command.upgrade(_config(database_path), "head")
    engine = build_engine(database_path)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory.begin() as session:
        seed_database(session)

    ids = _crear_escenario(factory)
    ids["database_path"] = database_path

    def override_get_db() -> Iterator[Session]:
        with factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[requiere_sesion] = lambda: None
    try:
        with TestClient(app) as client:
            yield client, factory, ids
    finally:
        app.dependency_overrides.clear()
        engine.dispose()


def _crear_escenario(
    factory: sessionmaker[Session],
) -> dict[str, int]:
    with factory.begin() as session:
        sucursal_ref = session.scalar(
            select(Sucursal).where(Sucursal.prefijo_folio == "REF")
        )
        sucursal_tot = session.scalar(
            select(Sucursal).where(Sucursal.prefijo_folio == "TOT")
        )
        assert sucursal_ref is not None
        assert sucursal_tot is not None
        grupo_ref = session.scalar(
            select(Grupo).where(Grupo.sucursal_id == sucursal_ref.id)
        )
        assert grupo_ref is not None

        alumnos = list(
            session.scalars(select(Alumno).order_by(Alumno.id).limit(5))
        )
        assert len(alumnos) == 5

        grupo_tot = Grupo(
            sucursal_id=sucursal_tot.id,
            nombre="Grupo Origen",
            dias_semana="Sábado",
            hora_inicio="09:00",
            hora_fin="11:00",
            precio_centavos=15000,
            activo=1,
        )
        session.add(grupo_tot)
        session.flush()

        sesiones_ref = []
        for fecha, estado in (
            ("2026-03-02", "programada"),
            ("2026-03-09", "programada"),
            ("2026-03-16", "programada"),
            ("2026-03-23", "cancelada"),
        ):
            sesion = Sesion(
                grupo_id=grupo_ref.id,
                fecha=fecha,
                estado=estado,
            )
            session.add(sesion)
            sesiones_ref.append(sesion)
        sesion_tot = Sesion(
            grupo_id=grupo_tot.id,
            fecha="2026-03-01",
            estado="programada",
        )
        session.add(sesion_tot)
        session.flush()

        pago_1 = Pago(
            folio="REF-1001",
            alumno_id=alumnos[0].id,
            sucursal_id=sucursal_ref.id,
            tipo="sesion",
            monto_centavos=14000,
            metodo="efectivo",
            fecha="2026-03-02 10:00:00",
            estado="vigente",
        )
        pago_2 = Pago(
            folio="REF-1002",
            alumno_id=alumnos[2].id,
            sucursal_id=sucursal_ref.id,
            tipo="sesion",
            monto_centavos=14000,
            metodo="efectivo",
            fecha="2026-03-02 10:01:00",
            estado="vigente",
        )
        pago_3 = Pago(
            folio="TOT-1001",
            alumno_id=alumnos[4].id,
            sucursal_id=sucursal_tot.id,
            tipo="sesion",
            monto_centavos=15000,
            metodo="efectivo",
            fecha="2026-03-01 10:00:00",
            estado="vigente",
        )
        pago_4 = Pago(
            folio="REF-1003",
            alumno_id=alumnos[1].id,
            sucursal_id=sucursal_ref.id,
            tipo="sesion",
            monto_centavos=14000,
            metodo="efectivo",
            fecha="2026-03-09 10:00:00",
            estado="vigente",
        )
        pago_5 = Pago(
            folio="REF-1004",
            alumno_id=alumnos[2].id,
            sucursal_id=sucursal_ref.id,
            tipo="sesion",
            monto_centavos=14000,
            metodo="efectivo",
            fecha="2026-03-09 10:01:00",
            estado="vigente",
        )
        session.add_all([pago_1, pago_2, pago_3, pago_4, pago_5])
        session.flush()

        falta_origen = Asistencia(
            sesion_id=sesion_tot.id,
            alumno_id=alumnos[4].id,
            estado="falto",
            es_reposicion=0,
            pago_id=pago_3.id,
            precio_aplicado_centavos=15000,
        )
        session.add(falta_origen)
        session.flush()

        falta_repuesta = Asistencia(
            sesion_id=sesiones_ref[1].id,
            alumno_id=alumnos[1].id,
            estado="falto",
            es_reposicion=0,
            pago_id=pago_4.id,
            precio_aplicado_centavos=14000,
        )
        falta_pendiente = Asistencia(
            sesion_id=sesiones_ref[1].id,
            alumno_id=alumnos[2].id,
            estado="falto",
            es_reposicion=0,
            pago_id=pago_5.id,
            precio_aplicado_centavos=14000,
        )
        session.add_all([falta_repuesta, falta_pendiente])
        session.flush()

        session.add_all(
            [
                Asistencia(
                    sesion_id=sesiones_ref[0].id,
                    alumno_id=alumnos[0].id,
                    estado="asistio",
                    es_reposicion=0,
                    pago_id=pago_1.id,
                    precio_aplicado_centavos=14000,
                ),
                Asistencia(
                    sesion_id=sesiones_ref[0].id,
                    alumno_id=alumnos[1].id,
                    estado="asistio",
                    es_reposicion=0,
                    pago_id=None,
                    precio_aplicado_centavos=14000,
                ),
                Asistencia(
                    sesion_id=sesiones_ref[0].id,
                    alumno_id=alumnos[2].id,
                    estado="falto",
                    es_reposicion=0,
                    pago_id=pago_2.id,
                    precio_aplicado_centavos=14000,
                ),
                Asistencia(
                    sesion_id=sesiones_ref[0].id,
                    alumno_id=alumnos[4].id,
                    estado="asistio",
                    es_reposicion=1,
                    repone_a_id=falta_origen.id,
                    pago_id=pago_3.id,
                    precio_aplicado_centavos=15000,
                ),
                Asistencia(
                    sesion_id=sesiones_ref[2].id,
                    alumno_id=alumnos[1].id,
                    estado="asistio",
                    es_reposicion=1,
                    repone_a_id=falta_repuesta.id,
                    pago_id=pago_4.id,
                    precio_aplicado_centavos=14000,
                ),
            ]
        )

        return {
            "grupo_ref": grupo_ref.id,
            "grupo_tot": grupo_tot.id,
            "alumno_1": alumnos[0].id,
            "alumno_2": alumnos[1].id,
            "alumno_3": alumnos[2].id,
            "sesion_1": sesiones_ref[0].id,
        }


def _params(ids: dict[str, int], **overrides: str) -> dict[str, str]:
    params = {
        "grupo_id": str(ids["grupo_ref"]),
        "desde": "2026-03-01",
        "hasta": "2026-03-31",
    }
    params.update(overrides)
    return params


def test_consulta_muestra_matriz_resumen_y_estados(
    attendance_app: tuple[
        TestClient,
        sessionmaker[Session],
        dict[str, int],
    ],
) -> None:
    client, _, ids = attendance_app

    response = client.get("/asistencias", params=_params(ids))

    assert response.status_code == 200
    assert "Consulta de asistencia" in response.text
    assert "Alumno 01" in response.text
    assert "Asistió" in response.text
    assert "Asistió · Deuda" in response.text
    assert "Faltó · Reponer" in response.text
    assert "Faltó · Repuesta" in response.text
    assert "Reposición" in response.text
    assert "Cancelada" in response.text
    assert "Grupo Origen" in response.text
    assert "REF-1001" in response.text
    assert "Exportar CSV" in response.text
    assert response.headers["cache-control"] == "no-store"


def test_filtra_por_fechas_y_excluye_sesiones_fuera_del_rango(
    attendance_app: tuple[
        TestClient,
        sessionmaker[Session],
        dict[str, int],
    ],
) -> None:
    client, _, ids = attendance_app

    response = client.get(
        "/asistencias",
        params=_params(ids, desde="2026-03-09", hasta="2026-03-31"),
    )

    assert response.status_code == 200
    assert "Faltó · Reponer" in response.text
    assert "Faltó · Repuesta" in response.text
    assert "REF-1001" not in response.text
    assert "2026-03-02" not in response.text


def test_exportacion_csv_incluye_bom_y_escapa_campos(
    attendance_app: tuple[
        TestClient,
        sessionmaker[Session],
        dict[str, int],
    ],
) -> None:
    client, factory, ids = attendance_app
    with factory.begin() as session:
        alumno = session.get(Alumno, ids["alumno_1"])
        assert alumno is not None
        alumno.nombre = 'Pérez, Ana "La Jefa"'

    response = client.get("/asistencias/exportar", params=_params(ids))

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert "asistencias_" in response.headers["content-disposition"]
    contenido = response.text
    assert contenido.startswith("\ufeff")
    assert "Sucursal;Grupo;Fecha de sesión" in contenido
    assert '"Pérez, Ana ""La Jefa"""' in contenido
    assert "REF-1001" in contenido
    assert "140.00" in contenido
    assert "Reposición" in contenido
    assert "TOT-1001" in contenido


def test_rango_invalido_y_grupo_inexistente(
    attendance_app: tuple[
        TestClient,
        sessionmaker[Session],
        dict[str, int],
    ],
) -> None:
    client, _, ids = attendance_app

    invertido = client.get(
        "/asistencias",
        params=_params(ids, desde="2026-03-31", hasta="2026-03-01"),
    )
    assert invertido.status_code == 200
    assert "no puede ser posterior" in invertido.text

    mal_formato = client.get(
        "/asistencias",
        params=_params(ids, desde="31-03-2026"),
    )
    assert mal_formato.status_code == 200
    assert "formato AAAA-MM-DD" in mal_formato.text

    inexistente = client.get(
        "/asistencias",
        params=_params(ids, grupo_id="999999"),
    )
    assert inexistente.status_code == 200
    assert "El grupo no existe" in inexistente.text

    exportacion = client.get(
        "/asistencias/exportar",
        params=_params(ids, desde="2026-03-31", hasta="2026-03-01"),
    )
    assert exportacion.status_code == 400
    assert "no puede ser posterior" in exportacion.text


def test_sin_grupo_muestra_estado_vacio(
    attendance_app: tuple[
        TestClient,
        sessionmaker[Session],
        dict[str, int],
    ],
) -> None:
    client, _, _ = attendance_app

    response = client.get("/asistencias")

    assert response.status_code == 200
    assert "Selecciona un grupo" in response.text
    assert "Consulta de asistencia" in response.text


def test_servicio_incluye_alumno_historico_y_valida_rango(
    attendance_app: tuple[
        TestClient,
        sessionmaker[Session],
        dict[str, int],
    ],
) -> None:
    _, factory, ids = attendance_app

    with factory() as session:
        alumno = session.get(Alumno, ids["alumno_1"])
        assert alumno is not None
        alumno.estado = "baja"
        resumen = attendance.resumen_asistencia(
            session,
            ids["grupo_ref"],
            date(2026, 3, 1),
            date(2026, 3, 31),
        )

    fila = next(
        item for item in resumen.filas if item.alumno_id == ids["alumno_1"]
    )
    assert fila.estado_alumno == "baja"
    assert resumen.total_asistio == 2
    assert resumen.total_falto == 3
    assert resumen.total_deuda == 1
    assert resumen.total_reposicion == 2

    with factory() as session, pytest.raises(attendance.AttendanceError):
        attendance.resumen_asistencia(
            session,
            ids["grupo_ref"],
            date(2026, 1, 1),
            date(2027, 6, 1),
        )
