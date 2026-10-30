from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import config
from app.models import (
    Alumno,
    Asistencia,
    BloqueGrupo,
    Configuracion,
    Grupo,
    Pago,
    Sesion,
    Sucursal,
)

ANCHOS_VALIDOS = (58, 80)
MATERIAS = {
    "ingles": "Inglés",
    "robotica": "Robótica",
}
METODOS = {
    "efectivo": "Efectivo",
    "transferencia": "Transferencia",
}
ESTADOS = {
    "vigente": "Vigente",
    "cancelado": "Cancelado",
}


@dataclass(frozen=True)
class TicketData:
    pago_id: int
    folio: str
    estado: str
    estado_etiqueta: str
    fecha: str
    alumno: str
    sucursal: str
    sucursal_direccion: str | None
    sucursal_telefono: str | None
    grupo: str | None
    materias: tuple[str, ...]
    sesion_fecha: str | None
    monto_centavos: int
    metodo: str
    metodo_etiqueta: str
    ancho_mm: int


def obtener_ancho_ticket(db: Session) -> int:
    registro = db.get(Configuracion, "ticket_ancho_mm")
    if registro is not None:
        try:
            ancho = int(registro.valor)
        except ValueError:
            ancho = 0
        if ancho in ANCHOS_VALIDOS:
            return ancho

    if config.TICKET_ANCHO_MM in ANCHOS_VALIDOS:
        return config.TICKET_ANCHO_MM
    return 80


def _ticket_desde_pago(db: Session, pago: Pago) -> TicketData:
    alumno = db.get(Alumno, pago.alumno_id)
    sucursal = db.get(Sucursal, pago.sucursal_id)
    asistencia = db.scalar(
        select(Asistencia).where(
            Asistencia.pago_id == pago.id,
            Asistencia.es_reposicion == 0,
        )
    )
    sesion = db.get(Sesion, asistencia.sesion_id) if asistencia else None
    grupo = db.get(Grupo, sesion.grupo_id) if sesion else None

    materias: tuple[str, ...] = ()
    if grupo is not None:
        bloques = db.scalars(
            select(BloqueGrupo)
            .where(BloqueGrupo.grupo_id == grupo.id)
            .order_by(BloqueGrupo.orden)
        )
        materias = tuple(
            MATERIAS.get(bloque.materia, bloque.materia)
            for bloque in bloques
        )

    return TicketData(
        pago_id=pago.id,
        folio=pago.folio,
        estado=pago.estado,
        estado_etiqueta=ESTADOS.get(pago.estado, pago.estado.capitalize()),
        fecha=pago.fecha,
        alumno=alumno.nombre if alumno is not None else "—",
        sucursal=sucursal.nombre if sucursal is not None else "—",
        sucursal_direccion=(
            sucursal.direccion if sucursal is not None else None
        ),
        sucursal_telefono=(
            sucursal.telefono if sucursal is not None else None
        ),
        grupo=grupo.nombre if grupo is not None else None,
        materias=materias,
        sesion_fecha=sesion.fecha if sesion is not None else None,
        monto_centavos=pago.monto_centavos,
        metodo=pago.metodo,
        metodo_etiqueta=METODOS.get(pago.metodo, pago.metodo.capitalize()),
        ancho_mm=obtener_ancho_ticket(db),
    )


def obtener_ticket(db: Session, pago_id: int) -> TicketData | None:
    pago = db.get(Pago, pago_id)
    if pago is None:
        return None
    return _ticket_desde_pago(db, pago)


def obtener_ticket_por_folio(db: Session, folio: str) -> TicketData | None:
    normalizado = folio.strip().upper()
    if not normalizado:
        return None

    pago = db.scalar(select(Pago).where(Pago.folio == normalizado))
    if pago is None:
        return None
    return _ticket_desde_pago(db, pago)
