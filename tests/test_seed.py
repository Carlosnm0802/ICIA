from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from app.core.database import build_engine
from app.models import (
    Alumno,
    Asistencia,
    BloqueGrupo,
    FolioContador,
    Grupo,
    GrupoAlumno,
    Maestro,
    Pago,
    Sesion as SesionModel,
    Sucursal,
)
from app.services.seed import SeedSummary, seed_database

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _config(database_path: Path) -> Config:
    config = Config(str(PROJECT_ROOT / "alembic.ini"))
    config.set_main_option("prepend_sys_path", str(PROJECT_ROOT))
    config.set_main_option(
        "sqlalchemy.url",
        f"sqlite:///{database_path.as_posix()}",
    )
    return config


def _count(session: Session, model: type) -> int:
    return session.scalar(select(func.count()).select_from(model)) or 0


@pytest.fixture
def session(tmp_path: Path) -> Iterator[Session]:
    database_path = tmp_path / "seed.db"
    command.upgrade(_config(database_path), "head")
    engine = build_engine(database_path)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    try:
        with factory.begin() as database_session:
            yield database_session
    finally:
        engine.dispose()


def test_seed_creates_expected_data(session: Session) -> None:
    summary = seed_database(session)

    assert summary == SeedSummary(
        sucursales_creadas=4,
        maestros_creados=2,
        grupos_creados=1,
        bloques_creados=2,
        alumnos_creados=35,
        inscripciones_creadas=35,
    )
    assert _count(session, Sucursal) == 4
    assert set(session.scalars(select(Sucursal.prefijo_folio))) == {
        "TOT",
        "OCO",
        "PON",
        "REF",
    }
    assert _count(session, Maestro) == 2
    assert {
        maestro.nombre: maestro.especialidad
        for maestro in session.scalars(select(Maestro))
    } == {
        "Maestro de Inglés": "Inglés",
        "Maestro de Robótica": "Robótica",
    }

    grupo = session.scalar(select(Grupo).where(Grupo.nombre == "Jueves 3-5 PM"))
    assert grupo is not None
    assert grupo.dias_semana == "Jueves"
    assert grupo.hora_inicio == "15:00"
    assert grupo.hora_fin == "17:00"
    assert grupo.precio_centavos == 14000
    sucursal = session.scalar(
        select(Sucursal).where(Sucursal.id == grupo.sucursal_id)
    )
    assert sucursal is not None
    assert sucursal.prefijo_folio == "REF"

    bloques = session.scalars(
        select(BloqueGrupo).order_by(BloqueGrupo.orden)
    ).all()
    assert [
        (bloque.materia, bloque.orden, bloque.duracion_minutos)
        for bloque in bloques
    ] == [
        ("ingles", 1, 60),
        ("robotica", 2, 60),
    ]
    maestros = {
        maestro.id: maestro.nombre
        for maestro in session.scalars(select(Maestro))
    }
    assert {maestros[bloque.maestro_id] for bloque in bloques} == {
        "Maestro de Inglés",
        "Maestro de Robótica",
    }

    assert _count(session, Alumno) == 35
    assert set(session.scalars(select(Alumno.nombre))) == {
        f"Alumno {indice:02d}" for indice in range(1, 36)
    }
    assert _count(session, GrupoAlumno) == 35
    assert (
        session.scalar(
            select(func.count())
            .select_from(GrupoAlumno)
            .where(GrupoAlumno.fecha_baja.is_(None))
        )
        == 35
    )

    contadores = session.scalars(select(FolioContador)).all()
    assert len(contadores) == 4
    assert all(contador.ultimo_consecutivo == 0 for contador in contadores)
    assert _count(session, SesionModel) == 0
    assert _count(session, Pago) == 0
    assert _count(session, Asistencia) == 0


def test_seed_is_idempotent(session: Session) -> None:
    seed_database(session)
    summary = seed_database(session)

    assert summary == SeedSummary(
        sucursales_creadas=0,
        maestros_creados=0,
        grupos_creados=0,
        bloques_creados=0,
        alumnos_creados=0,
        inscripciones_creadas=0,
    )
    assert _count(session, Sucursal) == 4
    assert _count(session, Maestro) == 2
    assert _count(session, Grupo) == 1
    assert _count(session, BloqueGrupo) == 2
    assert _count(session, Alumno) == 35
    assert _count(session, GrupoAlumno) == 35
    assert _count(session, FolioContador) == 4
