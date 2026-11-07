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
from app.models import Grupo, Maestro, Sesion, SesionMaestro, Sucursal
from app.services import payroll
from app.services import sessions as sessions_service
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
def payroll_app(
    tmp_path: Path,
) -> Iterator[tuple[TestClient, sessionmaker[Session]]]:
    database_path = tmp_path / "payroll.db"
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


def _maestro_ids(factory: sessionmaker[Session]) -> list[int]:
    with factory() as session:
        return list(session.scalars(select(Maestro.id).order_by(Maestro.id)))


def _crear_maestro(
    factory: sessionmaker[Session],
    nombre: str,
    activo: int = 1,
) -> int:
    with factory() as session:
        maestro = Maestro(nombre=nombre, activo=activo)
        session.add(maestro)
        session.commit()
        return maestro.id


def _crear_grupo(
    factory: sessionmaker[Session],
    sucursal_id: int,
    nombre: str,
) -> int:
    with factory() as session:
        grupo = Grupo(
            sucursal_id=sucursal_id,
            nombre=nombre,
            dias_semana="Lunes",
            hora_inicio="09:00",
            hora_fin="11:00",
            precio_centavos=14000,
        )
        session.add(grupo)
        session.commit()
        return grupo.id


def _crear_sesion(
    factory: sessionmaker[Session],
    grupo_id: int,
    fecha: date,
    *,
    estado: str = "programada",
    es_extra: int = 0,
    maestro_ids: tuple[int, ...] = (),
) -> int:
    with factory() as session:
        sesion = Sesion(
            grupo_id=grupo_id,
            fecha=fecha.isoformat(),
            estado=estado,
            es_extra=es_extra,
        )
        session.add(sesion)
        session.flush()
        for maestro_id in maestro_ids:
            session.add(
                SesionMaestro(
                    sesion_id=sesion.id,
                    maestro_id=maestro_id,
                    pagado=0,
                )
            )
        session.commit()
        return sesion.id


def _marca_id(
    factory: sessionmaker[Session],
    sesion_id: int,
    maestro_id: int,
) -> int:
    with factory() as session:
        marca = session.scalar(
            select(SesionMaestro).where(
                SesionMaestro.sesion_id == sesion_id,
                SesionMaestro.maestro_id == maestro_id,
            )
        )
        assert marca is not None
        return marca.id


def _marca(factory: sessionmaker[Session], marca_id: int) -> SesionMaestro:
    with factory() as session:
        marca = session.get(SesionMaestro, marca_id)
        assert marca is not None
        session.expunge(marca)
        return marca


def test_listar_honorarios_excluye_futuras_y_canceladas(
    payroll_app: tuple[TestClient, sessionmaker[Session]],
) -> None:
    _, factory = payroll_app
    sucursal_id, grupo_id = _ref_ids(factory)
    maestros = _maestro_ids(factory)
    hoy = date.today()

    sesion_hoy = _crear_sesion(
        factory,
        grupo_id,
        hoy,
        maestro_ids=(maestros[0], maestros[1]),
    )
    _crear_sesion(
        factory,
        grupo_id,
        hoy + timedelta(days=1),
        maestro_ids=(maestros[0],),
    )
    grupo_cancelado_id = _crear_grupo(
        factory,
        sucursal_id,
        "Grupo Cancelado",
    )
    _crear_sesion(
        factory,
        grupo_cancelado_id,
        hoy,
        estado="cancelada",
        maestro_ids=(maestros[0],),
    )

    with factory() as session:
        resumen = payroll.listar_honorarios(
            session,
            *payroll.rango_corte(hoy),
            hoy=hoy,
        )

    assert resumen.total == 2
    assert resumen.total_sesiones == 1
    assert resumen.pendientes == 2
    assert resumen.pagadas == 0
    assert {item.sesion_id for item in resumen.items} == {sesion_hoy}


def test_listar_honorarios_filtra_por_sucursal_maestro_y_estado(
    payroll_app: tuple[TestClient, sessionmaker[Session]],
) -> None:
    _, factory = payroll_app
    sucursal_ref_id, grupo_ref_id = _ref_ids(factory)
    maestros = _maestro_ids(factory)
    hoy = date.today()

    with factory() as session:
        sucursal_tot = session.scalar(
            select(Sucursal).where(Sucursal.prefijo_folio == "TOT")
        )
        assert sucursal_tot is not None
        sucursal_tot_id = sucursal_tot.id

    grupo_tot_id = _crear_grupo(factory, sucursal_tot_id, "Grupo TOT")
    sesion_ref = _crear_sesion(
        factory,
        grupo_ref_id,
        hoy,
        maestro_ids=(maestros[0],),
    )
    sesion_tot = _crear_sesion(
        factory,
        grupo_tot_id,
        hoy,
        maestro_ids=(maestros[1],),
    )
    marca_ref_id = _marca_id(factory, sesion_ref, maestros[0])

    with factory() as session:
        marca = session.get(SesionMaestro, marca_ref_id)
        assert marca is not None
        marca.pagado = 1
        marca.fecha_pago = "2026-11-06 15:00:00"
        session.commit()

    with factory() as session:
        resumen_ref = payroll.listar_honorarios(
            session,
            *payroll.rango_corte(hoy),
            hoy=hoy,
            sucursal_id=sucursal_ref_id,
        )
        resumen_tot = payroll.listar_honorarios(
            session,
            *payroll.rango_corte(hoy),
            hoy=hoy,
            sucursal_id=sucursal_tot_id,
        )
        resumen_maestro = payroll.listar_honorarios(
            session,
            *payroll.rango_corte(hoy),
            hoy=hoy,
            maestro_id=maestros[1],
        )
        resumen_pagados = payroll.listar_honorarios(
            session,
            *payroll.rango_corte(hoy),
            hoy=hoy,
            estado="pagado",
        )
        resumen_pendientes = payroll.listar_honorarios(
            session,
            *payroll.rango_corte(hoy),
            hoy=hoy,
            estado="pendiente",
        )

    assert [item.sesion_id for item in resumen_ref.items] == [sesion_ref]
    assert [item.sesion_id for item in resumen_tot.items] == [sesion_tot]
    assert [item.sesion_id for item in resumen_maestro.items] == [sesion_tot]
    assert [item.sesion_id for item in resumen_pagados.items] == [sesion_ref]
    assert [item.sesion_id for item in resumen_pendientes.items] == [sesion_tot]


def test_marcar_honorarios_lote_pagado_y_pendiente(
    payroll_app: tuple[TestClient, sessionmaker[Session]],
) -> None:
    _, factory = payroll_app
    _, grupo_id = _ref_ids(factory)
    maestros = _maestro_ids(factory)
    hoy = date.today()
    sesion_id = _crear_sesion(
        factory,
        grupo_id,
        hoy,
        maestro_ids=(maestros[0], maestros[1]),
    )
    marca_ids = [
        _marca_id(factory, sesion_id, maestros[0]),
        _marca_id(factory, sesion_id, maestros[1]),
    ]

    with factory() as session:
        cambios = payroll.marcar_honorarios_lote(
            session,
            marca_ids,
            pagado=True,
            hoy=hoy,
        )
    assert cambios == 2

    marcas_pagadas = [_marca(factory, marca_id) for marca_id in marca_ids]
    assert all(marca.pagado == 1 for marca in marcas_pagadas)
    assert all(marca.fecha_pago is not None for marca in marcas_pagadas)
    fechas_originales = {marca.id: marca.fecha_pago for marca in marcas_pagadas}

    with factory() as session:
        cambios_repetidos = payroll.marcar_honorarios_lote(
            session,
            marca_ids,
            pagado=True,
            hoy=hoy,
        )
    assert cambios_repetidos == 0
    assert {
        marca.id: marca.fecha_pago for marca in marcas_pagadas
    } == fechas_originales

    with factory() as session:
        cambios_pendiente = payroll.marcar_honorarios_lote(
            session,
            marca_ids,
            pagado=False,
            hoy=hoy,
        )
    assert cambios_pendiente == 2

    marcas_pendientes = [_marca(factory, marca_id) for marca_id in marca_ids]
    assert all(marca.pagado == 0 for marca in marcas_pendientes)
    assert all(marca.fecha_pago is None for marca in marcas_pendientes)


def test_marcar_honorarios_lote_rechaza_lote_invalido_sin_cambios(
    payroll_app: tuple[TestClient, sessionmaker[Session]],
) -> None:
    _, factory = payroll_app
    sucursal_id, grupo_id = _ref_ids(factory)
    maestros = _maestro_ids(factory)
    hoy = date.today()
    sesion_valida = _crear_sesion(
        factory,
        grupo_id,
        hoy,
        maestro_ids=(maestros[0],),
    )
    marca_valida_id = _marca_id(factory, sesion_valida, maestros[0])

    grupo_cancelado_id = _crear_grupo(
        factory,
        sucursal_id,
        "Grupo Cancelado Inválido",
    )
    sesion_cancelada = _crear_sesion(
        factory,
        grupo_cancelado_id,
        hoy,
        estado="cancelada",
        maestro_ids=(maestros[0],),
    )
    marca_cancelada_id = _marca_id(factory, sesion_cancelada, maestros[0])

    sesion_futura = _crear_sesion(
        factory,
        grupo_id,
        hoy + timedelta(days=1),
        maestro_ids=(maestros[0],),
    )
    marca_futura_id = _marca_id(factory, sesion_futura, maestros[0])

    with factory() as session:
        with pytest.raises(payroll.PayrollError, match="al menos"):
            payroll.marcar_honorarios_lote(session, [], pagado=True, hoy=hoy)

    with factory() as session:
        with pytest.raises(payroll.PayrollError, match="no existen"):
            payroll.marcar_honorarios_lote(
                session,
                [marca_valida_id, 999999],
                pagado=True,
                hoy=hoy,
            )

    with factory() as session:
        with pytest.raises(payroll.PayrollError, match="cancelada"):
            payroll.marcar_honorarios_lote(
                session,
                [marca_valida_id, marca_cancelada_id],
                pagado=True,
                hoy=hoy,
            )

    with factory() as session:
        with pytest.raises(payroll.PayrollError, match="futura"):
            payroll.marcar_honorarios_lote(
                session,
                [marca_valida_id, marca_futura_id],
                pagado=True,
                hoy=hoy,
            )

    assert _marca(factory, marca_valida_id).pagado == 0
    assert _marca(factory, marca_cancelada_id).pagado == 0
    assert _marca(factory, marca_futura_id).pagado == 0


def test_pantalla_pago_maestros_muestra_navegacion(
    payroll_app: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, _ = payroll_app

    respuesta = client.get("/pagos-maestros")
    assert respuesta.status_code == 200
    assert "ICIA" in respuesta.text
    assert "Pago a maestros" in respuesta.text
    assert "Marcas en el corte" in respuesta.text
    assert "No hay marcas de pago en este periodo." in respuesta.text
    assert 'href="/pagos-maestros"' in respuesta.text
    for dominio in ("unpkg", "cdnjs", "jsdelivr", "googleapis"):
        assert dominio not in respuesta.text


def test_pantalla_marca_y_desmarca_pagos(
    payroll_app: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, factory = payroll_app
    _, grupo_id = _ref_ids(factory)
    maestros = _maestro_ids(factory)
    hoy = date.today()
    sesion_id = _crear_sesion(
        factory,
        grupo_id,
        hoy,
        maestro_ids=(maestros[0],),
    )
    marca_id = _marca_id(factory, sesion_id, maestros[0])
    fechas = {
        "desde": hoy.isoformat(),
        "hasta": hoy.isoformat(),
        "estado": "todos",
    }

    listado = client.get("/pagos-maestros")
    assert "Maestro de Inglés" in listado.text
    assert "Pendiente" in listado.text

    marcado = client.post(
        "/pagos-maestros/marcar",
        data={**fechas, "marca_ids": str(marca_id), "pagado": "1"},
        follow_redirects=False,
    )
    assert marcado.status_code == 303
    assert "actualizados=1" in marcado.headers["location"]

    actualizado = client.get(marcado.headers["location"])
    assert "Se actualizó 1 marca de pago." in actualizado.text
    assert "Pagado" in actualizado.text
    assert _marca(factory, marca_id).fecha_pago is not None

    desmarcado = client.post(
        "/pagos-maestros/marcar",
        data={**fechas, "marca_ids": str(marca_id), "pagado": "0"},
        follow_redirects=False,
    )
    assert desmarcado.status_code == 303
    assert "actualizados=1" in desmarcado.headers["location"]

    pendiente = client.get(desmarcado.headers["location"])
    assert "Pendiente" in pendiente.text
    assert _marca(factory, marca_id).fecha_pago is None

    sin_seleccion = client.post(
        "/pagos-maestros/marcar",
        data={**fechas, "pagado": "1"},
        follow_redirects=False,
    )
    assert sin_seleccion.status_code == 303
    assert "error=" in sin_seleccion.headers["location"]


def test_corte_refleja_suplencia_liquidada(
    payroll_app: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, factory = payroll_app
    _, grupo_id = _ref_ids(factory)
    maestros = _maestro_ids(factory)
    hoy = date.today()
    sesion_id = _crear_sesion(
        factory,
        grupo_id,
        hoy,
        maestro_ids=(maestros[0], maestros[1]),
    )
    marca_titular_id = _marca_id(factory, sesion_id, maestros[0])
    suplente_id = _crear_maestro(factory, "Suplente de Honorarios")

    with factory() as session:
        sessions_service.sustituir_maestro_sesion(
            session,
            grupo_id,
            sesion_id,
            marca_titular_id,
            suplente_id,
        )

    listado = client.get("/pagos-maestros")
    assert "Suplente de Honorarios" in listado.text
    assert "Suplente" in listado.text
    assert "Titular: Maestro de Inglés" in listado.text

    filtros = {
        "desde": hoy.isoformat(),
        "hasta": hoy.isoformat(),
        "estado": "todos",
    }
    marcado = client.post(
        "/pagos-maestros/marcar",
        data={**filtros, "marca_ids": str(marca_titular_id), "pagado": "1"},
        follow_redirects=False,
    )
    assert marcado.status_code == 303
    assert "actualizados=1" in marcado.headers["location"]

    pagados = client.get(
        f"/pagos-maestros?desde={hoy.isoformat()}&hasta={hoy.isoformat()}"
        "&estado=pagado"
    )
    assert "Suplente de Honorarios" in pagados.text
    assert "Pagado" in pagados.text
    assert _marca(factory, marca_titular_id).maestro_id == suplente_id
