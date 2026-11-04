from collections.abc import Iterator
from datetime import date, timedelta
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session, sessionmaker

from app.core.database import build_engine, get_db
from app.core.security import requiere_sesion
from app.main import app
from app.models import (
    Alumno,
    Asistencia,
    FolioContador,
    Grupo,
    Pago,
    Sesion,
    Sucursal,
)
from app.services import cashier as cashier_service
from app.services.cashier import CashierError
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
def repositions_app(
    tmp_path: Path,
) -> Iterator[tuple[TestClient, sessionmaker[Session]]]:
    database_path = tmp_path / "repositions.db"
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
        alumno_id = session.scalar(
            select(Alumno.id).order_by(Alumno.id).limit(1)
        )
        assert alumno_id is not None
        return sucursal.id, grupo.id, alumno_id


def _create_falta_pagada(
    factory: sessionmaker[Session],
    grupo_id: int,
    alumno_id: int,
    fecha: date | None = None,
) -> tuple[int, int]:
    with factory.begin() as session:
        sesion = Sesion(
            grupo_id=grupo_id,
            fecha=(fecha or date.today()).isoformat(),
            estado="programada",
        )
        session.add(sesion)
        session.flush()
        sesion_id = sesion.id

    with factory() as session:
        cobro = cashier_service.cobrar_sesion(
            session,
            sesion_id=sesion_id,
            alumno_id=alumno_id,
            metodo="efectivo",
        )

    with factory() as session:
        falta = cashier_service.marcar_falta(
            session,
            sesion_id=sesion_id,
            alumno_id=alumno_id,
        )

    return falta.asistencia_id, cobro.pago_id


def _create_target(
    factory: sessionmaker[Session],
    fecha: date | None = None,
    estado: str = "programada",
) -> tuple[int, int]:
    with factory.begin() as session:
        sucursal = session.scalar(
            select(Sucursal).where(Sucursal.prefijo_folio == "TOT")
        )
        assert sucursal is not None
        grupo = Grupo(
            sucursal_id=sucursal.id,
            nombre="Grupo destino",
            dias_semana="Sábado",
            hora_inicio="10:00",
            hora_fin="12:00",
            precio_centavos=13000,
        )
        session.add(grupo)
        session.flush()
        sesion = Sesion(
            grupo_id=grupo.id,
            fecha=(fecha or date.today() + timedelta(days=1)).isoformat(),
            estado=estado,
        )
        session.add(sesion)
        session.flush()
        return grupo.id, sesion.id


def _create_same_group_session(
    factory: sessionmaker[Session],
    grupo_id: int,
) -> int:
    with factory.begin() as session:
        sesion = Sesion(
            grupo_id=grupo_id,
            fecha=(date.today() + timedelta(days=1)).isoformat(),
            estado="programada",
        )
        session.add(sesion)
        session.flush()
        return sesion.id


def test_registrar_reposicion_no_crea_pago_ni_folio(
    repositions_app: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, factory = repositions_app
    sucursal_id, grupo_id, alumno_id = _ref_ids(factory)
    falta_id, pago_id = _create_falta_pagada(
        factory,
        grupo_id,
        alumno_id,
    )
    grupo_destino, sesion_destino = _create_target(factory)

    with factory() as session:
        resultado = cashier_service.registrar_reposicion(
            session,
            falta_id=falta_id,
            sesion_destino_id=sesion_destino,
        )

    assert resultado.falta_id == falta_id
    assert resultado.pago_id == pago_id
    assert resultado.folio == "REF-0001"
    assert resultado.grupo_id == grupo_destino
    assert resultado.sesion_id == sesion_destino
    assert resultado.sucursal == "Tototlán"
    assert resultado.monto_centavos == 14000

    with factory() as session:
        falta = session.get(Asistencia, falta_id)
        assert falta is not None
        assert falta.estado == "falto"
        reposicion = session.get(Asistencia, resultado.asistencia_id)
        assert reposicion is not None
        assert reposicion.estado == "asistio"
        assert reposicion.es_reposicion == 1
        assert reposicion.repone_a_id == falta_id
        assert reposicion.pago_id == pago_id
        assert reposicion.precio_aplicado_centavos == 14000
        assert session.scalar(select(func.count()).select_from(Pago)) == 1
        contador = session.scalar(
            select(FolioContador.ultimo_consecutivo).where(
                FolioContador.sucursal_id == sucursal_id
            )
        )
        assert contador == 1
        pendientes = session.execute(
            text("SELECT COUNT(*) FROM v_reposiciones_pendientes")
        ).scalar_one()
        assert pendientes == 0

    dashboard = client.get("/dashboard")
    assert dashboard.status_code == 200
    assert "$140.00" in dashboard.text
    assert "0 asistencias sin pago" in dashboard.text


def test_registrar_reposicion_rechaza_mismo_grupo(
    repositions_app: tuple[TestClient, sessionmaker[Session]],
) -> None:
    _, factory = repositions_app
    _sucursal_id, grupo_id, alumno_id = _ref_ids(factory)
    falta_id, _ = _create_falta_pagada(factory, grupo_id, alumno_id)
    sesion_destino = _create_same_group_session(factory, grupo_id)

    with factory() as session:
        with pytest.raises(CashierError, match="otro grupo"):
            cashier_service.registrar_reposicion(
                session,
                falta_id=falta_id,
                sesion_destino_id=sesion_destino,
            )


def test_registrar_reposicion_rechaza_sesion_cancelada(
    repositions_app: tuple[TestClient, sessionmaker[Session]],
) -> None:
    _, factory = repositions_app
    _sucursal_id, grupo_id, alumno_id = _ref_ids(factory)
    falta_id, _ = _create_falta_pagada(factory, grupo_id, alumno_id)
    _, sesion_destino = _create_target(factory, estado="cancelada")

    with factory() as session:
        with pytest.raises(CashierError, match="cancelada"):
            cashier_service.registrar_reposicion(
                session,
                falta_id=falta_id,
                sesion_destino_id=sesion_destino,
            )


def test_registrar_reposicion_rechaza_fecha_anterior(
    repositions_app: tuple[TestClient, sessionmaker[Session]],
) -> None:
    _, factory = repositions_app
    _sucursal_id, grupo_id, alumno_id = _ref_ids(factory)
    falta_id, _ = _create_falta_pagada(factory, grupo_id, alumno_id)
    _, sesion_destino = _create_target(
        factory,
        fecha=date.today() - timedelta(days=1),
    )

    with factory() as session:
        with pytest.raises(CashierError, match="anterior"):
            cashier_service.registrar_reposicion(
                session,
                falta_id=falta_id,
                sesion_destino_id=sesion_destino,
            )


def test_registrar_reposicion_rechaza_duplicado(
    repositions_app: tuple[TestClient, sessionmaker[Session]],
) -> None:
    _, factory = repositions_app
    _sucursal_id, grupo_id, alumno_id = _ref_ids(factory)
    falta_id, _ = _create_falta_pagada(factory, grupo_id, alumno_id)
    _, sesion_destino = _create_target(factory)

    with factory() as session:
        cashier_service.registrar_reposicion(
            session,
            falta_id=falta_id,
            sesion_destino_id=sesion_destino,
        )

    with factory() as session:
        with pytest.raises(CashierError, match="ya fue repuesta"):
            cashier_service.registrar_reposicion(
                session,
                falta_id=falta_id,
                sesion_destino_id=sesion_destino,
            )


def test_registrar_reposicion_rechaza_asistencia_en_destino(
    repositions_app: tuple[TestClient, sessionmaker[Session]],
) -> None:
    _, factory = repositions_app
    _sucursal_id, grupo_id, alumno_id = _ref_ids(factory)
    falta_id, _ = _create_falta_pagada(factory, grupo_id, alumno_id)
    _, sesion_destino = _create_target(factory)

    with factory.begin() as session:
        session.add(
            Asistencia(
                sesion_id=sesion_destino,
                alumno_id=alumno_id,
                estado="asistio",
                es_reposicion=0,
                pago_id=None,
                precio_aplicado_centavos=13000,
            )
        )

    with factory() as session:
        with pytest.raises(CashierError, match="ya tiene asistencia"):
            cashier_service.registrar_reposicion(
                session,
                falta_id=falta_id,
                sesion_destino_id=sesion_destino,
            )


def test_registrar_reposicion_rollback_si_falla_commit(
    repositions_app: tuple[TestClient, sessionmaker[Session]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, factory = repositions_app
    _sucursal_id, grupo_id, alumno_id = _ref_ids(factory)
    falta_id, _ = _create_falta_pagada(factory, grupo_id, alumno_id)
    _, sesion_destino = _create_target(factory)

    session = factory()

    def fallar_commit() -> None:
        raise RuntimeError("fallo simulado")

    monkeypatch.setattr(session, "commit", fallar_commit)
    try:
        with pytest.raises(RuntimeError, match="fallo simulado"):
            cashier_service.registrar_reposicion(
                session,
                falta_id=falta_id,
                sesion_destino_id=sesion_destino,
            )
    finally:
        session.close()

    with factory() as session:
        assert session.scalar(select(func.count()).select_from(Asistencia)) == 1


def test_reposiciones_lista_pendientes_y_sesiones_destino(
    repositions_app: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, factory = repositions_app
    _sucursal_id, grupo_id, alumno_id = _ref_ids(factory)
    _create_falta_pagada(factory, grupo_id, alumno_id)
    _create_target(factory)

    response = client.get("/reposiciones")

    assert response.status_code == 200
    assert "Reposiciones pendientes" in response.text
    assert "Alumno 01" in response.text
    assert "El Refugio" in response.text
    assert "Jueves 3-5 PM" in response.text
    assert "REF-0001" in response.text
    assert "$140.00" in response.text
    assert "Grupo destino" in response.text
    assert "Tototlán" in response.text
    assert "Registrar reposición" in response.text
    assert response.headers["cache-control"] == "no-store"


def test_reposiciones_estado_vacio(
    repositions_app: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, _ = repositions_app

    response = client.get("/reposiciones")

    assert response.status_code == 200
    assert "Sin reposiciones pendientes" in response.text
    assert "$0.00" in response.text


def test_reposiciones_sin_sesiones_destino(
    repositions_app: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, factory = repositions_app
    _sucursal_id, grupo_id, alumno_id = _ref_ids(factory)
    _create_falta_pagada(factory, grupo_id, alumno_id)

    response = client.get("/reposiciones")

    assert response.status_code == 200
    assert "No hay sesiones disponibles en otros grupos." in response.text


def test_registrar_reposicion_desde_ui(
    repositions_app: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, factory = repositions_app
    _sucursal_id, grupo_id, alumno_id = _ref_ids(factory)
    falta_id, pago_id = _create_falta_pagada(
        factory,
        grupo_id,
        alumno_id,
    )
    _, sesion_destino = _create_target(factory)

    response = client.post(
        f"/reposiciones/{falta_id}/registrar",
        data={"sesion_id": sesion_destino},
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/reposiciones?registrada=1"

    pagina = client.get(response.headers["location"])
    assert pagina.status_code == 200
    assert "Reposición registrada" in pagina.text
    assert "No se generó cobro nuevo" in pagina.text
    assert "Sin reposiciones pendientes" in pagina.text

    with factory() as session:
        reposicion = session.scalar(
            select(Asistencia).where(Asistencia.repone_a_id == falta_id)
        )
        assert reposicion is not None
        assert reposicion.pago_id == pago_id
        assert reposicion.sesion_id == sesion_destino
        assert session.scalar(select(func.count()).select_from(Pago)) == 1

    dashboard = client.get("/dashboard")
    assert dashboard.status_code == 200
    assert "$140.00" in dashboard.text


def test_registrar_reposicion_duplicada_desde_ui(
    repositions_app: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, factory = repositions_app
    _sucursal_id, grupo_id, alumno_id = _ref_ids(factory)
    falta_id, _ = _create_falta_pagada(factory, grupo_id, alumno_id)
    _, sesion_destino = _create_target(factory)
    url = f"/reposiciones/{falta_id}/registrar"

    primera = client.post(
        url,
        data={"sesion_id": sesion_destino},
        follow_redirects=False,
    )
    assert primera.status_code == 303

    segunda = client.post(
        url,
        data={"sesion_id": sesion_destino},
        follow_redirects=False,
    )

    assert segunda.status_code == 303
    assert segunda.headers["location"].startswith("/reposiciones?error=")
    pagina = client.get(segunda.headers["location"])
    assert "ya fue repuesta" in pagina.text

    with factory() as session:
        assert (
            session.scalar(
                select(func.count())
                .select_from(Asistencia)
                .where(Asistencia.repone_a_id == falta_id)
            )
            == 1
        )
