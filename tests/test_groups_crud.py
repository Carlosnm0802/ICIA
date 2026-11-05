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
    BloqueGrupo,
    Grupo,
    Maestro,
    Pago,
    Sesion,
    Sucursal,
)
from app.services import cashier as cashier_service
from app.services import catalog
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
def catalog_app(
    tmp_path: Path,
) -> Iterator[tuple[TestClient, sessionmaker[Session]]]:
    database_path = tmp_path / "catalog.db"
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


def _sucursal_id(factory: sessionmaker[Session], prefijo: str = "REF") -> int:
    with factory() as session:
        sucursal = session.scalar(
            select(Sucursal).where(Sucursal.prefijo_folio == prefijo)
        )
        assert sucursal is not None
        return sucursal.id


def _maestro_ids(factory: sessionmaker[Session]) -> list[int]:
    with factory() as session:
        return list(session.scalars(select(Maestro.id).order_by(Maestro.id)))


def _grupo_form(
    sucursal_id: int,
    maestros: list[int],
    **overrides: object,
) -> dict[str, object]:
    datos: dict[str, object] = {
        "sucursal_id": sucursal_id,
        "nombre": "Lunes 4-6 PM",
        "dias_semana": ["Lunes", "Miércoles"],
        "hora_inicio": "16:00",
        "hora_fin": "18:00",
        "precio": "140.00",
        "bloque_materia": ["ingles", "robotica"],
        "bloque_duracion": [60, 60],
        "bloque_maestro": [maestros[0], maestros[-1]],
    }
    datos.update(overrides)
    return datos


def test_sucursales_lista_y_alta(
    catalog_app: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, _ = catalog_app

    respuesta = client.get("/sucursales")
    assert respuesta.status_code == 200
    assert "ICIA" in respuesta.text
    assert "El Refugio" in respuesta.text
    assert "REF" in respuesta.text

    creada = client.post(
        "/sucursales",
        data={
            "nombre": "Chapala",
            "prefijo_folio": "cha",
            "direccion": "Centro",
            "telefono": "333-000-0000",
        },
        follow_redirects=False,
    )
    assert creada.status_code == 303

    listado = client.get("/sucursales")
    assert "Chapala" in listado.text
    assert "CHA" in listado.text


def test_sucursal_rechaza_nombre_y_prefijo_duplicados(
    catalog_app: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, _ = catalog_app

    respuesta = client.post(
        "/sucursales",
        data={"nombre": "el refugio", "prefijo_folio": "NUE1"},
        follow_redirects=False,
    )
    assert respuesta.status_code == 303
    assert "error=" in respuesta.headers["location"]

    respuesta = client.post(
        "/sucursales",
        data={"nombre": "Nueva", "prefijo_folio": "ref"},
        follow_redirects=False,
    )
    assert respuesta.status_code == 303
    assert "error=" in respuesta.headers["location"]


def test_sucursal_prefijo_bloqueado_con_pagos(
    catalog_app: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, factory = catalog_app
    sucursal_id = _sucursal_id(factory)

    with factory.begin() as session:
        grupo = session.scalar(
            select(Grupo).where(Grupo.sucursal_id == sucursal_id)
        )
        assert grupo is not None
        sesion = Sesion(
            grupo_id=grupo.id,
            fecha=date.today().isoformat(),
            estado="programada",
        )
        session.add(sesion)
        session.flush()
        sesion_id = sesion.id
        alumno_id = session.scalar(select(Alumno.id).limit(1))
        assert alumno_id is not None

    with factory() as session:
        cashier_service.cobrar_sesion(
            session,
            sesion_id=sesion_id,
            alumno_id=alumno_id,
            metodo="efectivo",
        )

    with factory() as session:
        with pytest.raises(catalog.CatalogError, match="prefijo"):
            catalog.actualizar_sucursal(
                session,
                sucursal_id,
                nombre="El Refugio",
                prefijo="RFX",
            )

    formulario = client.get(f"/sucursales/{sucursal_id}/editar")
    assert "readonly" in formulario.text

    with factory() as session:
        assert (
            catalog.sucursal_tiene_pagos(session, sucursal_id) is True
        )


def test_sucursal_no_se_desactiva_con_grupos_activos(
    catalog_app: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, factory = catalog_app
    sucursal_id = _sucursal_id(factory)

    respuesta = client.post(
        f"/sucursales/{sucursal_id}/estado",
        data={"activa": "0"},
        follow_redirects=False,
    )
    assert respuesta.status_code == 303
    assert "error=" in respuesta.headers["location"]

    with factory() as session:
        sucursal = session.get(Sucursal, sucursal_id)
        assert sucursal is not None
        assert sucursal.activa == 1


def test_crear_grupo_desde_formulario(
    catalog_app: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, factory = catalog_app
    sucursal_id = _sucursal_id(factory)
    maestros = _maestro_ids(factory)

    respuesta = client.post(
        "/grupos",
        data=_grupo_form(sucursal_id, maestros),
        follow_redirects=False,
    )
    assert respuesta.status_code == 303
    assert respuesta.headers["location"].startswith("/grupos?")

    with factory() as session:
        grupo = session.scalar(
            select(Grupo).where(Grupo.nombre == "Lunes 4-6 PM")
        )
        assert grupo is not None
        assert grupo.dias_semana == "Lunes,Miércoles"
        assert grupo.precio_centavos == 14000
        bloques = list(
            session.scalars(
                select(BloqueGrupo)
                .where(BloqueGrupo.grupo_id == grupo.id)
                .order_by(BloqueGrupo.orden)
            )
        )
        assert [bloque.materia for bloque in bloques] == [
            "ingles",
            "robotica",
        ]
        assert [bloque.duracion_minutos for bloque in bloques] == [60, 60]


def test_crear_grupo_valida_duracion_exacta(
    catalog_app: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, factory = catalog_app
    sucursal_id = _sucursal_id(factory)
    maestros = _maestro_ids(factory)

    datos = _grupo_form(sucursal_id, maestros)
    datos["bloque_duracion"] = [60, 45]
    respuesta = client.post(
        "/grupos",
        data=datos,
        follow_redirects=False,
    )
    assert respuesta.status_code == 303
    assert "error=" in respuesta.headers["location"]

    with factory() as session:
        assert (
            session.scalar(
                select(Grupo).where(Grupo.nombre == "Lunes 4-6 PM")
            )
            is None
        )


def test_crear_grupo_rechaza_materia_y_maestro_invalidos(
    catalog_app: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, factory = catalog_app
    sucursal_id = _sucursal_id(factory)
    maestros = _maestro_ids(factory)

    datos = _grupo_form(sucursal_id, maestros)
    datos["bloque_materia"] = ["ingles", "historia"]
    respuesta = client.post("/grupos", data=datos, follow_redirects=False)
    assert "error=" in respuesta.headers["location"]

    datos = _grupo_form(sucursal_id, maestros)
    datos["bloque_maestro"] = [maestros[0], 999_999]
    respuesta = client.post("/grupos", data=datos, follow_redirects=False)
    assert "error=" in respuesta.headers["location"]


def test_editar_grupo_reemplaza_bloques_y_precio(
    catalog_app: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, factory = catalog_app
    sucursal_id = _sucursal_id(factory)
    maestros = _maestro_ids(factory)

    with factory() as session:
        grupo = session.scalar(
            select(Grupo).where(Grupo.sucursal_id == sucursal_id)
        )
        assert grupo is not None
        grupo_id = grupo.id

    datos = _grupo_form(
        sucursal_id,
        maestros,
        nombre="Jueves 3-5 PM",
        dias_semana=["Jueves"],
        hora_inicio="15:00",
        hora_fin="17:00",
        precio="150",
        bloque_materia=["robotica", "ingles"],
        bloque_duracion=[60, 60],
        bloque_maestro=[maestros[-1], maestros[0]],
    )
    respuesta = client.post(
        f"/grupos/{grupo_id}",
        data=datos,
        follow_redirects=False,
    )
    assert respuesta.status_code == 303
    assert "error=" not in respuesta.headers["location"]

    with factory() as session:
        grupo = session.get(Grupo, grupo_id)
        assert grupo is not None
        assert grupo.precio_centavos == 15000
        assert grupo.dias_semana == "Jueves"
        bloques = list(
            session.scalars(
                select(BloqueGrupo)
                .where(BloqueGrupo.grupo_id == grupo_id)
                .order_by(BloqueGrupo.orden)
            )
        )
        assert [bloque.materia for bloque in bloques] == [
            "robotica",
            "ingles",
        ]


def test_cambio_precio_no_altera_pagos_anteriores(
    catalog_app: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, factory = catalog_app
    sucursal_id = _sucursal_id(factory)

    with factory.begin() as session:
        grupo = session.scalar(
            select(Grupo).where(Grupo.sucursal_id == sucursal_id)
        )
        assert grupo is not None
        grupo_id = grupo.id
        sesion = Sesion(
            grupo_id=grupo_id,
            fecha=date.today().isoformat(),
            estado="programada",
        )
        session.add(sesion)
        session.flush()
        sesion_id = sesion.id

    with factory() as session:
        alumno_id = session.scalar(select(Alumno.id).limit(1))
    assert alumno_id is not None

    with factory() as session:
        resultado = cashier_service.cobrar_sesion(
            session,
            sesion_id=sesion_id,
            alumno_id=alumno_id,
            metodo="efectivo",
        )
        pago_id = resultado.pago_id

    maestros = _maestro_ids(factory)
    datos = _grupo_form(
        sucursal_id,
        maestros,
        nombre="Jueves 3-5 PM",
        dias_semana=["Jueves"],
        hora_inicio="15:00",
        hora_fin="17:00",
        precio="200.00",
        bloque_materia=["ingles", "robotica"],
        bloque_duracion=[60, 60],
        bloque_maestro=[maestros[0], maestros[-1]],
    )
    respuesta = client.post(
        f"/grupos/{grupo_id}",
        data=datos,
        follow_redirects=False,
    )
    assert respuesta.status_code == 303

    with factory() as session:
        pago = session.get(Pago, resultado.pago_id)
        assert pago is not None
        assert pago.monto_centavos == 14000


def test_desactivar_grupo_lo_oculta_del_pos(
    catalog_app: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, factory = catalog_app
    sucursal_id = _sucursal_id(factory)

    with factory() as session:
        grupo = session.scalar(
            select(Grupo).where(Grupo.sucursal_id == sucursal_id)
        )
        assert grupo is not None
        grupo_id = grupo.id

    respuesta = client.post(
        f"/grupos/{grupo_id}/estado",
        data={"activo": "0"},
        follow_redirects=False,
    )
    assert respuesta.status_code == 303

    pos = client.get(f"/pos?sucursal_id={sucursal_id}")
    assert pos.status_code == 200
    assert "Jueves 3-5 PM" not in pos.text

    listado = client.get("/grupos?inactivos=1")
    assert "Inactivo" in listado.text

    reactivar = client.post(
        f"/grupos/{grupo_id}/estado",
        data={"activo": "1"},
        follow_redirects=False,
    )
    assert reactivar.status_code == 303

    pos = client.get(f"/pos?sucursal_id={sucursal_id}")
    assert "Jueves 3-5 PM" in pos.text


def test_formularios_muestran_identidad_y_sin_cdn(
    catalog_app: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, factory = catalog_app
    sucursal_id = _sucursal_id(factory)

    for ruta in (
        "/sucursales",
        "/sucursales/nueva",
        "/grupos",
        "/grupos/nuevo",
    ):
        respuesta = client.get(ruta)
        assert respuesta.status_code == 200
        assert "ICIA" in respuesta.text
        for dominio in ("unpkg", "cdnjs", "jsdelivr", "googleapis"):
            assert dominio not in respuesta.text

    with factory() as session:
        grupo = session.scalar(
            select(Grupo).where(Grupo.sucursal_id == sucursal_id)
        )
        assert grupo is not None
        editar = client.get(f"/grupos/{grupo.id}/editar")
        assert editar.status_code == 200
        assert "140.00" in editar.text
        assert "Inglés" in editar.text
        assert "Robótica" in editar.text
