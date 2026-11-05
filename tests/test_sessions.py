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
from app.models import Alumno, Asistencia, BloqueGrupo, Grupo, Maestro, Sesion, SesionMaestro, Sucursal
from app.services import cashier as cashier_service
from app.services import catalog
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
def sessions_app(
    tmp_path: Path,
) -> Iterator[tuple[TestClient, sessionmaker[Session]]]:
    database_path = tmp_path / "sessions.db"
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


def test_generar_sesiones_horizonte_y_sesion_maestros(
    sessions_app: tuple[TestClient, sessionmaker[Session]],
) -> None:
    _, factory = sessions_app
    _, grupo_id = _ref_ids(factory)
    base_lunes = date(2026, 11, 2)  # Lunes

    with factory() as session:
        grupo = session.get(Grupo, grupo_id)
        assert grupo is not None
        # Jueves en 8 semanas (del 2-Nov al 28-Dic) -> 8 o 9 jueves
        creadas = sessions_service.generar_sesiones_grupo(
            session, grupo, hoy=base_lunes, semanas=8
        )
        session.commit()
        assert creadas >= 8

        sesiones = list(
            session.scalars(
                select(Sesion)
                .where(Sesion.grupo_id == grupo.id)
                .order_by(Sesion.fecha)
            )
        )
        for s in sesiones:
            d = date.fromisoformat(s.fecha)
            assert d.weekday() == 3  # Jueves
            assert s.estado == "programada"
            assert s.es_extra == 0

            maestros_sesion = list(
                session.scalars(
                    select(SesionMaestro.maestro_id).where(
                        SesionMaestro.sesion_id == s.id
                    )
                )
            )
            assert len(maestros_sesion) == 2
            assert len(set(maestros_sesion)) == 2


def test_generacion_es_idempotente(
    sessions_app: tuple[TestClient, sessionmaker[Session]],
) -> None:
    _, factory = sessions_app
    _, grupo_id = _ref_ids(factory)
    base_lunes = date(2026, 11, 2)

    with factory() as session:
        grupo = session.get(Grupo, grupo_id)
        assert grupo is not None
        creadas_primera = sessions_service.generar_sesiones_grupo(
            session, grupo, hoy=base_lunes, semanas=8
        )
        session.commit()
        assert creadas_primera > 0

        creadas_segunda = sessions_service.generar_sesiones_grupo(
            session, grupo, hoy=base_lunes, semanas=8
        )
        session.commit()
        assert creadas_segunda == 0


def test_no_genera_para_grupo_o_sucursal_inactivos(
    sessions_app: tuple[TestClient, sessionmaker[Session]],
) -> None:
    _, factory = sessions_app
    sucursal_id, grupo_id = _ref_ids(factory)

    with factory() as session:
        grupo = session.get(Grupo, grupo_id)
        assert grupo is not None
        grupo.activo = 0
        session.commit()

        creadas = sessions_service.generar_sesiones_grupo(session, grupo)
        assert creadas == 0

        grupo.activo = 1
        sucursal = session.get(Sucursal, sucursal_id)
        assert sucursal is not None
        sucursal.activa = 0
        session.commit()

        creadas_suc_inactiva = sessions_service.generar_sesiones_grupo(session, grupo)
        assert creadas_suc_inactiva == 0


def test_creacion_de_grupo_genera_sesiones_automaticamente(
    sessions_app: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, factory = sessions_app
    sucursal_id, _ = _ref_ids(factory)
    maestros = _maestro_ids(factory)

    datos = {
        "sucursal_id": sucursal_id,
        "nombre": "Sábados Matutinos",
        "dias_semana": ["Sábado"],
        "hora_inicio": "09:00",
        "hora_fin": "11:00",
        "precio": "120.00",
        "bloque_materia": ["ingles", "robotica"],
        "bloque_duracion": [60, 60],
        "bloque_maestro": [maestros[0], maestros[1]],
    }
    resp = client.post("/grupos", data=datos, follow_redirects=False)
    assert resp.status_code == 303

    with factory() as session:
        grupo = session.scalar(
            select(Grupo).where(Grupo.nombre == "Sábados Matutinos")
        )
        assert grupo is not None
        sesiones = list(
            session.scalars(select(Sesion).where(Sesion.grupo_id == grupo.id))
        )
        assert len(sesiones) >= 8
        for s in sesiones:
            assert date.fromisoformat(s.fecha).weekday() == 5  # Sábado


def test_edicion_de_horario_sincroniza_sesiones_futuras(
    sessions_app: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, factory = sessions_app
    sucursal_id, _ = _ref_ids(factory)
    maestros = _maestro_ids(factory)

    # 1. Crear grupo en Lunes
    datos = {
        "sucursal_id": sucursal_id,
        "nombre": "Grupo Sincronizable",
        "dias_semana": ["Lunes"],
        "hora_inicio": "16:00",
        "hora_fin": "18:00",
        "precio": "140.00",
        "bloque_materia": ["ingles", "robotica"],
        "bloque_duracion": [60, 60],
        "bloque_maestro": [maestros[0], maestros[1]],
    }
    client.post("/grupos", data=datos, follow_redirects=False)

    with factory() as session:
        grupo = session.scalar(
            select(Grupo).where(Grupo.nombre == "Grupo Sincronizable")
        )
        assert grupo is not None
        grupo_id = grupo.id
        sesiones_lunes = list(
            session.scalars(select(Sesion).where(Sesion.grupo_id == grupo_id))
        )
        assert len(sesiones_lunes) >= 8

    # 2. Modificar a Martes
    datos_actualizados = dict(
        datos,
        dias_semana=["Martes"],
    )
    client.post(f"/grupos/{grupo_id}", data=datos_actualizados, follow_redirects=False)

    with factory() as session:
        sesiones_nuevas = list(
            session.scalars(
                select(Sesion)
                .where(Sesion.grupo_id == grupo_id)
                .order_by(Sesion.fecha)
            )
        )
        assert len(sesiones_nuevas) >= 8
        for s in sesiones_nuevas:
            assert date.fromisoformat(s.fecha).weekday() == 1  # Martes


def test_sincronizacion_conserva_sesion_con_asistencia(
    sessions_app: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, factory = sessions_app
    sucursal_id, _ = _ref_ids(factory)
    maestros = _maestro_ids(factory)

    with factory() as session:
        grupo = catalog.crear_grupo(
            session,
            sucursal_id=sucursal_id,
            nombre="Grupo Con Asistencia",
            dias_semana=["Lunes"],
            hora_inicio="16:00",
            hora_fin="18:00",
            precio="140.00",
            bloques=[
                catalog.BloqueForm(
                    materia="ingles", orden=1, duracion_minutos=60, maestro_id=maestros[0]
                ),
                catalog.BloqueForm(
                    materia="robotica", orden=2, duracion_minutos=60, maestro_id=maestros[1]
                ),
            ],
        )
        grupo_id = grupo.id

    with factory() as session:
        primera_sesion = session.scalar(
            select(Sesion)
            .where(Sesion.grupo_id == grupo_id)
            .order_by(Sesion.fecha.asc())
            .limit(1)
        )
        assert primera_sesion is not None
        sesion_preservar_id = primera_sesion.id
        fecha_preservar = primera_sesion.fecha

        alumno_id = session.scalar(select(Alumno.id).limit(1))
        assert alumno_id is not None
        session.add(
            Asistencia(
                sesion_id=sesion_preservar_id,
                alumno_id=alumno_id,
                estado="asistio",
                es_reposicion=0,
            )
        )
        session.commit()

    # Actualizar horario a Viernes
    client.post(
        f"/grupos/{grupo_id}",
        data={
            "sucursal_id": sucursal_id,
            "nombre": "Grupo Con Asistencia",
            "dias_semana": ["Viernes"],
            "hora_inicio": "16:00",
            "hora_fin": "18:00",
            "precio": "140.00",
            "bloque_materia": ["ingles", "robotica"],
            "bloque_duracion": [60, 60],
            "bloque_maestro": [maestros[0], maestros[1]],
        },
        follow_redirects=False,
    )

    with factory() as session:
        # La sesión con asistencia se conservó
        sesion_conservada = session.get(Sesion, sesion_preservar_id)
        assert sesion_conservada is not None
        assert sesion_conservada.fecha == fecha_preservar

        # Y se generaron las sesiones de los viernes
        sesiones_viernes = list(
            session.scalars(
                select(Sesion).where(
                    Sesion.grupo_id == grupo_id,
                    Sesion.id != sesion_preservar_id,
                )
            )
        )
        for s in sesiones_viernes:
            assert date.fromisoformat(s.fecha).weekday() == 4  # Viernes


def test_reprogramar_sesion_exitoso(
    sessions_app: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, factory = sessions_app
    _, grupo_id = _ref_ids(factory)
    base_lunes = date.today() + timedelta(days=7)

    with factory() as session:
        grupo = session.get(Grupo, grupo_id)
        assert grupo is not None
        sessions_service.generar_sesiones_grupo(session, grupo)
        session.commit()

        sesion = session.scalar(
            select(Sesion)
            .where(Sesion.grupo_id == grupo_id, Sesion.estado == "programada")
            .order_by(Sesion.fecha.desc())
            .limit(1)
        )
        assert sesion is not None
        sesion_id = sesion.id

    nueva_fecha = (date.today() + timedelta(days=90)).isoformat()
    resp = client.post(
        f"/grupos/{grupo_id}/sesiones/{sesion_id}/reprogramar",
        data={"fecha": nueva_fecha},
        follow_redirects=False,
    )
    assert resp.status_code == 303
    assert "reprogramada=1" in resp.headers["location"]

    with factory() as session:
        sesion_mod = session.get(Sesion, sesion_id)
        assert sesion_mod is not None
        assert sesion_mod.fecha == nueva_fecha


def test_reprogramar_sesion_rechaza_casos_invalidos(
    sessions_app: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, factory = sessions_app
    _, grupo_id = _ref_ids(factory)

    with factory() as session:
        grupo = session.get(Grupo, grupo_id)
        assert grupo is not None
        sessions_service.generar_sesiones_grupo(session, grupo)
        session.commit()

        sesiones = list(
            session.scalars(
                select(Sesion)
                .where(Sesion.grupo_id == grupo_id)
                .order_by(Sesion.fecha.asc())
                .limit(2)
            )
        )
        s1, s2 = sesiones[0], sesiones[1]
        s1_id = s1.id
        s2_fecha = s2.fecha

    # 1. Rechazar colisión con otra fecha existente
    resp_colision = client.post(
        f"/grupos/{grupo_id}/sesiones/{s1_id}/reprogramar",
        data={"fecha": s2_fecha},
        follow_redirects=False,
    )
    assert resp_colision.status_code == 303
    assert "error=" in resp_colision.headers["location"]

    # 2. Rechazar fecha en el pasado
    fecha_pasada = (date.today() - timedelta(days=10)).isoformat()
    resp_pasada = client.post(
        f"/grupos/{grupo_id}/sesiones/{s1_id}/reprogramar",
        data={"fecha": fecha_pasada},
        follow_redirects=False,
    )
    assert resp_pasada.status_code == 303
    assert "error=" in resp_pasada.headers["location"]

    # 3. Rechazar si ya tiene asistencias
    with factory() as session:
        alumno_id = session.scalar(select(Alumno.id).limit(1))
        assert alumno_id is not None
        session.add(
            Asistencia(
                sesion_id=s1_id,
                alumno_id=alumno_id,
                estado="asistio",
                es_reposicion=0,
            )
        )
        session.commit()

    nueva_libre = (date.today() + timedelta(days=120)).isoformat()
    resp_asist = client.post(
        f"/grupos/{grupo_id}/sesiones/{s1_id}/reprogramar",
        data={"fecha": nueva_libre},
        follow_redirects=False,
    )
    assert resp_asist.status_code == 303
    assert "error=" in resp_asist.headers["location"]


def test_pantalla_sesiones_html_identidad_y_sin_cdn(
    sessions_app: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, factory = sessions_app
    _, grupo_id = _ref_ids(factory)

    resp = client.get(f"/grupos/{grupo_id}/sesiones")
    assert resp.status_code == 200
    assert "ICIA" in resp.text
    assert "Sesiones de" in resp.text
    assert "Programadas" in resp.text
    assert "Generar horizonte" in resp.text

    # Sin CDNs externas
    for dominio in ("unpkg", "cdnjs", "jsdelivr", "googleapis"):
        assert dominio not in resp.text


def test_pos_reutiliza_sesion_generada_de_hoy(
    sessions_app: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, factory = sessions_app
    sucursal_id, _ = _ref_ids(factory)
    maestros = _maestro_ids(factory)
    dia_de_hoy = catalog.DIAS_SEMANA[date.today().weekday()]

    # Crear grupo que incluya el día de hoy
    with factory() as session:
        grupo = catalog.crear_grupo(
            session,
            sucursal_id=sucursal_id,
            nombre="Grupo De Hoy",
            dias_semana=[dia_de_hoy],
            hora_inicio="12:00",
            hora_fin="14:00",
            precio="130.00",
            bloques=[
                catalog.BloqueForm(
                    materia="ingles", orden=1, duracion_minutos=60, maestro_id=maestros[0]
                ),
                catalog.BloqueForm(
                    materia="robotica", orden=2, duracion_minutos=60, maestro_id=maestros[1]
                ),
            ],
        )
        grupo_id = grupo.id

    # La sesión de hoy ya debe existir porque se generó automáticamente
    with factory() as session:
        sesion_hoy = session.scalar(
            select(Sesion).where(
                Sesion.grupo_id == grupo_id,
                Sesion.fecha == date.today().isoformat(),
            )
        )
        assert sesion_hoy is not None

    # Al abrir POS para este grupo, se debe seleccionar directamente la sesión de hoy
    pos_resp = client.get(f"/pos?sucursal_id={sucursal_id}&grupo_id={grupo_id}")
    assert pos_resp.status_code == 200
    assert "No hay sesión para hoy" not in pos_resp.text
    assert "session-summary" in pos_resp.text


def _crear_sesion(
    factory: sessionmaker[Session],
    grupo_id: int,
    fecha: str,
    estado: str = "programada",
    es_extra: int = 0,
    maestro_ids: tuple[int, ...] = (),
) -> int:
    with factory() as session:
        sesion = Sesion(
            grupo_id=grupo_id,
            fecha=fecha,
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


def _maestros_de_sesion(
    factory: sessionmaker[Session],
    sesion_id: int,
) -> set[int]:
    with factory() as session:
        return set(
            session.scalars(
                select(SesionMaestro.maestro_id).where(
                    SesionMaestro.sesion_id == sesion_id
                )
            )
        )


def test_cancelar_sesion_programada_sin_datos(
    sessions_app: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, factory = sessions_app
    _, grupo_id = _ref_ids(factory)
    maestros = _maestro_ids(factory)
    fecha = (date.today() + timedelta(days=10)).isoformat()

    sesion_id = _crear_sesion(
        factory,
        grupo_id,
        fecha,
        maestro_ids=(maestros[0], maestros[1]),
    )

    resp = client.post(
        f"/grupos/{grupo_id}/sesiones/{sesion_id}/cancelar",
        follow_redirects=False,
    )
    assert resp.status_code == 303
    assert "cancelada=1" in resp.headers["location"]

    with factory() as session:
        sesion = session.get(Sesion, sesion_id)
        assert sesion is not None
        assert sesion.estado == "cancelada"

        marcas = list(
            session.scalars(
                select(SesionMaestro).where(SesionMaestro.sesion_id == sesion_id)
            )
        )
        assert len(marcas) == 2
        assert all(marca.pagado == 0 for marca in marcas)


def test_cancelar_sesion_rechaza_casos_invalidos(
    sessions_app: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, factory = sessions_app
    _, grupo_id = _ref_ids(factory)
    maestros = _maestro_ids(factory)

    with factory() as session:
        alumno_id = session.scalar(select(Alumno.id).limit(1))
    assert alumno_id is not None

    fecha_pasada = (date.today() - timedelta(days=1)).isoformat()
    sesion_pasada = _crear_sesion(factory, grupo_id, fecha_pasada)
    resp_pasada = client.post(
        f"/grupos/{grupo_id}/sesiones/{sesion_pasada}/cancelar",
        follow_redirects=False,
    )
    assert resp_pasada.status_code == 303
    assert "error=" in resp_pasada.headers["location"]

    sesion_con_asistencia = _crear_sesion(
        factory, grupo_id, (date.today() + timedelta(days=11)).isoformat()
    )
    with factory() as session:
        session.add(
            Asistencia(
                sesion_id=sesion_con_asistencia,
                alumno_id=alumno_id,
                estado="asistio",
                es_reposicion=0,
            )
        )
        session.commit()

    resp_asistencia = client.post(
        f"/grupos/{grupo_id}/sesiones/{sesion_con_asistencia}/cancelar",
        follow_redirects=False,
    )
    assert resp_asistencia.status_code == 303
    assert "error=" in resp_asistencia.headers["location"]

    sesion_pagada = _crear_sesion(
        factory,
        grupo_id,
        (date.today() + timedelta(days=12)).isoformat(),
        maestro_ids=(maestros[0],),
    )
    with factory() as session:
        marca = session.scalar(
            select(SesionMaestro).where(SesionMaestro.sesion_id == sesion_pagada)
        )
        assert marca is not None
        marca.pagado = 1
        session.commit()

    resp_pagada = client.post(
        f"/grupos/{grupo_id}/sesiones/{sesion_pagada}/cancelar",
        follow_redirects=False,
    )
    assert resp_pagada.status_code == 303
    assert "error=" in resp_pagada.headers["location"]

    sesion_cancelada = _crear_sesion(
        factory,
        grupo_id,
        (date.today() + timedelta(days=13)).isoformat(),
        estado="cancelada",
    )
    resp_cancelada = client.post(
        f"/grupos/{grupo_id}/sesiones/{sesion_cancelada}/cancelar",
        follow_redirects=False,
    )
    assert resp_cancelada.status_code == 303
    assert "error=" in resp_cancelada.headers["location"]

    sesion_impartida = _crear_sesion(
        factory,
        grupo_id,
        (date.today() + timedelta(days=14)).isoformat(),
        estado="impartida",
    )
    resp_impartida = client.post(
        f"/grupos/{grupo_id}/sesiones/{sesion_impartida}/cancelar",
        follow_redirects=False,
    )
    assert resp_impartida.status_code == 303
    assert "error=" in resp_impartida.headers["location"]

    with factory() as session:
        assert session.get(Sesion, sesion_pasada).estado == "programada"
        assert session.get(Sesion, sesion_con_asistencia).estado == "programada"
        assert session.get(Sesion, sesion_pagada).estado == "programada"
        assert session.get(Sesion, sesion_cancelada).estado == "cancelada"
        assert session.get(Sesion, sesion_impartida).estado == "impartida"


def test_reactivar_sesion_cancelada(
    sessions_app: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, factory = sessions_app
    _, grupo_id = _ref_ids(factory)
    maestros = _maestro_ids(factory)

    sesion_id = _crear_sesion(
        factory,
        grupo_id,
        (date.today() + timedelta(days=15)).isoformat(),
        estado="cancelada",
        maestro_ids=(maestros[0], maestros[1]),
    )

    resp = client.post(
        f"/grupos/{grupo_id}/sesiones/{sesion_id}/reactivar",
        follow_redirects=False,
    )
    assert resp.status_code == 303
    assert "reactivada=1" in resp.headers["location"]

    with factory() as session:
        sesion = session.get(Sesion, sesion_id)
        assert sesion is not None
        assert sesion.estado == "programada"
    assert _maestros_de_sesion(factory, sesion_id) == {maestros[0], maestros[1]}

    sesion_pasada = _crear_sesion(
        factory,
        grupo_id,
        (date.today() - timedelta(days=2)).isoformat(),
        estado="cancelada",
    )
    resp_pasada = client.post(
        f"/grupos/{grupo_id}/sesiones/{sesion_pasada}/reactivar",
        follow_redirects=False,
    )
    assert resp_pasada.status_code == 303
    assert "error=" in resp_pasada.headers["location"]


def test_crear_sesion_extra_copia_maestros(
    sessions_app: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, factory = sessions_app
    _, grupo_id = _ref_ids(factory)
    maestros = _maestro_ids(factory)
    fecha = (date.today() + timedelta(days=16)).isoformat()

    resp = client.post(
        f"/grupos/{grupo_id}/sesiones/extra",
        data={"fecha": fecha},
        follow_redirects=False,
    )
    assert resp.status_code == 303
    assert "extra_creada=1" in resp.headers["location"]

    with factory() as session:
        sesion = session.scalar(
            select(Sesion).where(
                Sesion.grupo_id == grupo_id,
                Sesion.fecha == fecha,
            )
        )
        assert sesion is not None
        assert sesion.es_extra == 1
        assert sesion.estado == "programada"
        sesion_id = sesion.id

    assert _maestros_de_sesion(factory, sesion_id) == set(maestros)


def test_crear_sesion_extra_rechaza_casos_invalidos(
    sessions_app: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, factory = sessions_app
    _, grupo_id = _ref_ids(factory)
    fecha_ocupada = (date.today() + timedelta(days=17)).isoformat()
    _crear_sesion(factory, grupo_id, fecha_ocupada)

    resp_duplicada = client.post(
        f"/grupos/{grupo_id}/sesiones/extra",
        data={"fecha": fecha_ocupada},
        follow_redirects=False,
    )
    assert resp_duplicada.status_code == 303
    assert "error=" in resp_duplicada.headers["location"]

    resp_pasada = client.post(
        f"/grupos/{grupo_id}/sesiones/extra",
        data={"fecha": (date.today() - timedelta(days=1)).isoformat()},
        follow_redirects=False,
    )
    assert resp_pasada.status_code == 303
    assert "error=" in resp_pasada.headers["location"]

    resp_invalida = client.post(
        f"/grupos/{grupo_id}/sesiones/extra",
        data={"fecha": "2026-13-40"},
        follow_redirects=False,
    )
    assert resp_invalida.status_code == 303
    assert "error=" in resp_invalida.headers["location"]

    with factory() as session:
        grupo = session.get(Grupo, grupo_id)
        assert grupo is not None
        grupo.activo = 0
        session.commit()

    resp_grupo_inactivo = client.post(
        f"/grupos/{grupo_id}/sesiones/extra",
        data={"fecha": (date.today() + timedelta(days=18)).isoformat()},
        follow_redirects=False,
    )
    assert resp_grupo_inactivo.status_code == 303
    assert "error=" in resp_grupo_inactivo.headers["location"]

    with factory() as session:
        grupo = session.get(Grupo, grupo_id)
        assert grupo is not None
        grupo.activo = 1
        sucursal = session.get(Sucursal, grupo.sucursal_id)
        assert sucursal is not None
        sucursal.activa = 0
        session.commit()

    resp_sucursal_inactiva = client.post(
        f"/grupos/{grupo_id}/sesiones/extra",
        data={"fecha": (date.today() + timedelta(days=19)).isoformat()},
        follow_redirects=False,
    )
    assert resp_sucursal_inactiva.status_code == 303
    assert "error=" in resp_sucursal_inactiva.headers["location"]


def test_canceladas_y_extras_sobreviven_a_sincronizacion(
    sessions_app: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, factory = sessions_app
    sucursal_id, _ = _ref_ids(factory)
    maestros = _maestro_ids(factory)

    with factory() as session:
        grupo = catalog.crear_grupo(
            session,
            sucursal_id=sucursal_id,
            nombre="Grupo Preservación",
            dias_semana=["Lunes"],
            hora_inicio="16:00",
            hora_fin="18:00",
            precio="140.00",
            bloques=[
                catalog.BloqueForm(
                    materia="ingles",
                    orden=1,
                    duracion_minutos=60,
                    maestro_id=maestros[0],
                ),
                catalog.BloqueForm(
                    materia="robotica",
                    orden=2,
                    duracion_minutos=60,
                    maestro_id=maestros[1],
                ),
            ],
        )
        grupo_id = grupo.id

    extra_fecha = date.today() + timedelta(days=1)
    while extra_fecha.weekday() == 0:
        extra_fecha += timedelta(days=1)

    with factory() as session:
        sesiones = list(
            session.scalars(
                select(Sesion)
                .where(Sesion.grupo_id == grupo_id)
                .order_by(Sesion.fecha.asc())
            )
        )
        assert sesiones
        cancelable = sesiones[0]
        cancelable_id = cancelable.id
        sessions_service.cancelar_sesion(session, grupo_id, cancelable_id)

        extra = sessions_service.crear_sesion_extra(
            session,
            grupo_id,
            extra_fecha.isoformat(),
        )
        extra_id = extra.id

    maestros_cancelada = _maestros_de_sesion(factory, cancelable_id)
    maestros_extra = _maestros_de_sesion(factory, extra_id)
    assert maestros_cancelada == {maestros[0], maestros[1]}
    assert maestros_extra == {maestros[0], maestros[1]}

    with factory() as session:
        nuevo_maestro = Maestro(nombre="Maestro Nuevo", especialidad="Robótica")
        session.add(nuevo_maestro)
        session.commit()
        nuevo_maestro_id = nuevo_maestro.id

    resp = client.post(
        f"/grupos/{grupo_id}",
        data={
            "sucursal_id": sucursal_id,
            "nombre": "Grupo Preservación",
            "dias_semana": ["Lunes"],
            "hora_inicio": "16:00",
            "hora_fin": "18:00",
            "precio": "140.00",
            "bloque_materia": ["ingles", "robotica"],
            "bloque_duracion": [60, 60],
            "bloque_maestro": [nuevo_maestro_id, maestros[1]],
        },
        follow_redirects=False,
    )
    assert resp.status_code == 303

    with factory() as session:
        cancelada = session.get(Sesion, cancelable_id)
        assert cancelada is not None
        assert cancelada.estado == "cancelada"

        extra = session.get(Sesion, extra_id)
        assert extra is not None
        assert extra.es_extra == 1
        assert extra.estado == "programada"

        programadas = list(
            session.scalars(
                select(Sesion).where(
                    Sesion.grupo_id == grupo_id,
                    Sesion.estado == "programada",
                    Sesion.es_extra == 0,
                )
            )
        )
        assert programadas
        ids_programadas = {
            maestro_id
            for sesion in programadas
            for maestro_id in _maestros_de_sesion(factory, sesion.id)
        }
        assert nuevo_maestro_id in ids_programadas

    assert _maestros_de_sesion(factory, cancelable_id) == maestros_cancelada
    assert _maestros_de_sesion(factory, extra_id) == maestros_extra


def test_pantalla_sesiones_muestra_acciones_de_cancelacion(
    sessions_app: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, factory = sessions_app
    _, grupo_id = _ref_ids(factory)

    with factory() as session:
        grupo = session.get(Grupo, grupo_id)
        assert grupo is not None
        sessions_service.generar_sesiones_grupo(session, grupo)
        session.commit()
        sesion = session.scalar(
            select(Sesion)
            .where(Sesion.grupo_id == grupo_id)
            .order_by(Sesion.fecha.asc())
            .limit(1)
        )
        assert sesion is not None
        sesion_id = sesion.id
        sessions_service.cancelar_sesion(session, grupo_id, sesion_id)

    resp = client.get(f"/grupos/{grupo_id}/sesiones?cancelada=1")
    assert resp.status_code == 200
    assert "Sesión cancelada. No generará faltas" in resp.text
    assert "Crear sesión extra" in resp.text
    assert "Reactivar" in resp.text


def test_pos_muestra_sesion_extra(
    sessions_app: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, factory = sessions_app
    sucursal_id, grupo_id = _ref_ids(factory)

    with factory() as session:
        sessions_service.crear_sesion_extra(
            session,
            grupo_id,
            date.today().isoformat(),
        )

    resp = client.get(f"/pos?sucursal_id={sucursal_id}&grupo_id={grupo_id}")
    assert resp.status_code == 200
    assert "Programada · Extra" in resp.text
