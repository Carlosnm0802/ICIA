import re
from collections.abc import Iterator
from datetime import date
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import Engine, func, select, text
from sqlalchemy.orm import Session, sessionmaker

from app.core.database import build_engine, get_db
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
from app.services.cashier import CashierError, cobrar_sesion, registrar_deuda
from app.services.folios import FolioError
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


def _build_factory(
    tmp_path: Path,
    nombre: str,
) -> tuple[sessionmaker[Session], Engine]:
    database_path = tmp_path / nombre
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
def cashier_factory(
    tmp_path: Path,
) -> Iterator[sessionmaker[Session]]:
    factory, engine = _build_factory(tmp_path, "cashier.db")
    try:
        yield factory
    finally:
        engine.dispose()


@pytest.fixture
def cashier_app(
    tmp_path: Path,
) -> Iterator[tuple[TestClient, sessionmaker[Session]]]:
    factory, engine = _build_factory(tmp_path, "cashier_api.db")

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
                select(Alumno.id).order_by(Alumno.id).limit(3)
            )
        )
        return sucursal.id, grupo.id, alumnos


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


def _contador(
    factory: sessionmaker[Session],
    sucursal_id: int,
) -> int:
    with factory() as session:
        valor = session.scalar(
            select(FolioContador.ultimo_consecutivo).where(
                FolioContador.sucursal_id == sucursal_id
            )
        )
        assert valor is not None
        return valor


def _conteos(
    factory: sessionmaker[Session],
) -> tuple[int, int]:
    with factory() as session:
        pagos = session.scalar(select(func.count()).select_from(Pago))
        asistencias = session.scalar(
            select(func.count()).select_from(Asistencia)
        )
        return pagos or 0, asistencias or 0


def test_cobro_crea_pago_y_asistencia(
    cashier_factory: sessionmaker[Session],
) -> None:
    sucursal_id, grupo_id, alumnos = _ref_ids(cashier_factory)
    sesion_id = _create_session(cashier_factory, grupo_id)

    with cashier_factory() as session:
        resultado = cobrar_sesion(
            session,
            sesion_id=sesion_id,
            alumno_id=alumnos[0],
            metodo="efectivo",
        )

    assert resultado.folio == "REF-0001"
    assert resultado.monto_centavos == 14000
    assert resultado.metodo == "efectivo"
    assert resultado.sesion_id == sesion_id

    with cashier_factory() as session:
        pago = session.scalar(select(Pago))
        assert pago is not None
        assert pago.folio == "REF-0001"
        assert pago.alumno_id == alumnos[0]
        assert pago.sucursal_id == sucursal_id
        assert pago.tipo == "sesion"
        assert pago.monto_centavos == 14000
        assert pago.metodo == "efectivo"
        assert pago.estado == "vigente"

        asistencia = session.scalar(select(Asistencia))
        assert asistencia is not None
        assert asistencia.sesion_id == sesion_id
        assert asistencia.alumno_id == alumnos[0]
        assert asistencia.estado == "asistio"
        assert asistencia.es_reposicion == 0
        assert asistencia.pago_id == pago.id
        assert asistencia.precio_aplicado_centavos == 14000

    assert _contador(cashier_factory, sucursal_id) == 1


def test_cobro_usa_precio_vigente_y_conserva_anteriores(
    cashier_factory: sessionmaker[Session],
) -> None:
    _, grupo_id, alumnos = _ref_ids(cashier_factory)
    sesion_id = _create_session(cashier_factory, grupo_id)

    with cashier_factory() as session:
        primero = cobrar_sesion(
            session,
            sesion_id=sesion_id,
            alumno_id=alumnos[0],
            metodo="efectivo",
        )

    with cashier_factory.begin() as session:
        grupo = session.get(Grupo, grupo_id)
        assert grupo is not None
        grupo.precio_centavos = 15000

    with cashier_factory() as session:
        segundo = cobrar_sesion(
            session,
            sesion_id=sesion_id,
            alumno_id=alumnos[1],
            metodo="transferencia",
        )

    assert primero.monto_centavos == 14000
    assert segundo.monto_centavos == 15000

    with cashier_factory() as session:
        pagos = list(session.scalars(select(Pago).order_by(Pago.id)))
        asistencias = list(
            session.scalars(select(Asistencia).order_by(Asistencia.id))
        )
        assert [pago.monto_centavos for pago in pagos] == [14000, 15000]
        assert [
            asistencia.precio_aplicado_centavos for asistencia in asistencias
        ] == [14000, 15000]


def test_cobro_genera_folios_consecutivos(
    cashier_factory: sessionmaker[Session],
) -> None:
    _, grupo_id, alumnos = _ref_ids(cashier_factory)
    sesion_id = _create_session(cashier_factory, grupo_id)

    with cashier_factory() as session:
        primero = cobrar_sesion(
            session,
            sesion_id=sesion_id,
            alumno_id=alumnos[0],
            metodo="efectivo",
        )
    with cashier_factory() as session:
        segundo = cobrar_sesion(
            session,
            sesion_id=sesion_id,
            alumno_id=alumnos[1],
            metodo="efectivo",
        )

    assert primero.folio == "REF-0001"
    assert segundo.folio == "REF-0002"


def test_cobro_rechaza_sesion_cancelada(
    cashier_factory: sessionmaker[Session],
) -> None:
    sucursal_id, grupo_id, alumnos = _ref_ids(cashier_factory)
    sesion_id = _create_session(
        cashier_factory,
        grupo_id,
        estado="cancelada",
    )

    with cashier_factory() as session:
        with pytest.raises(CashierError, match="cancelada"):
            cobrar_sesion(
                session,
                sesion_id=sesion_id,
                alumno_id=alumnos[0],
                metodo="efectivo",
            )

    assert _conteos(cashier_factory) == (0, 0)
    assert _contador(cashier_factory, sucursal_id) == 0


def test_cobro_rechaza_alumno_no_inscrito(
    cashier_factory: sessionmaker[Session],
) -> None:
    sucursal_id, grupo_id, _ = _ref_ids(cashier_factory)
    sesion_id = _create_session(cashier_factory, grupo_id)
    with cashier_factory.begin() as session:
        alumno = Alumno(nombre="Alumno externo")
        session.add(alumno)
        session.flush()
        alumno_id = alumno.id

    with cashier_factory() as session:
        with pytest.raises(CashierError, match="no está inscrito"):
            cobrar_sesion(
                session,
                sesion_id=sesion_id,
                alumno_id=alumno_id,
                metodo="efectivo",
            )

    assert _conteos(cashier_factory) == (0, 0)
    assert _contador(cashier_factory, sucursal_id) == 0


def test_cobro_rechaza_alumno_inactivo(
    cashier_factory: sessionmaker[Session],
) -> None:
    sucursal_id, grupo_id, alumnos = _ref_ids(cashier_factory)
    sesion_id = _create_session(cashier_factory, grupo_id)
    with cashier_factory.begin() as session:
        alumno = session.get(Alumno, alumnos[0])
        assert alumno is not None
        alumno.estado = "baja"

    with cashier_factory() as session:
        with pytest.raises(CashierError, match="no está activo"):
            cobrar_sesion(
                session,
                sesion_id=sesion_id,
                alumno_id=alumnos[0],
                metodo="efectivo",
            )

    assert _conteos(cashier_factory) == (0, 0)
    assert _contador(cashier_factory, sucursal_id) == 0


def test_cobro_rechaza_doble_cobro(
    cashier_factory: sessionmaker[Session],
) -> None:
    sucursal_id, grupo_id, alumnos = _ref_ids(cashier_factory)
    sesion_id = _create_session(cashier_factory, grupo_id)

    with cashier_factory() as session:
        cobrar_sesion(
            session,
            sesion_id=sesion_id,
            alumno_id=alumnos[0],
            metodo="efectivo",
        )

    with cashier_factory() as session:
        with pytest.raises(CashierError, match="ya tiene asistencia"):
            cobrar_sesion(
                session,
                sesion_id=sesion_id,
                alumno_id=alumnos[0],
                metodo="efectivo",
            )

    assert _conteos(cashier_factory) == (1, 1)
    assert _contador(cashier_factory, sucursal_id) == 1


def test_cobro_rechaza_metodo_invalido(
    cashier_factory: sessionmaker[Session],
) -> None:
    _, grupo_id, alumnos = _ref_ids(cashier_factory)
    sesion_id = _create_session(cashier_factory, grupo_id)

    with cashier_factory() as session:
        with pytest.raises(CashierError, match="Método de pago inválido"):
            cobrar_sesion(
                session,
                sesion_id=sesion_id,
                alumno_id=alumnos[0],
                metodo="tarjeta",
            )


def test_cobro_rechaza_sesion_inexistente(
    cashier_factory: sessionmaker[Session],
) -> None:
    _, _, alumnos = _ref_ids(cashier_factory)

    with cashier_factory() as session:
        with pytest.raises(CashierError, match="sesión no existe"):
            cobrar_sesion(
                session,
                sesion_id=999999,
                alumno_id=alumnos[0],
                metodo="efectivo",
            )


def test_cobro_rechaza_transaccion_abierta(
    cashier_factory: sessionmaker[Session],
) -> None:
    _, grupo_id, alumnos = _ref_ids(cashier_factory)
    sesion_id = _create_session(cashier_factory, grupo_id)

    with cashier_factory() as session:
        session.execute(select(1))
        with pytest.raises(CashierError, match="transacción abierta"):
            cobrar_sesion(
                session,
                sesion_id=sesion_id,
                alumno_id=alumnos[0],
                metodo="efectivo",
            )


def test_rollback_total_si_falla_commit(
    cashier_factory: sessionmaker[Session],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sucursal_id, grupo_id, alumnos = _ref_ids(cashier_factory)
    sesion_id = _create_session(cashier_factory, grupo_id)
    session = cashier_factory()

    def fallar_commit() -> None:
        raise RuntimeError("fallo simulado")

    monkeypatch.setattr(session, "commit", fallar_commit)
    try:
        with pytest.raises(RuntimeError, match="fallo simulado"):
            cobrar_sesion(
                session,
                sesion_id=sesion_id,
                alumno_id=alumnos[0],
                metodo="efectivo",
            )
    finally:
        session.close()

    assert _conteos(cashier_factory) == (0, 0)
    assert _contador(cashier_factory, sucursal_id) == 0


def test_rollback_total_si_falla_folio(
    cashier_factory: sessionmaker[Session],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sucursal_id, grupo_id, alumnos = _ref_ids(cashier_factory)
    sesion_id = _create_session(cashier_factory, grupo_id)

    def fallar_folio(_db: Session, _sucursal_id: int) -> str:
        raise FolioError("sin folio disponible")

    monkeypatch.setattr(
        "app.services.cashier.siguiente_folio",
        fallar_folio,
    )

    with cashier_factory() as session:
        with pytest.raises(CashierError, match="sin folio disponible"):
            cobrar_sesion(
                session,
                sesion_id=sesion_id,
                alumno_id=alumnos[0],
                metodo="efectivo",
            )

    assert _conteos(cashier_factory) == (0, 0)
    assert _contador(cashier_factory, sucursal_id) == 0


def test_deuda_crea_asistencia_sin_pago(
    cashier_factory: sessionmaker[Session],
) -> None:
    sucursal_id, grupo_id, alumnos = _ref_ids(cashier_factory)
    sesion_id = _create_session(cashier_factory, grupo_id)

    with cashier_factory() as session:
        resultado = registrar_deuda(
            session,
            sesion_id=sesion_id,
            alumno_id=alumnos[0],
        )

    assert resultado.monto_centavos == 14000
    assert resultado.sesion_id == sesion_id

    with cashier_factory() as session:
        asistencia = session.scalar(select(Asistencia))
        assert asistencia is not None
        assert asistencia.sesion_id == sesion_id
        assert asistencia.alumno_id == alumnos[0]
        assert asistencia.estado == "asistio"
        assert asistencia.es_reposicion == 0
        assert asistencia.pago_id is None
        assert asistencia.precio_aplicado_centavos == 14000
        assert session.scalar(select(func.count()).select_from(Pago)) == 0

        deuda = session.execute(
            text(
                "SELECT alumno, monto_centavos "
                "FROM v_deudas WHERE asistencia_id = :id"
            ),
            {"id": resultado.asistencia_id},
        ).one()
        assert deuda == (resultado.alumno, 14000)

    assert _contador(cashier_factory, sucursal_id) == 0


def test_deuda_congela_precio_del_grupo(
    cashier_factory: sessionmaker[Session],
) -> None:
    _sucursal_id, grupo_id, alumnos = _ref_ids(cashier_factory)
    sesion_id = _create_session(cashier_factory, grupo_id)

    with cashier_factory.begin() as session:
        grupo = session.get(Grupo, grupo_id)
        assert grupo is not None
        grupo.precio_centavos = 15000

    with cashier_factory() as session:
        resultado = registrar_deuda(
            session,
            sesion_id=sesion_id,
            alumno_id=alumnos[0],
        )

    assert resultado.monto_centavos == 15000

    with cashier_factory.begin() as session:
        grupo = session.get(Grupo, grupo_id)
        assert grupo is not None
        grupo.precio_centavos = 16000

    with cashier_factory() as session:
        monto = session.execute(
            text(
                "SELECT monto_centavos FROM v_deudas "
                "WHERE asistencia_id = :id"
            ),
            {"id": resultado.asistencia_id},
        ).scalar_one()
        assert monto == 15000


def test_deuda_rechaza_duplicado(
    cashier_factory: sessionmaker[Session],
) -> None:
    _sucursal_id, grupo_id, alumnos = _ref_ids(cashier_factory)
    sesion_id = _create_session(cashier_factory, grupo_id)

    with cashier_factory() as session:
        registrar_deuda(
            session,
            sesion_id=sesion_id,
            alumno_id=alumnos[0],
        )

    with cashier_factory() as session:
        with pytest.raises(CashierError, match="ya tiene asistencia"):
            registrar_deuda(
                session,
                sesion_id=sesion_id,
                alumno_id=alumnos[0],
            )

    assert _conteos(cashier_factory) == (0, 1)


def test_deuda_rechaza_sesion_cancelada(
    cashier_factory: sessionmaker[Session],
) -> None:
    _sucursal_id, grupo_id, alumnos = _ref_ids(cashier_factory)
    sesion_id = _create_session(
        cashier_factory,
        grupo_id,
        estado="cancelada",
    )

    with cashier_factory() as session:
        with pytest.raises(CashierError, match="cancelada"):
            registrar_deuda(
                session,
                sesion_id=sesion_id,
                alumno_id=alumnos[0],
            )

    assert _conteos(cashier_factory) == (0, 0)


def test_deuda_rechaza_alumno_no_inscrito(
    cashier_factory: sessionmaker[Session],
) -> None:
    _sucursal_id, grupo_id, _alumnos = _ref_ids(cashier_factory)
    sesion_id = _create_session(cashier_factory, grupo_id)

    with cashier_factory.begin() as session:
        alumno = Alumno(nombre="Alumno externo")
        session.add(alumno)
        session.flush()
        alumno_id = alumno.id

    with cashier_factory() as session:
        with pytest.raises(CashierError, match="no está inscrito"):
            registrar_deuda(
                session,
                sesion_id=sesion_id,
                alumno_id=alumno_id,
            )

    assert _conteos(cashier_factory) == (0, 0)


def test_deuda_rollback_si_falla_commit(
    cashier_factory: sessionmaker[Session],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _sucursal_id, grupo_id, alumnos = _ref_ids(cashier_factory)
    sesion_id = _create_session(cashier_factory, grupo_id)
    session = cashier_factory()

    def fallar_commit() -> None:
        raise RuntimeError("fallo simulado")

    monkeypatch.setattr(session, "commit", fallar_commit)
    try:
        with pytest.raises(RuntimeError, match="fallo simulado"):
            registrar_deuda(
                session,
                sesion_id=sesion_id,
                alumno_id=alumnos[0],
            )
    finally:
        session.close()

    assert _conteos(cashier_factory) == (0, 0)


def _preparar_cobro(
    factory: sessionmaker[Session],
) -> tuple[int, int, int]:
    sucursal_id, grupo_id, alumnos = _ref_ids(factory)
    sesion_id = _create_session(factory, grupo_id)
    return sucursal_id, sesion_id, alumnos[0]


def test_api_cobro_exitoso(
    cashier_app: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, factory = cashier_app
    sucursal_id, sesion_id, alumno_id = _preparar_cobro(factory)

    response = client.post(
        "/pos/cobrar",
        json={
            "sesion_id": sesion_id,
            "alumno_id": alumno_id,
            "metodo": "efectivo",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True
    assert data["pago"]["folio"] == "REF-0001"
    assert data["pago"]["monto_centavos"] == 14000
    assert data["pago"]["monto"] == "$140.00"
    assert data["pago"]["metodo"] == "efectivo"
    assert data["alumno"]["id"] == alumno_id
    assert data["alumno"]["estado"] == "pagado"
    assert data["resumen"]["pagados"] == 1
    assert data["resumen"]["pendientes"] == 34

    roster = client.get(
        f"/pos?sucursal_id={sucursal_id}"
        f"&grupo_id={data['pago']['grupo_id']}"
        f"&sesion_id={sesion_id}"
    )
    assert roster.status_code == 200
    assert re.search(
        rf'class="student-card"\s+data-alumno-id="{alumno_id}"'
        rf'\s+data-estado="pagado"',
        roster.text,
    )


def test_api_cobro_duplicado(
    cashier_app: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, factory = cashier_app
    _, sesion_id, alumno_id = _preparar_cobro(factory)
    payload = {
        "sesion_id": sesion_id,
        "alumno_id": alumno_id,
        "metodo": "efectivo",
    }

    assert client.post("/pos/cobrar", json=payload).status_code == 200
    response = client.post("/pos/cobrar", json=payload)

    assert response.status_code == 409
    assert "ya tiene asistencia" in response.json()["detail"]


def test_api_cobro_sesion_cancelada(
    cashier_app: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, factory = cashier_app
    sucursal_id, grupo_id, alumnos = _ref_ids(factory)
    sesion_id = _create_session(factory, grupo_id, estado="cancelada")

    response = client.post(
        "/pos/cobrar",
        json={
            "sesion_id": sesion_id,
            "alumno_id": alumnos[0],
            "metodo": "efectivo",
        },
    )

    assert response.status_code == 409
    assert "cancelada" in response.json()["detail"]
    assert _conteos(factory) == (0, 0)
    assert _contador(factory, sucursal_id) == 0


def test_api_cobro_metodo_invalido(
    cashier_app: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, factory = cashier_app
    _, sesion_id, alumno_id = _preparar_cobro(factory)

    response = client.post(
        "/pos/cobrar",
        json={
            "sesion_id": sesion_id,
            "alumno_id": alumno_id,
            "metodo": "tarjeta",
        },
    )

    assert response.status_code == 422
    assert _conteos(factory) == (0, 0)


def test_api_cobro_metodo_por_defecto(
    cashier_app: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, factory = cashier_app
    _, sesion_id, alumno_id = _preparar_cobro(factory)

    response = client.post(
        "/pos/cobrar",
        json={
            "sesion_id": sesion_id,
            "alumno_id": alumno_id,
        },
    )

    assert response.status_code == 200
    assert response.json()["pago"]["metodo"] == "efectivo"


def test_api_deuda_exitosa(
    cashier_app: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, factory = cashier_app
    sucursal_id, sesion_id, alumno_id = _preparar_cobro(factory)

    response = client.post(
        "/pos/asistio-sin-pagar",
        json={"sesion_id": sesion_id, "alumno_id": alumno_id},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True
    assert data["deuda"]["alumno_id"] == alumno_id
    assert data["deuda"]["monto_centavos"] == 14000
    assert data["deuda"]["monto"] == "$140.00"
    assert data["alumno"]["estado"] == "deuda"
    assert data["resumen"]["deudas"] == 1
    assert data["resumen"]["pendientes"] == 34
    assert _conteos(factory) == (0, 1)

    roster = client.get(
        f"/pos?sucursal_id={sucursal_id}"
        f"&grupo_id={data['deuda']['grupo_id']}"
        f"&sesion_id={sesion_id}"
    )
    assert roster.status_code == 200
    assert re.search(
        rf'class="student-card"\s+data-alumno-id="{alumno_id}"'
        rf'\s+data-estado="deuda"',
        roster.text,
    )


def test_api_deuda_duplicada(
    cashier_app: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, factory = cashier_app
    _, sesion_id, alumno_id = _preparar_cobro(factory)
    payload = {"sesion_id": sesion_id, "alumno_id": alumno_id}

    assert client.post("/pos/asistio-sin-pagar", json=payload).status_code == 200
    response = client.post("/pos/asistio-sin-pagar", json=payload)

    assert response.status_code == 409
    assert "ya tiene asistencia" in response.json()["detail"]
    assert _conteos(factory) == (0, 1)


def test_api_deuda_sesion_cancelada(
    cashier_app: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, factory = cashier_app
    sucursal_id, grupo_id, alumnos = _ref_ids(factory)
    sesion_id = _create_session(factory, grupo_id, estado="cancelada")

    response = client.post(
        "/pos/asistio-sin-pagar",
        json={"sesion_id": sesion_id, "alumno_id": alumnos[0]},
    )

    assert response.status_code == 409
    assert "cancelada" in response.json()["detail"]
    assert _conteos(factory) == (0, 0)
    assert _contador(factory, sucursal_id) == 0
