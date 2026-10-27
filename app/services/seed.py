from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import inspect, select
from sqlalchemy.orm import Session

from app.core.database import SessionLocal, engine
from app.models import (
    Alumno,
    BloqueGrupo,
    Grupo,
    GrupoAlumno,
    Maestro,
    Sucursal,
)

SUCURSALES = (
    ("Tototlán", "TOT"),
    ("Ocotlán", "OCO"),
    ("Poncitlán", "PON"),
    ("El Refugio", "REF"),
)
MAESTROS = (
    ("Maestro de Inglés", "Inglés"),
    ("Maestro de Robótica", "Robótica"),
)
ALUMNOS = tuple(f"Alumno {indice:02d}" for indice in range(1, 36))
GRUPO_SUCURSAL_PREFIJO = "REF"
GRUPO_NOMBRE = "Jueves 3-5 PM"
GRUPO_DIAS = "Jueves"
GRUPO_HORA_INICIO = "15:00"
GRUPO_HORA_FIN = "17:00"
GRUPO_PRECIO_CENTAVOS = 14000
BLOQUES = (
    ("ingles", 1, 60, "Maestro de Inglés"),
    ("robotica", 2, 60, "Maestro de Robótica"),
)
TABLAS_REQUERIDAS = (
    "sucursales",
    "alumnos",
    "maestros",
    "grupos",
    "bloques_grupo",
    "grupo_alumnos",
    "folio_contadores",
)


@dataclass(frozen=True)
class SeedSummary:
    sucursales_creadas: int
    maestros_creados: int
    grupos_creados: int
    bloques_creados: int
    alumnos_creados: int
    inscripciones_creadas: int


def _seed_sucursales(session: Session) -> int:
    creadas = 0
    for nombre, prefijo in SUCURSALES:
        existente = session.scalar(
            select(Sucursal).where(Sucursal.prefijo_folio == prefijo)
        )
        if existente is None:
            session.add(Sucursal(nombre=nombre, prefijo_folio=prefijo))
            creadas += 1
    session.flush()
    return creadas


def _seed_maestros(session: Session) -> int:
    creados = 0
    for nombre, especialidad in MAESTROS:
        existente = session.scalar(
            select(Maestro).where(
                Maestro.nombre == nombre,
                Maestro.especialidad == especialidad,
            )
        )
        if existente is None:
            session.add(Maestro(nombre=nombre, especialidad=especialidad))
            creados += 1
    session.flush()
    return creados


def _seed_grupo(session: Session) -> tuple[Grupo, int]:
    sucursal = session.scalar(
        select(Sucursal).where(
            Sucursal.prefijo_folio == GRUPO_SUCURSAL_PREFIJO
        )
    )
    if sucursal is None:
        raise RuntimeError(
            f"No existe la sucursal con prefijo {GRUPO_SUCURSAL_PREFIJO}"
        )

    grupo = session.scalar(
        select(Grupo).where(
            Grupo.sucursal_id == sucursal.id,
            Grupo.nombre == GRUPO_NOMBRE,
        )
    )
    if grupo is not None:
        return grupo, 0

    grupo = Grupo(
        sucursal_id=sucursal.id,
        nombre=GRUPO_NOMBRE,
        dias_semana=GRUPO_DIAS,
        hora_inicio=GRUPO_HORA_INICIO,
        hora_fin=GRUPO_HORA_FIN,
        precio_centavos=GRUPO_PRECIO_CENTAVOS,
    )
    session.add(grupo)
    session.flush()
    return grupo, 1


def _seed_bloques(session: Session, grupo: Grupo) -> int:
    creados = 0
    for materia, orden, duracion_minutos, maestro_nombre in BLOQUES:
        maestro = session.scalar(
            select(Maestro).where(Maestro.nombre == maestro_nombre)
        )
        if maestro is None:
            raise RuntimeError(f"No existe el maestro {maestro_nombre}")

        existente = session.scalar(
            select(BloqueGrupo).where(
                BloqueGrupo.grupo_id == grupo.id,
                BloqueGrupo.orden == orden,
            )
        )
        if existente is None:
            session.add(
                BloqueGrupo(
                    grupo_id=grupo.id,
                    materia=materia,
                    orden=orden,
                    duracion_minutos=duracion_minutos,
                    maestro_id=maestro.id,
                )
            )
            creados += 1
    session.flush()
    return creados


def _seed_alumnos(session: Session) -> tuple[list[Alumno], int]:
    existentes = {
        alumno.nombre: alumno
        for alumno in session.scalars(
            select(Alumno).where(Alumno.nombre.in_(ALUMNOS))
        )
    }
    creados = 0
    alumnos = []
    for nombre in ALUMNOS:
        alumno = existentes.get(nombre)
        if alumno is None:
            alumno = Alumno(nombre=nombre)
            session.add(alumno)
            existentes[nombre] = alumno
            creados += 1
        alumnos.append(alumno)
    session.flush()
    return alumnos, creados


def _seed_inscripciones(
    session: Session,
    grupo: Grupo,
    alumnos: list[Alumno],
) -> int:
    inscritos = set(
        session.scalars(
            select(GrupoAlumno.alumno_id).where(
                GrupoAlumno.grupo_id == grupo.id,
                GrupoAlumno.fecha_baja.is_(None),
            )
        )
    )
    creadas = 0
    for alumno in alumnos:
        if alumno.id not in inscritos:
            session.add(
                GrupoAlumno(grupo_id=grupo.id, alumno_id=alumno.id)
            )
            inscritos.add(alumno.id)
            creadas += 1
    session.flush()
    return creadas


def seed_database(session: Session) -> SeedSummary:
    sucursales_creadas = _seed_sucursales(session)
    maestros_creados = _seed_maestros(session)
    grupo, grupos_creados = _seed_grupo(session)
    bloques_creados = _seed_bloques(session, grupo)
    alumnos, alumnos_creados = _seed_alumnos(session)
    inscripciones_creadas = _seed_inscripciones(session, grupo, alumnos)

    return SeedSummary(
        sucursales_creadas=sucursales_creadas,
        maestros_creados=maestros_creados,
        grupos_creados=grupos_creados,
        bloques_creados=bloques_creados,
        alumnos_creados=alumnos_creados,
        inscripciones_creadas=inscripciones_creadas,
    )


def _ensure_schema() -> None:
    inspector = inspect(engine)
    faltantes = [
        tabla for tabla in TABLAS_REQUERIDAS if not inspector.has_table(tabla)
    ]
    if faltantes:
        raise RuntimeError(
            "Faltan tablas en la base de datos: "
            f"{', '.join(faltantes)}. Ejecuta: alembic upgrade head"
        )


def main() -> None:
    _ensure_schema()
    with SessionLocal.begin() as session:
        summary = seed_database(session)

    print("Datos semilla cargados.")
    print(f"Sucursales creadas: {summary.sucursales_creadas}")
    print(f"Maestros creados: {summary.maestros_creados}")
    print(f"Grupos creados: {summary.grupos_creados}")
    print(f"Bloques creados: {summary.bloques_creados}")
    print(f"Alumnos creados: {summary.alumnos_creados}")
    print(f"Inscripciones creadas: {summary.inscripciones_creadas}")


if __name__ == "__main__":
    main()
