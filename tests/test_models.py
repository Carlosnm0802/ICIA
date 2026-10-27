from sqlalchemy.orm import configure_mappers

import app.models
from app.core.database import Base

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
