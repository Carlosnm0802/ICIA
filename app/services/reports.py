from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from sqlalchemy import and_, func, select, text
from sqlalchemy.orm import Session

from app.models import Alumno, Grupo, Pago, Sesion, Sucursal


@dataclass(frozen=True)
class ResumenDashboard:
    fecha: date
    inicio_semana: date
    cobrado_hoy_centavos: int
    tickets_hoy: int
    cobrado_semana_centavos: int
    tickets_semana: int
    deudas_asistencias: int
    deudas_centavos: int
    alumnos_activos: int


@dataclass(frozen=True)
class RecaudacionSucursal:
    sucursal_id: int
    nombre: str
    prefijo_folio: str
    total_centavos: int
    tickets: int


@dataclass(frozen=True)
class DeudaPendiente:
    asistencia_id: int
    alumno_id: int
    alumno: str
    sesion_id: int
    fecha_sesion: str
    grupo_id: int
    grupo: str
    sucursal_id: int
    sucursal: str
    monto_centavos: int


@dataclass(frozen=True)
class ReposicionPendiente:
    asistencia_id: int
    alumno_id: int
    alumno: str
    sesion_id: int
    fecha_falta: str
    grupo_id: int
    grupo: str
    sucursal_id: int
    sucursal: str
    pago_id: int
    folio: str
    monto_centavos: int


@dataclass(frozen=True)
class SesionDestino:
    id: int
    fecha: str
    grupo_id: int
    grupo: str
    sucursal_id: int
    sucursal: str
    hora_inicio: str
    hora_fin: str


def rango_semana(hoy: date | None = None) -> tuple[date, date]:
    fecha = hoy or date.today()
    return fecha - timedelta(days=fecha.weekday()), fecha


def _pagos_periodo(
    db: Session,
    desde: date,
    hasta: date,
) -> tuple[int, int]:
    total, tickets = db.execute(
        select(
            func.coalesce(func.sum(Pago.monto_centavos), 0),
            func.count(Pago.id),
        ).where(
            Pago.estado == "vigente",
            func.date(Pago.fecha) >= desde.isoformat(),
            func.date(Pago.fecha) <= hasta.isoformat(),
        )
    ).one()
    return int(total), int(tickets)


def resumen_dashboard(
    db: Session,
    hoy: date | None = None,
) -> ResumenDashboard:
    inicio_semana, fecha = rango_semana(hoy)

    cobrado_hoy, tickets_hoy = _pagos_periodo(db, fecha, fecha)
    cobrado_semana, tickets_semana = _pagos_periodo(
        db,
        inicio_semana,
        fecha,
    )

    deudas = db.execute(
        text(
            "SELECT COUNT(*) AS asistencias, "
            "COALESCE(SUM(monto_centavos), 0) AS monto "
            "FROM v_deudas"
        )
    ).mappings().one()

    alumnos_activos = db.scalar(
        select(func.count(Alumno.id)).where(Alumno.estado == "activo")
    )

    return ResumenDashboard(
        fecha=fecha,
        inicio_semana=inicio_semana,
        cobrado_hoy_centavos=cobrado_hoy,
        tickets_hoy=tickets_hoy,
        cobrado_semana_centavos=cobrado_semana,
        tickets_semana=tickets_semana,
        deudas_asistencias=int(deudas["asistencias"]),
        deudas_centavos=int(deudas["monto"]),
        alumnos_activos=int(alumnos_activos or 0),
    )


def recaudacion_por_sucursal(
    db: Session,
    desde: date,
    hasta: date,
) -> list[RecaudacionSucursal]:
    total = func.coalesce(func.sum(Pago.monto_centavos), 0).label(
        "total_centavos"
    )
    tickets = func.count(Pago.id).label("tickets")

    filas = db.execute(
        select(
            Sucursal.id,
            Sucursal.nombre,
            Sucursal.prefijo_folio,
            total,
            tickets,
        )
        .outerjoin(
            Pago,
            and_(
                Pago.sucursal_id == Sucursal.id,
                Pago.estado == "vigente",
                func.date(Pago.fecha) >= desde.isoformat(),
                func.date(Pago.fecha) <= hasta.isoformat(),
            ),
        )
        .where(Sucursal.activa == 1)
        .group_by(
            Sucursal.id,
            Sucursal.nombre,
            Sucursal.prefijo_folio,
        )
        .order_by(Sucursal.nombre)
    ).all()

    return [
        RecaudacionSucursal(
            sucursal_id=int(fila.id),
            nombre=fila.nombre,
            prefijo_folio=fila.prefijo_folio,
            total_centavos=int(fila.total_centavos),
            tickets=int(fila.tickets),
        )
        for fila in filas
    ]


def listar_deudas(db: Session) -> list[DeudaPendiente]:
    filas = db.execute(
        text(
            "SELECT "
            "d.asistencia_id, d.alumno_id, d.alumno, "
            "d.sesion_id, d.fecha_sesion, "
            "d.grupo_id, d.grupo, d.sucursal_id, d.sucursal, "
            "d.monto_centavos "
            "FROM v_deudas d "
            "JOIN asistencias a ON a.id = d.asistencia_id "
            "WHERE a.es_reposicion = 0 "
            "ORDER BY d.alumno COLLATE NOCASE, "
            "d.fecha_sesion, d.asistencia_id"
        )
    ).mappings().all()

    return [
        DeudaPendiente(
            asistencia_id=int(fila["asistencia_id"]),
            alumno_id=int(fila["alumno_id"]),
            alumno=fila["alumno"],
            sesion_id=int(fila["sesion_id"]),
            fecha_sesion=fila["fecha_sesion"],
            grupo_id=int(fila["grupo_id"]),
            grupo=fila["grupo"],
            sucursal_id=int(fila["sucursal_id"]),
            sucursal=fila["sucursal"],
            monto_centavos=int(fila["monto_centavos"]),
        )
        for fila in filas
    ]


def listar_reposiciones_pendientes(
    db: Session,
) -> list[ReposicionPendiente]:
    filas = db.execute(
        text(
            "SELECT "
            "r.asistencia_id, r.alumno_id, r.alumno, "
            "r.sesion_id, r.fecha_falta, "
            "r.grupo_id, r.grupo, su.id AS sucursal_id, "
            "su.nombre AS sucursal, "
            "r.pago_id, r.folio, r.monto_centavos "
            "FROM v_reposiciones_pendientes r "
            "JOIN grupos g ON g.id = r.grupo_id "
            "JOIN sucursales su ON su.id = g.sucursal_id "
            "ORDER BY r.alumno COLLATE NOCASE, "
            "r.fecha_falta, r.asistencia_id"
        )
    ).mappings().all()

    return [
        ReposicionPendiente(
            asistencia_id=int(fila["asistencia_id"]),
            alumno_id=int(fila["alumno_id"]),
            alumno=fila["alumno"],
            sesion_id=int(fila["sesion_id"]),
            fecha_falta=fila["fecha_falta"],
            grupo_id=int(fila["grupo_id"]),
            grupo=fila["grupo"],
            sucursal_id=int(fila["sucursal_id"]),
            sucursal=fila["sucursal"],
            pago_id=int(fila["pago_id"]),
            folio=fila["folio"],
            monto_centavos=int(fila["monto_centavos"]),
        )
        for fila in filas
    ]


def listar_sesiones_destino(db: Session) -> list[SesionDestino]:
    filas = db.execute(
        select(
            Sesion.id,
            Sesion.fecha,
            Grupo.id,
            Grupo.nombre,
            Sucursal.id,
            Sucursal.nombre,
            Grupo.hora_inicio,
            Grupo.hora_fin,
        )
        .join(Grupo, Grupo.id == Sesion.grupo_id)
        .join(Sucursal, Sucursal.id == Grupo.sucursal_id)
        .where(
            Sesion.estado != "cancelada",
            Grupo.activo == 1,
            Sucursal.activa == 1,
        )
        .order_by(Sesion.fecha, Grupo.hora_inicio, Grupo.nombre)
    ).all()

    return [
        SesionDestino(
            id=int(fila[0]),
            fecha=fila[1],
            grupo_id=int(fila[2]),
            grupo=fila[3],
            sucursal_id=int(fila[4]),
            sucursal=fila[5],
            hora_inicio=fila[6],
            hora_fin=fila[7],
        )
        for fila in filas
    ]
