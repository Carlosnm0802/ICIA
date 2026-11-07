from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from unicodedata import normalize

from sqlalchemy import or_, select
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

MAX_RANGO_DIAS = 366


class AttendanceError(Exception):
    pass


@dataclass(frozen=True)
class SesionAsistencia:
    id: int
    fecha: str
    estado: str
    es_extra: bool
    total_registros: int
    total_asistio: int
    total_falto: int
    total_deuda: int
    total_reposicion: int


@dataclass(frozen=True)
class CeldaAsistencia:
    tipo: str
    etiqueta: str
    folio: str | None = None
    monto_centavos: int | None = None
    origen: str | None = None


@dataclass(frozen=True)
class FilaAsistencia:
    alumno_id: int
    alumno: str
    tutor: str | None
    estado_alumno: str
    celdas: dict[int, CeldaAsistencia] = field(default_factory=dict)
    total_asistio: int = 0
    total_falto: int = 0
    total_deuda: int = 0
    total_reposicion: int = 0


@dataclass(frozen=True)
class RegistroAsistencia:
    sucursal: str
    grupo: str
    fecha_sesion: str
    estado_sesion: str
    alumno: str
    tutor: str | None
    estado_asistencia: str
    reposicion: bool
    folio: str | None
    monto_centavos: int | None
    origen: str | None


@dataclass(frozen=True)
class ResumenAsistencia:
    grupo_id: int
    grupo: str
    sucursal_id: int
    sucursal: str
    desde: date
    hasta: date
    sesiones: list[SesionAsistencia]
    filas: list[FilaAsistencia]
    registros: list[RegistroAsistencia]
    total_sesiones: int
    total_registros: int
    total_asistio: int
    total_falto: int
    total_deuda: int
    total_reposicion: int
    porcentaje_asistencia: int


def rango_mes_actual(hoy: date | None = None) -> tuple[date, date]:
    fecha = hoy or date.today()
    return fecha.replace(day=1), fecha


def validar_rango(desde: date, hasta: date) -> None:
    if desde > hasta:
        raise AttendanceError(
            "La fecha inicial no puede ser posterior a la fecha final."
        )
    if (hasta - desde).days > MAX_RANGO_DIAS:
        raise AttendanceError(
            f"El rango no puede exceder {MAX_RANGO_DIAS} días."
        )


def _clave_orden(nombre: str) -> str:
    sin_acentos = normalize("NFKD", nombre).encode("ascii", "ignore").decode()
    return sin_acentos.casefold()


def _etiqueta_fecha(fecha: str) -> str:
    try:
        return date.fromisoformat(fecha).strftime("%d/%m/%Y")
    except ValueError:
        return fecha


def _contexto_grupo(
    db: Session,
    grupo_id: int,
) -> tuple[Grupo, Sucursal]:
    grupo = db.get(Grupo, grupo_id)
    if grupo is None:
        raise AttendanceError("El grupo no existe.")
    sucursal = db.get(Sucursal, grupo.sucursal_id)
    if sucursal is None:
        raise AttendanceError("La sucursal del grupo no existe.")
    return grupo, sucursal


def _alumnos_del_rango(
    db: Session,
    grupo_id: int,
    desde: date,
    hasta: date,
) -> dict[int, tuple[str, str | None, str]]:
    filas = db.execute(
        select(
            Alumno.id,
            Alumno.nombre,
            Alumno.tutor,
            Alumno.estado,
        )
        .join(GrupoAlumno, GrupoAlumno.alumno_id == Alumno.id)
        .where(
            GrupoAlumno.grupo_id == grupo_id,
            GrupoAlumno.fecha_alta <= hasta.isoformat(),
            or_(
                GrupoAlumno.fecha_baja.is_(None),
                GrupoAlumno.fecha_baja >= desde.isoformat(),
            ),
        )
    ).all()
    return {
        int(alumno_id): (nombre, tutor, estado)
        for alumno_id, nombre, tutor, estado in filas
    }


def _origenes_reposicion(
    db: Session,
    repone_ids: set[int],
) -> dict[int, str]:
    if not repone_ids:
        return {}
    filas = db.execute(
        select(
            Asistencia.id,
            Sesion.fecha,
            Grupo.nombre,
        )
        .join(Sesion, Sesion.id == Asistencia.sesion_id)
        .join(Grupo, Grupo.id == Sesion.grupo_id)
        .where(Asistencia.id.in_(repone_ids))
    ).all()
    return {
        int(asistencia_id): f"{grupo} · {_etiqueta_fecha(fecha)}"
        for asistencia_id, fecha, grupo in filas
    }


def _faltas_repuestas(
    db: Session,
    falta_ids: set[int],
) -> set[int]:
    if not falta_ids:
        return set()
    return {
        int(repone_id)
        for repone_id in db.scalars(
            select(Asistencia.repone_a_id).where(
                Asistencia.repone_a_id.in_(falta_ids),
                Asistencia.estado == "asistio",
            )
        )
        if repone_id is not None
    }


def resumen_asistencia(
    db: Session,
    grupo_id: int,
    desde: date,
    hasta: date,
) -> ResumenAsistencia:
    validar_rango(desde, hasta)
    grupo, sucursal = _contexto_grupo(db, grupo_id)

    sesiones_db = list(
        db.scalars(
            select(Sesion)
            .where(
                Sesion.grupo_id == grupo.id,
                Sesion.fecha >= desde.isoformat(),
                Sesion.fecha <= hasta.isoformat(),
            )
            .order_by(Sesion.fecha, Sesion.id)
        )
    )
    sesiones_por_id = {sesion.id: sesion for sesion in sesiones_db}
    alumnos = _alumnos_del_rango(db, grupo.id, desde, hasta)

    asistencias_db = list(
        db.execute(
            select(Asistencia, Pago, Alumno)
            .outerjoin(Pago, Pago.id == Asistencia.pago_id)
            .join(Alumno, Alumno.id == Asistencia.alumno_id)
            .where(Asistencia.sesion_id.in_(sesiones_por_id))
        ).all()
    )
    for asistencia, _, alumno in asistencias_db:
        alumnos[alumno.id] = (
            alumno.nombre,
            alumno.tutor,
            alumno.estado,
        )

    repone_ids = {
        int(asistencia.repone_a_id)
        for asistencia, _, _ in asistencias_db
        if asistencia.repone_a_id is not None
    }
    origenes = _origenes_reposicion(db, repone_ids)

    falta_ids = {
        int(asistencia.id)
        for asistencia, _, _ in asistencias_db
        if asistencia.es_reposicion == 0 and asistencia.estado == "falto"
    }
    repuestas = _faltas_repuestas(db, falta_ids)

    filas = {
        alumno_id: FilaAsistencia(
            alumno_id=alumno_id,
            alumno=datos[0],
            tutor=datos[1],
            estado_alumno=datos[2],
        )
        for alumno_id, datos in alumnos.items()
    }
    registros: list[RegistroAsistencia] = []
    conteos_sesion: dict[int, dict[str, int]] = {
        sesion.id: {
            "registros": 0,
            "asistio": 0,
            "falto": 0,
            "deuda": 0,
            "reposicion": 0,
        }
        for sesion in sesiones_db
    }
    total_asistio = 0
    total_falto = 0
    total_deuda = 0
    total_reposicion = 0

    for asistencia, pago, alumno in asistencias_db:
        sesion = sesiones_por_id[asistencia.sesion_id]
        fila = filas[alumno.id]
        celda: CeldaAsistencia

        if asistencia.es_reposicion == 1:
            origen = (
                origenes.get(asistencia.repone_a_id)
                if asistencia.repone_a_id is not None
                else None
            )
            celda = CeldaAsistencia(
                tipo="reposicion",
                etiqueta="Reposición",
                folio=pago.folio if pago is not None else None,
                monto_centavos=(
                    pago.monto_centavos if pago is not None else None
                ),
                origen=origen,
            )
            fila = _reemplazar_fila(
                fila,
                total_reposicion=fila.total_reposicion + 1,
            )
            conteos_sesion[sesion.id]["reposicion"] += 1
            total_reposicion += 1
        elif asistencia.estado == "falto":
            repuesta = asistencia.id in repuestas
            if repuesta:
                etiqueta = "Faltó · Repuesta"
                tipo = "falta_repuesta"
            elif pago is not None and pago.estado == "vigente":
                etiqueta = "Faltó · Reponer"
                tipo = "falta_reponer"
            else:
                etiqueta = "Faltó"
                tipo = "falto"
            celda = CeldaAsistencia(
                tipo=tipo,
                etiqueta=etiqueta,
                folio=pago.folio if pago is not None else None,
                monto_centavos=_monto(pago, asistencia, grupo),
            )
            fila = _reemplazar_fila(
                fila,
                total_falto=fila.total_falto + 1,
            )
            conteos_sesion[sesion.id]["falto"] += 1
            total_falto += 1
        else:
            es_deuda = pago is None or pago.estado != "vigente"
            celda = CeldaAsistencia(
                tipo="deuda" if es_deuda else "asistio",
                etiqueta="Asistió · Deuda" if es_deuda else "Asistió",
                folio=pago.folio if pago is not None else None,
                monto_centavos=_monto(pago, asistencia, grupo),
            )
            fila = _reemplazar_fila(
                fila,
                total_asistio=fila.total_asistio + 1,
                total_deuda=(
                    fila.total_deuda + 1 if es_deuda else fila.total_deuda
                ),
            )
            conteos_sesion[sesion.id]["asistio"] += 1
            total_asistio += 1
            if es_deuda:
                conteos_sesion[sesion.id]["deuda"] += 1
                total_deuda += 1

        fila.celdas[sesion.id] = celda
        filas[alumno.id] = fila
        conteos_sesion[sesion.id]["registros"] += 1
        registros.append(
            RegistroAsistencia(
                sucursal=sucursal.nombre,
                grupo=grupo.nombre,
                fecha_sesion=sesion.fecha,
                estado_sesion=sesion.estado,
                alumno=alumno.nombre,
                tutor=alumno.tutor,
                estado_asistencia=celda.etiqueta,
                reposicion=asistencia.es_reposicion == 1,
                folio=pago.folio if pago is not None else None,
                monto_centavos=_monto(pago, asistencia, grupo),
                origen=celda.origen,
            )
        )

    sesiones = [
        SesionAsistencia(
            id=sesion.id,
            fecha=sesion.fecha,
            estado=sesion.estado,
            es_extra=bool(sesion.es_extra),
            total_registros=conteos_sesion[sesion.id]["registros"],
            total_asistio=conteos_sesion[sesion.id]["asistio"],
            total_falto=conteos_sesion[sesion.id]["falto"],
            total_deuda=conteos_sesion[sesion.id]["deuda"],
            total_reposicion=conteos_sesion[sesion.id]["reposicion"],
        )
        for sesion in sesiones_db
    ]
    ordenadas = sorted(filas.values(), key=lambda fila: _clave_orden(fila.alumno))
    base_asistencia = total_asistio + total_falto
    porcentaje = (
        round((total_asistio / base_asistencia) * 100)
        if base_asistencia
        else 0
    )

    return ResumenAsistencia(
        grupo_id=grupo.id,
        grupo=grupo.nombre,
        sucursal_id=sucursal.id,
        sucursal=sucursal.nombre,
        desde=desde,
        hasta=hasta,
        sesiones=sesiones,
        filas=ordenadas,
        registros=sorted(
            registros,
            key=lambda registro: (
                registro.fecha_sesion,
                _clave_orden(registro.alumno),
            ),
        ),
        total_sesiones=len(sesiones),
        total_registros=len(registros),
        total_asistio=total_asistio,
        total_falto=total_falto,
        total_deuda=total_deuda,
        total_reposicion=total_reposicion,
        porcentaje_asistencia=porcentaje,
    )


def _monto(
    pago: Pago | None,
    asistencia: Asistencia,
    grupo: Grupo,
) -> int:
    if pago is not None:
        return pago.monto_centavos
    if asistencia.precio_aplicado_centavos is not None:
        return asistencia.precio_aplicado_centavos
    return grupo.precio_centavos


def _reemplazar_fila(
    fila: FilaAsistencia,
    *,
    total_asistio: int | None = None,
    total_falto: int | None = None,
    total_deuda: int | None = None,
    total_reposicion: int | None = None,
) -> FilaAsistencia:
    return FilaAsistencia(
        alumno_id=fila.alumno_id,
        alumno=fila.alumno,
        tutor=fila.tutor,
        estado_alumno=fila.estado_alumno,
        celdas=fila.celdas,
        total_asistio=(
            fila.total_asistio if total_asistio is None else total_asistio
        ),
        total_falto=fila.total_falto if total_falto is None else total_falto,
        total_deuda=fila.total_deuda if total_deuda is None else total_deuda,
        total_reposicion=(
            fila.total_reposicion
            if total_reposicion is None
            else total_reposicion
        ),
    )
