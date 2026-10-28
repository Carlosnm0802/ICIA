from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from unicodedata import normalize

from sqlalchemy import and_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import (
    Alumno,
    Asistencia,
    Grupo,
    GrupoAlumno,
    Pago,
    Sesion,
    Sucursal,
)

ESTADOS = {
    "pendiente": "Pendiente",
    "pagado": "Pagado",
    "deuda": "Deuda",
    "falto": "Faltó",
}


@dataclass(frozen=True)
class AlumnoRoster:
    id: int
    nombre: str
    estado: str
    etiqueta: str


@dataclass(frozen=True)
class ResumenRoster:
    total: int
    pendientes: int
    pagados: int
    deudas: int
    faltas: int


def clave_orden(nombre: str) -> str:
    sin_acentos = normalize("NFKD", nombre).encode("ascii", "ignore").decode()
    return sin_acentos.casefold()


def listar_sucursales(db: Session) -> list[Sucursal]:
    return list(
        db.scalars(
            select(Sucursal)
            .where(Sucursal.activa == 1)
            .order_by(Sucursal.nombre)
        )
    )


def obtener_sucursal(db: Session, sucursal_id: int) -> Sucursal | None:
    return db.scalar(
        select(Sucursal).where(
            Sucursal.id == sucursal_id,
            Sucursal.activa == 1,
        )
    )


def listar_grupos(db: Session, sucursal_id: int) -> list[Grupo]:
    return list(
        db.scalars(
            select(Grupo)
            .where(
                Grupo.sucursal_id == sucursal_id,
                Grupo.activo == 1,
            )
            .order_by(Grupo.hora_inicio, Grupo.nombre)
        )
    )


def obtener_grupo(
    db: Session,
    grupo_id: int,
    sucursal_id: int,
) -> Grupo | None:
    return db.scalar(
        select(Grupo).where(
            Grupo.id == grupo_id,
            Grupo.sucursal_id == sucursal_id,
            Grupo.activo == 1,
        )
    )


def obtener_grupo_activo(db: Session, grupo_id: int) -> Grupo | None:
    return db.scalar(
        select(Grupo).where(
            Grupo.id == grupo_id,
            Grupo.activo == 1,
        )
    )


def listar_sesiones(db: Session, grupo_id: int) -> list[Sesion]:
    return list(
        db.scalars(
            select(Sesion)
            .where(Sesion.grupo_id == grupo_id)
            .order_by(Sesion.fecha.desc())
        )
    )


def obtener_sesion(
    db: Session,
    sesion_id: int,
    grupo_id: int,
) -> Sesion | None:
    return db.scalar(
        select(Sesion).where(
            Sesion.id == sesion_id,
            Sesion.grupo_id == grupo_id,
        )
    )


def sesion_de_hoy(
    db: Session,
    grupo_id: int,
    hoy: date | None = None,
) -> Sesion | None:
    fecha = (hoy or date.today()).isoformat()
    return db.scalar(
        select(Sesion).where(
            Sesion.grupo_id == grupo_id,
            Sesion.fecha == fecha,
        )
    )


def abrir_sesion_hoy(
    db: Session,
    grupo: Grupo,
    hoy: date | None = None,
) -> Sesion:
    fecha = (hoy or date.today()).isoformat()
    existente = sesion_de_hoy(db, grupo.id, hoy)
    if existente is not None:
        return existente

    sesion = Sesion(
        grupo_id=grupo.id,
        fecha=fecha,
        estado="programada",
        es_extra=0,
    )
    db.add(sesion)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        existente = sesion_de_hoy(db, grupo.id, hoy)
        if existente is None:
            raise
        return existente

    db.refresh(sesion)
    return sesion


def _estado(asistencia: Asistencia | None, pago: Pago | None) -> str:
    if asistencia is None:
        return "pendiente"
    if asistencia.estado == "falto":
        return "falto"
    if pago is not None and pago.estado == "vigente":
        return "pagado"
    return "deuda"


def listar_roster(
    db: Session,
    grupo_id: int,
    sesion_id: int,
) -> tuple[list[AlumnoRoster], ResumenRoster]:
    consulta = (
        select(Alumno, Asistencia, Pago)
        .join(
            GrupoAlumno,
            and_(
                GrupoAlumno.alumno_id == Alumno.id,
                GrupoAlumno.grupo_id == grupo_id,
            ),
        )
        .outerjoin(
            Asistencia,
            and_(
                Asistencia.sesion_id == sesion_id,
                Asistencia.alumno_id == Alumno.id,
                Asistencia.es_reposicion == 0,
            ),
        )
        .outerjoin(Pago, Pago.id == Asistencia.pago_id)
        .where(
            GrupoAlumno.fecha_baja.is_(None),
            Alumno.estado == "activo",
        )
    )

    filas = db.execute(consulta).all()
    alumnos = []
    for alumno, asistencia, pago in filas:
        estado = _estado(asistencia, pago)
        alumnos.append(
            AlumnoRoster(
                id=alumno.id,
                nombre=alumno.nombre,
                estado=estado,
                etiqueta=ESTADOS[estado],
            )
        )
    alumnos.sort(key=lambda alumno: clave_orden(alumno.nombre))

    resumen = ResumenRoster(
        total=len(alumnos),
        pendientes=sum(1 for alumno in alumnos if alumno.estado == "pendiente"),
        pagados=sum(1 for alumno in alumnos if alumno.estado == "pagado"),
        deudas=sum(1 for alumno in alumnos if alumno.estado == "deuda"),
        faltas=sum(1 for alumno in alumnos if alumno.estado == "falto"),
    )
    return alumnos, resumen
