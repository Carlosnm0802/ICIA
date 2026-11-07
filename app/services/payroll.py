from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session, aliased

from app.models import Grupo, Maestro, Sesion, SesionMaestro, Sucursal

ESTADOS_PAGO = ("todos", "pendiente", "pagado")


class PayrollError(Exception):
    pass


@dataclass(frozen=True)
class HonorarioItem:
    marca_id: int
    sesion_id: int
    fecha: str
    es_extra: bool
    grupo_id: int
    grupo_nombre: str
    sucursal_id: int
    sucursal_nombre: str
    maestro_id: int
    maestro_nombre: str
    titular_nombre: str | None
    pagado: bool
    fecha_pago: str | None


@dataclass(frozen=True)
class ResumenHonorarios:
    desde: str
    hasta: str
    items: tuple[HonorarioItem, ...]
    total: int
    pagadas: int
    pendientes: int
    total_sesiones: int


def rango_corte(hoy: date | None = None) -> tuple[date, date]:
    fecha = hoy or date.today()
    return fecha - timedelta(days=fecha.weekday()), fecha


def listar_maestros_filtro(db: Session) -> list[Maestro]:
    return list(db.scalars(select(Maestro).order_by(Maestro.nombre)))


def listar_honorarios(
    db: Session,
    desde: date,
    hasta: date,
    *,
    hoy: date | None = None,
    sucursal_id: int | None = None,
    maestro_id: int | None = None,
    estado: str = "todos",
) -> ResumenHonorarios:
    if desde > hasta:
        raise PayrollError("La fecha inicial no puede ser posterior a la final.")
    if estado not in ESTADOS_PAGO:
        raise PayrollError("El estado de pago no es válido.")

    base_hoy = hoy or date.today()
    fin = min(hasta, base_hoy)
    titular = aliased(Maestro)

    consulta = (
        select(
            SesionMaestro,
            Sesion,
            Grupo,
            Sucursal,
            Maestro.nombre,
            titular.nombre,
        )
        .join(Sesion, Sesion.id == SesionMaestro.sesion_id)
        .join(Grupo, Grupo.id == Sesion.grupo_id)
        .join(Sucursal, Sucursal.id == Grupo.sucursal_id)
        .join(Maestro, Maestro.id == SesionMaestro.maestro_id)
        .outerjoin(titular, titular.id == SesionMaestro.maestro_titular_id)
        .where(
            Sesion.estado != "cancelada",
            Sesion.fecha >= desde.isoformat(),
            Sesion.fecha <= fin.isoformat(),
        )
    )

    if sucursal_id is not None:
        consulta = consulta.where(Sucursal.id == sucursal_id)
    if maestro_id is not None:
        consulta = consulta.where(SesionMaestro.maestro_id == maestro_id)
    if estado == "pendiente":
        consulta = consulta.where(SesionMaestro.pagado == 0)
    elif estado == "pagado":
        consulta = consulta.where(SesionMaestro.pagado == 1)

    filas = db.execute(
        consulta.order_by(
            Sesion.fecha.asc(),
            Sucursal.nombre,
            Grupo.nombre,
            Maestro.nombre,
        )
    ).all()

    items = tuple(
        HonorarioItem(
            marca_id=marca.id,
            sesion_id=sesion.id,
            fecha=sesion.fecha,
            es_extra=bool(sesion.es_extra),
            grupo_id=grupo.id,
            grupo_nombre=grupo.nombre,
            sucursal_id=sucursal.id,
            sucursal_nombre=sucursal.nombre,
            maestro_id=marca.maestro_id,
            maestro_nombre=maestro_nombre,
            titular_nombre=titular_nombre,
            pagado=bool(marca.pagado),
            fecha_pago=marca.fecha_pago,
        )
        for marca, sesion, grupo, sucursal, maestro_nombre, titular_nombre in filas
    )

    pagadas = sum(1 for item in items if item.pagado)
    return ResumenHonorarios(
        desde=desde.isoformat(),
        hasta=fin.isoformat(),
        items=items,
        total=len(items),
        pagadas=pagadas,
        pendientes=len(items) - pagadas,
        total_sesiones=len({item.sesion_id for item in items}),
    )


def marcar_honorarios_lote(
    db: Session,
    marca_ids: Sequence[int],
    *,
    pagado: bool,
    hoy: date | None = None,
) -> int:
    ids = sorted(set(marca_ids))
    if not ids:
        raise PayrollError("Selecciona al menos una marca de pago.")

    base_hoy = hoy or date.today()
    hoy_iso = base_hoy.isoformat()
    filas = db.execute(
        select(SesionMaestro, Sesion)
        .join(Sesion, Sesion.id == SesionMaestro.sesion_id)
        .where(SesionMaestro.id.in_(ids))
    ).all()

    if len(filas) != len(ids):
        raise PayrollError(
            "Una o más marcas de pago ya no existen. Actualiza la pantalla."
        )

    for marca, sesion in filas:
        if sesion.estado == "cancelada":
            raise PayrollError(
                "No se pueden modificar honorarios de una sesión cancelada."
            )
        if sesion.fecha > hoy_iso:
            raise PayrollError(
                "No se pueden modificar honorarios de una sesión futura."
            )

    fecha_pago = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cambios = 0
    for marca, _sesion in filas:
        if pagado:
            if marca.pagado != 1:
                marca.pagado = 1
                marca.fecha_pago = fecha_pago
                cambios += 1
        elif marca.pagado != 0:
            marca.pagado = 0
            marca.fecha_pago = None
            cambios += 1

    try:
        db.commit()
    except Exception:
        db.rollback()
        raise

    return cambios
