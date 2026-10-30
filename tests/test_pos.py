import re
from collections.abc import Iterator
from datetime import date
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from app.core.database import build_engine, get_db
from app.main import app
from app.models import Alumno, Asistencia, Grupo, Pago, Sesion, Sucursal
from app.services.pos import clave_orden
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
def pos_app(
    tmp_path: Path,
) -> Iterator[tuple[TestClient, sessionmaker[Session]]]:
    database_path = tmp_path / "pos.db"
    command.upgrade(_config(database_path), "head")
    engine = build_engine(database_path)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory.begin() as session:
        seed_database(session)

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


def test_pos_lists_branches(pos_app: tuple[TestClient, sessionmaker[Session]]) -> None:
    client, _ = pos_app
    response = client.get("/pos")

    assert response.status_code == 200
    assert "ICIA" in response.text
    for nombre in ("Tototlán", "Ocotlán", "Poncitlán", "El Refugio"):
        assert nombre in response.text


def test_pos_lists_groups(
    pos_app: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, factory = pos_app
    sucursal_id, _ = _ref_ids(factory)

    response = client.get(f"/pos?sucursal_id={sucursal_id}")

    assert response.status_code == 200
    assert "Jueves 3-5 PM" in response.text
    assert "$140.00" in response.text


def test_pos_opens_today_session_and_lists_students(
    pos_app: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, factory = pos_app
    _, grupo_id = _ref_ids(factory)

    response = client.post(
        f"/pos/sesiones?grupo_id={grupo_id}",
        follow_redirects=False,
    )

    assert response.status_code == 303
    location = response.headers["location"]
    assert "sesion_id=" in location

    roster = client.get(location)
    assert roster.status_code == 200
    nombres = [f"Alumno {indice:02d}" for indice in range(1, 36)]
    for nombre in nombres:
        assert nombre in roster.text
    posiciones = [roster.text.index(nombre) for nombre in nombres]
    assert posiciones == sorted(posiciones)

    with factory() as session:
        assert session.scalar(select(func.count()).select_from(Sesion)) == 1
        assert session.scalar(select(func.count()).select_from(Pago)) == 0
        assert session.scalar(select(func.count()).select_from(Asistencia)) == 0


def test_pos_open_session_is_idempotent(
    pos_app: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, factory = pos_app
    _, grupo_id = _ref_ids(factory)
    url = f"/pos/sesiones?grupo_id={grupo_id}"

    first = client.post(url, follow_redirects=False)
    second = client.post(url, follow_redirects=False)

    assert first.status_code == 303
    assert second.status_code == 303
    assert first.headers["location"] == second.headers["location"]
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(Sesion)) == 1


def test_pos_roster_shows_payment_states(
    pos_app: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, factory = pos_app
    sucursal_id, grupo_id = _ref_ids(factory)
    sesion_id = _create_today_session(factory, grupo_id)

    with factory.begin() as session:
        alumnos = {
            alumno.nombre: alumno.id
            for alumno in session.scalars(select(Alumno))
        }
        pago = Pago(
            folio="REF-0001",
            alumno_id=alumnos["Alumno 01"],
            sucursal_id=sucursal_id,
            tipo="sesion",
            monto_centavos=14000,
            metodo="efectivo",
        )
        session.add(pago)
        session.flush()
        session.add(
            Asistencia(
                sesion_id=sesion_id,
                alumno_id=alumnos["Alumno 01"],
                estado="asistio",
                pago_id=pago.id,
                precio_aplicado_centavos=14000,
            )
        )
        session.add(
            Asistencia(
                sesion_id=sesion_id,
                alumno_id=alumnos["Alumno 02"],
                estado="asistio",
                pago_id=None,
                precio_aplicado_centavos=14000,
            )
        )
        session.add(
            Asistencia(
                sesion_id=sesion_id,
                alumno_id=alumnos["Alumno 03"],
                estado="falto",
                pago_id=None,
                precio_aplicado_centavos=14000,
            )
        )

    response = client.get(
        f"/pos?sucursal_id={sucursal_id}"
        f"&grupo_id={grupo_id}"
        f"&sesion_id={sesion_id}"
    )

    assert response.status_code == 200
    assert re.search(
        rf'data-alumno-id="{alumnos["Alumno 01"]}"\s+data-estado="pagado"',
        response.text,
    )
    assert re.search(
        rf'data-alumno-id="{alumnos["Alumno 02"]}"\s+data-estado="deuda"',
        response.text,
    )
    assert re.search(
        rf'data-alumno-id="{alumnos["Alumno 03"]}"\s+data-estado="falto"',
        response.text,
    )
    assert "32 pendientes" in response.text
    assert "1 pagados" in response.text
    assert "1 deudas" in response.text
    assert "1 faltas" in response.text


def test_pos_empty_branch(
    pos_app: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, factory = pos_app
    with factory() as session:
        sucursal = session.scalar(
            select(Sucursal).where(Sucursal.prefijo_folio == "TOT")
        )
        assert sucursal is not None
        sucursal_id = sucursal.id

    response = client.get(f"/pos?sucursal_id={sucursal_id}")

    assert response.status_code == 200
    assert "No hay grupos activos en esta sucursal." in response.text


def test_pos_group_without_session_shows_open_button(
    pos_app: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, factory = pos_app
    sucursal_id, grupo_id = _ref_ids(factory)

    response = client.get(
        f"/pos?sucursal_id={sucursal_id}&grupo_id={grupo_id}"
    )

    assert response.status_code == 200
    assert "Abrir sesión de hoy" in response.text
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(Sesion)) == 0


def test_pos_cancelled_session_shows_notice(
    pos_app: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, factory = pos_app
    sucursal_id, grupo_id = _ref_ids(factory)
    sesion_id = _create_today_session(factory, grupo_id, estado="cancelada")

    response = client.get(
        f"/pos?sucursal_id={sucursal_id}"
        f"&grupo_id={grupo_id}"
        f"&sesion_id={sesion_id}"
    )

    assert response.status_code == 200
    assert "Sesión cancelada: no genera faltas, cobros ni pago a maestros." in response.text


def test_static_css_is_served(
    pos_app: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, _ = pos_app
    response = client.get("/static/css/app.css")

    assert response.status_code == 200
    assert "--primary" in response.text
    assert ".action-bar" in response.text
    assert ".toast" in response.text
    assert ".student-card--cobrando" in response.text


def test_clave_orden_ignores_accents_and_case() -> None:
    nombres = ["Zoe", "Ángel", "beatriz", "Carlos"]

    assert sorted(nombres, key=clave_orden) == [
        "Ángel",
        "beatriz",
        "Carlos",
        "Zoe",
    ]


def test_pos_session_includes_keyboard_controls(
    pos_app: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, factory = pos_app
    sucursal_id, grupo_id = _ref_ids(factory)
    sesion_id = _create_today_session(factory, grupo_id)

    response = client.get(
        f"/pos?sucursal_id={sucursal_id}"
        f"&grupo_id={grupo_id}"
        f"&sesion_id={sesion_id}"
    )

    assert response.status_code == 200
    assert f'data-sesion-id="{sesion_id}"' in response.text
    assert 'data-counter="pendientes"' in response.text
    assert 'data-counter="pagados"' in response.text
    assert 'data-counter="deudas"' in response.text
    assert 'data-counter="faltas"' in response.text
    assert 'id="pos-toast"' in response.text
    assert 'data-metodo="efectivo"' in response.text
    assert 'data-metodo="transferencia"' in response.text
    assert "/static/js/pos.js" in response.text


def test_pos_cancelled_session_omits_keyboard_controls(
    pos_app: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, factory = pos_app
    sucursal_id, grupo_id = _ref_ids(factory)
    sesion_id = _create_today_session(
        factory,
        grupo_id,
        estado="cancelada",
    )

    response = client.get(
        f"/pos?sucursal_id={sucursal_id}"
        f"&grupo_id={grupo_id}"
        f"&sesion_id={sesion_id}"
    )

    assert response.status_code == 200
    assert 'id="pos-toast"' not in response.text
    assert 'data-metodo="efectivo"' not in response.text
    assert "/static/js/pos.js" not in response.text


def test_static_pos_js_is_served(
    pos_app: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, _ = pos_app
    response = client.get("/static/js/pos.js")

    assert response.status_code == 200
    assert 'fetch("/pos/cobrar"' in response.text
    assert 'event.key === "F1"' in response.text
    assert 'event.key === "F2"' in response.text
    assert "data-counter" in response.text
    assert "window.location" not in response.text
