from pathlib import Path

from sqlalchemy.orm import Session, configure_mappers

import app.models
from app.core.database import Base, build_engine
from app.models import Alumno, Grupo, GrupoAlumno, Sucursal

EXPECTED_TABLES = {
    "alumnos",
    "asistencias",
    "bloques_grupo",
    "configuracion",
    "folio_contadores",
    "grupo_alumnos",
    "grupos",
    "maestros",
    "pagos",
    "sesion_maestros",
    "sesiones",
    "sucursales",
}


def test_metadata_contains_all_contract_tables() -> None:
    assert set(Base.metadata.tables) == EXPECTED_TABLES


def test_mappers_configure_without_errors() -> None:
    configure_mappers()


def test_models_persist_and_expose_relationships(tmp_path: Path) -> None:
    engine = build_engine(tmp_path / "models.db")
    Base.metadata.create_all(engine)
    try:
        with Session(engine) as session:
            sucursal = Sucursal(nombre="El Refugio", prefijo_folio="REF")
            grupo = Grupo(
                sucursal=sucursal,
                nombre="Jueves 3-5 PM",
                dias_semana="Jueves",
                hora_inicio="15:00",
                hora_fin="17:00",
                precio_centavos=14000,
            )
            alumno = Alumno(nombre="Alumno 01")
            session.add_all([grupo, alumno])
            session.flush()
            inscripcion = GrupoAlumno(grupo=grupo, alumno=alumno)
            session.add(inscripcion)
            session.commit()

            assert sucursal.id is not None
            assert grupo.id is not None
            assert alumno.id is not None
            assert grupo.sucursal is sucursal
            assert grupo.sucursal_id == sucursal.id
            assert inscripcion.grupo is grupo
            assert inscripcion.alumno is alumno
            assert grupo.alumnos == [inscripcion]
            assert alumno.grupos == [inscripcion]
            assert sucursal.grupos == [grupo]
            assert grupo.activo == 1
            assert alumno.estado == "activo"
            assert inscripcion.fecha_alta is not None
            assert session.get(Grupo, grupo.id) is grupo
    finally:
        engine.dispose()
