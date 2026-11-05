from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Sequence

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import SESSION_HORIZON_WEEKS
from app.models import Asistencia, BloqueGrupo, Grupo, Maestro, Sesion, SesionMaestro, Sucursal

DIAS_INDICE = {
    "Lunes": 0,
    "Martes": 1,
    "Miércoles": 2,
    "Jueves": 3,
    "Viernes": 4,
    "Sábado": 5,
    "Domingo": 6,
}


class SessionServiceError(Exception):
    pass


@dataclass(frozen=True)
class SesionItem:
    id: int
    fecha: str
    estado: str
    es_extra: bool
    asistencias_total: int
    maestros: tuple[str, ...]
    puede_reprogramar: bool
    puede_cancelar: bool
    puede_reactivar: bool


@dataclass(frozen=True)
class SesionesGrupoResumen:
    grupo_id: int
    grupo_nombre: str
    sucursal_id: int
    sucursal_nombre: str
    dias_semana: str
    hora_inicio: str
    hora_fin: str
    precio_centavos: int
    total_programadas: int
    total_impartidas: int
    total_canceladas: int
    sesiones: list[SesionItem]


def dias_a_indices(dias_semana: str) -> set[int]:
    indices: set[int] = set()
    for dia in dias_semana.split(","):
        limpio = dia.strip()
        if limpio in DIAS_INDICE:
            indices.add(DIAS_INDICE[limpio])
    return indices


def calcular_fechas_horizonte(
    dias_semana: str,
    desde: date,
    hasta: date,
) -> list[date]:
    indices = dias_a_indices(dias_semana)
    if not indices or hasta < desde:
        return []

    fechas: list[date] = []
    actual = desde
    un_dia = timedelta(days=1)
    while actual <= hasta:
        if actual.weekday() in indices:
            fechas.append(actual)
        actual += un_dia
    return fechas


def _maestros_del_grupo(db: Session, grupo_id: int) -> list[int]:
    return list(
        db.scalars(
            select(BloqueGrupo.maestro_id)
            .where(BloqueGrupo.grupo_id == grupo_id)
            .distinct()
        )
    )


def _asegurar_maestros_sesion(
    db: Session,
    sesion: Sesion,
    maestro_ids: Sequence[int],
) -> None:
    existentes = set(
        db.scalars(
            select(SesionMaestro.maestro_id).where(
                SesionMaestro.sesion_id == sesion.id
            )
        )
    )
    for maestro_id in maestro_ids:
        if maestro_id not in existentes:
            db.add(
                SesionMaestro(
                    sesion_id=sesion.id,
                    maestro_id=maestro_id,
                    pagado=0,
                )
            )


def generar_sesiones_grupo(
    db: Session,
    grupo: Grupo,
    desde: date | None = None,
    hasta: date | None = None,
    hoy: date | None = None,
    semanas: int | None = None,
) -> int:
    sucursal = db.scalar(
        select(Sucursal).where(
            Sucursal.id == grupo.sucursal_id,
            Sucursal.activa == 1,
        )
    )
    if sucursal is None or grupo.activo == 0:
        return 0

    base_hoy = hoy or date.today()
    inicio = desde if desde is not None else base_hoy
    num_semanas = semanas if semanas is not None else SESSION_HORIZON_WEEKS
    fin = hasta if hasta is not None else (base_hoy + timedelta(weeks=num_semanas))

    fechas = calcular_fechas_horizonte(grupo.dias_semana, inicio, fin)
    if not fechas:
        return 0

    fechas_iso = [f.isoformat() for f in fechas]
    existentes: dict[str, Sesion] = {
        s.fecha: s
        for s in db.scalars(
            select(Sesion).where(
                Sesion.grupo_id == grupo.id,
                Sesion.fecha.in_(fechas_iso),
            )
        )
    }

    maestro_ids = _maestros_del_grupo(db, grupo.id)
    creadas = 0

    for fecha_obj in fechas:
        iso = fecha_obj.isoformat()
        sesion = existentes.get(iso)
        if sesion is None:
            sesion = Sesion(
                grupo_id=grupo.id,
                fecha=iso,
                estado="programada",
                es_extra=0,
            )
            db.add(sesion)
            db.flush()
            existentes[iso] = sesion
            creadas += 1
            if maestro_ids:
                _asegurar_maestros_sesion(db, sesion, maestro_ids)

    return creadas


def sincronizar_sesiones_grupo(
    db: Session,
    grupo: Grupo,
    hoy: date | None = None,
    reemplazar_futuras: bool = True,
) -> int:
    base_hoy = hoy or date.today()
    hoy_iso = base_hoy.isoformat()

    if reemplazar_futuras:
        sesiones_con_asistencia = select(Asistencia.sesion_id).distinct()
        sesiones_con_pago_maestro = (
            select(SesionMaestro.sesion_id)
            .where(SesionMaestro.pagado == 1)
            .distinct()
        )

        candidatas = list(
            db.scalars(
                select(Sesion).where(
                    Sesion.grupo_id == grupo.id,
                    Sesion.fecha >= hoy_iso,
                    Sesion.estado == "programada",
                    Sesion.es_extra == 0,
                    Sesion.id.not_in(sesiones_con_asistencia),
                    Sesion.id.not_in(sesiones_con_pago_maestro),
                )
            )
        )
        for sesion in candidatas:
            db.delete(sesion)
        db.flush()

    creadas = generar_sesiones_grupo(db, grupo, desde=base_hoy, hoy=base_hoy)
    return creadas


def generar_sesiones_activas(
    db: Session,
    hoy: date | None = None,
) -> int:
    grupos = list(
        db.scalars(
            select(Grupo)
            .join(Sucursal, Sucursal.id == Grupo.sucursal_id)
            .where(
                Grupo.activo == 1,
                Sucursal.activa == 1,
            )
        )
    )
    total_creadas = 0
    for grupo in grupos:
        total_creadas += generar_sesiones_grupo(db, grupo, hoy=hoy)
    return total_creadas


def listar_sesiones_grupo(
    db: Session,
    grupo_id: int,
    hoy: date | None = None,
) -> SesionesGrupoResumen | None:
    grupo = db.scalar(select(Grupo).where(Grupo.id == grupo_id))
    if grupo is None:
        return None
    sucursal = db.scalar(select(Sucursal).where(Sucursal.id == grupo.sucursal_id))
    sucursal_nombre = sucursal.nombre if sucursal else ""

    sesiones = list(
        db.scalars(
            select(Sesion)
            .where(Sesion.grupo_id == grupo.id)
            .order_by(Sesion.fecha.asc())
        )
    )

    conteo_asistencias: dict[int, int] = dict(
        db.execute(
            select(Asistencia.sesion_id, func.count(Asistencia.id))
            .where(Asistencia.sesion_id.in_([s.id for s in sesiones] or [0]))
            .group_by(Asistencia.sesion_id)
        ).all()
    )

    maestros_por_sesion: dict[int, list[str]] = {}
    sesiones_con_honorarios_pagados: set[int] = set()
    filas_maestros = db.execute(
        select(SesionMaestro.sesion_id, Maestro.nombre, SesionMaestro.pagado)
        .join(Maestro, Maestro.id == SesionMaestro.maestro_id)
        .where(SesionMaestro.sesion_id.in_([s.id for s in sesiones] or [0]))
        .order_by(Maestro.nombre)
    ).all()
    for s_id, m_nombre, m_pagado in filas_maestros:
        maestros_por_sesion.setdefault(s_id, []).append(m_nombre)
        if m_pagado == 1:
            sesiones_con_honorarios_pagados.add(s_id)

    items: list[SesionItem] = []
    tot_prog = 0
    tot_imp = 0
    tot_canc = 0
    hoy_iso = (hoy or date.today()).isoformat()

    for s in sesiones:
        if s.estado == "programada":
            tot_prog += 1
        elif s.estado == "impartida":
            tot_imp += 1
        elif s.estado == "cancelada":
            tot_canc += 1

        num_asistencias = conteo_asistencias.get(s.id, 0)
        con_datos = (
            num_asistencias > 0
            or s.id in sesiones_con_honorarios_pagados
        )
        puede_reprogramar = s.estado == "programada" and num_asistencias == 0
        puede_cancelar = (
            s.estado == "programada"
            and s.fecha >= hoy_iso
            and not con_datos
        )
        puede_reactivar = (
            s.estado == "cancelada"
            and s.fecha >= hoy_iso
            and not con_datos
        )

        items.append(
            SesionItem(
                id=s.id,
                fecha=s.fecha,
                estado=s.estado,
                es_extra=bool(s.es_extra),
                asistencias_total=num_asistencias,
                maestros=tuple(maestros_por_sesion.get(s.id, [])),
                puede_reprogramar=puede_reprogramar,
                puede_cancelar=puede_cancelar,
                puede_reactivar=puede_reactivar,
            )
        )

    return SesionesGrupoResumen(
        grupo_id=grupo.id,
        grupo_nombre=grupo.nombre,
        sucursal_id=grupo.sucursal_id,
        sucursal_nombre=sucursal_nombre,
        dias_semana=grupo.dias_semana,
        hora_inicio=grupo.hora_inicio,
        hora_fin=grupo.hora_fin,
        precio_centavos=grupo.precio_centavos,
        total_programadas=tot_prog,
        total_impartidas=tot_imp,
        total_canceladas=tot_canc,
        sesiones=items,
    )


def _obtener_sesion_grupo(
    db: Session,
    grupo_id: int,
    sesion_id: int,
) -> Sesion:
    sesion = db.scalar(
        select(Sesion).where(
            Sesion.id == sesion_id,
            Sesion.grupo_id == grupo_id,
        )
    )
    if sesion is None:
        raise SessionServiceError("La sesión no existe para este grupo.")
    return sesion


def _contar_asistencias(db: Session, sesion_id: int) -> int:
    return (
        db.scalar(
            select(func.count(Asistencia.id)).where(
                Asistencia.sesion_id == sesion_id
            )
        )
        or 0
    )


def _tiene_honorarios_pagados(db: Session, sesion_id: int) -> bool:
    return (
        db.scalar(
            select(func.count(SesionMaestro.id)).where(
                SesionMaestro.sesion_id == sesion_id,
                SesionMaestro.pagado == 1,
            )
        )
        or 0
    ) > 0


def _validar_sin_datos(db: Session, sesion: Sesion, accion: str) -> None:
    if _contar_asistencias(db, sesion.id) > 0:
        raise SessionServiceError(
            f"No se puede {accion} una sesión que ya tiene asistencias o cobros registrados."
        )
    if _tiene_honorarios_pagados(db, sesion.id):
        raise SessionServiceError(
            f"No se puede {accion} una sesión con honorarios de maestros ya pagados."
        )


def cancelar_sesion(
    db: Session,
    grupo_id: int,
    sesion_id: int,
    hoy: date | None = None,
) -> Sesion:
    sesion = _obtener_sesion_grupo(db, grupo_id, sesion_id)

    if sesion.estado == "cancelada":
        raise SessionServiceError("La sesión ya está cancelada.")
    if sesion.estado != "programada":
        raise SessionServiceError(
            f"Solo se pueden cancelar sesiones programadas (estado actual: {sesion.estado})."
        )

    base_hoy = hoy or date.today()
    if sesion.fecha < base_hoy.isoformat():
        raise SessionServiceError("No se puede cancelar una sesión pasada.")

    _validar_sin_datos(db, sesion, "cancelar")

    sesion.estado = "cancelada"
    db.commit()
    db.refresh(sesion)
    return sesion


def reactivar_sesion(
    db: Session,
    grupo_id: int,
    sesion_id: int,
    hoy: date | None = None,
) -> Sesion:
    sesion = _obtener_sesion_grupo(db, grupo_id, sesion_id)

    if sesion.estado != "cancelada":
        raise SessionServiceError("Solo se pueden reactivar sesiones canceladas.")

    base_hoy = hoy or date.today()
    if sesion.fecha < base_hoy.isoformat():
        raise SessionServiceError("No se puede reactivar una sesión pasada.")

    _validar_sin_datos(db, sesion, "reactivar")

    sesion.estado = "programada"
    db.commit()
    db.refresh(sesion)
    return sesion


def crear_sesion_extra(
    db: Session,
    grupo_id: int,
    fecha_iso: str,
    hoy: date | None = None,
) -> Sesion:
    grupo = db.scalar(
        select(Grupo).where(
            Grupo.id == grupo_id,
            Grupo.activo == 1,
        )
    )
    if grupo is None:
        raise SessionServiceError("El grupo no existe o está inactivo.")

    sucursal = db.scalar(
        select(Sucursal).where(
            Sucursal.id == grupo.sucursal_id,
            Sucursal.activa == 1,
        )
    )
    if sucursal is None:
        raise SessionServiceError("La sucursal del grupo está inactiva.")

    try:
        fecha = date.fromisoformat(fecha_iso.strip())
    except ValueError as exc:
        raise SessionServiceError(
            "La fecha de la sesión extra debe tener formato YYYY-MM-DD."
        ) from exc

    base_hoy = hoy or date.today()
    if fecha < base_hoy:
        raise SessionServiceError(
            "La sesión extra debe ser de hoy o de una fecha futura."
        )

    iso = fecha.isoformat()
    existente = db.scalar(
        select(Sesion).where(
            Sesion.grupo_id == grupo.id,
            Sesion.fecha == iso,
        )
    )
    if existente is not None:
        if existente.estado == "cancelada":
            raise SessionServiceError(
                f"Ya existe una sesión cancelada en la fecha {iso}; reactívala o elige otra fecha."
            )
        raise SessionServiceError(
            f"El grupo ya tiene una sesión registrada en la fecha {iso}."
        )

    sesion = Sesion(
        grupo_id=grupo.id,
        fecha=iso,
        estado="programada",
        es_extra=1,
    )
    try:
        db.add(sesion)
        db.flush()
        maestro_ids = _maestros_del_grupo(db, grupo.id)
        if maestro_ids:
            _asegurar_maestros_sesion(db, sesion, maestro_ids)
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise SessionServiceError(
            f"El grupo ya tiene una sesión registrada en la fecha {iso}."
        ) from exc

    db.refresh(sesion)
    return sesion


def reprogramar_sesion(
    db: Session,
    grupo_id: int,
    sesion_id: int,
    nueva_fecha_iso: str,
    hoy: date | None = None,
) -> Sesion:
    sesion = _obtener_sesion_grupo(db, grupo_id, sesion_id)

    if sesion.estado != "programada":
        raise SessionServiceError(
            f"Solo se pueden reprogramar sesiones programadas (estado actual: {sesion.estado})."
        )

    tiene_asistencias = (
        db.scalar(
            select(func.count(Asistencia.id)).where(
                Asistencia.sesion_id == sesion.id
            )
        )
        or 0
    ) > 0
    if tiene_asistencias:
        raise SessionServiceError(
            "No se puede reprogramar una sesión que ya tiene asistencias o cobros registrados."
        )

    try:
        nueva_fecha = date.fromisoformat(nueva_fecha_iso.strip())
    except ValueError as exc:
        raise SessionServiceError("La nueva fecha debe tener formato YYYY-MM-DD.") from exc

    base_hoy = hoy or date.today()
    if nueva_fecha < base_hoy:
        raise SessionServiceError("No se puede reprogramar una sesión a una fecha pasada.")

    nueva_iso = nueva_fecha.isoformat()
    if nueva_iso == sesion.fecha:
        return sesion

    colision = db.scalar(
        select(Sesion.id).where(
            Sesion.grupo_id == grupo_id,
            Sesion.fecha == nueva_iso,
            Sesion.id != sesion.id,
        )
    )
    if colision is not None:
        raise SessionServiceError(
            f"El grupo ya tiene una sesión registrada en la fecha {nueva_iso}."
        )

    sesion.fecha = nueva_iso
    db.commit()
    db.refresh(sesion)
    return sesion
