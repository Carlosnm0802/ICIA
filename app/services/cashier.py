from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select, text
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
from app.services.folios import FolioError, siguiente_folio

METODOS = {"efectivo", "transferencia"}
MOTIVO_DESHACER = "Asistencia deshecha desde Cobro Express"


class CashierError(RuntimeError):
    pass


@dataclass(frozen=True)
class CobroResultado:
    pago_id: int
    folio: str
    alumno_id: int
    alumno: str
    grupo_id: int
    grupo: str
    sucursal_id: int
    sucursal: str
    sesion_id: int
    sesion_fecha: str
    monto_centavos: int
    metodo: str
    fecha: str


@dataclass(frozen=True)
class DeudaResultado:
    asistencia_id: int
    alumno_id: int
    alumno: str
    grupo_id: int
    grupo: str
    sucursal_id: int
    sucursal: str
    sesion_id: int
    sesion_fecha: str
    monto_centavos: int


@dataclass(frozen=True)
class DeshacerResultado:
    tipo: str
    pago_id: int | None
    folio: str | None
    alumno_id: int
    alumno: str
    grupo_id: int
    grupo: str
    sucursal_id: int
    sucursal: str
    sesion_id: int
    sesion_fecha: str
    monto_centavos: int


@dataclass(frozen=True)
class _Contexto:
    sesion: Sesion
    grupo: Grupo
    sucursal: Sucursal
    alumno: Alumno


def _ahora_local() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _contexto(
    db: Session,
    sesion_id: int,
    alumno_id: int,
    *,
    accion: str,
) -> _Contexto:
    sesion = db.get(Sesion, sesion_id)
    if sesion is None:
        raise CashierError("La sesión no existe.")
    if sesion.estado == "cancelada":
        raise CashierError(f"No se puede {accion} una sesión cancelada.")

    grupo = db.get(Grupo, sesion.grupo_id)
    if grupo is None or grupo.activo != 1:
        raise CashierError("El grupo no está activo.")

    sucursal = db.get(Sucursal, grupo.sucursal_id)
    if sucursal is None or sucursal.activa != 1:
        raise CashierError("La sucursal no está activa.")

    alumno = db.get(Alumno, alumno_id)
    if alumno is None or alumno.estado != "activo":
        raise CashierError("El alumno no existe o no está activo.")

    inscrito = db.scalar(
        select(GrupoAlumno.id).where(
            GrupoAlumno.grupo_id == grupo.id,
            GrupoAlumno.alumno_id == alumno.id,
            GrupoAlumno.fecha_baja.is_(None),
        )
    )
    if inscrito is None:
        raise CashierError("El alumno no está inscrito en el grupo.")

    existente = db.scalar(
        select(Asistencia.id).where(
            Asistencia.sesion_id == sesion.id,
            Asistencia.alumno_id == alumno.id,
            Asistencia.es_reposicion == 0,
        )
    )
    if existente is not None:
        raise CashierError(
            "El alumno ya tiene asistencia registrada en esta sesión."
        )

    return _Contexto(
        sesion=sesion,
        grupo=grupo,
        sucursal=sucursal,
        alumno=alumno,
    )


def cobrar_sesion(
    db: Session,
    *,
    sesion_id: int,
    alumno_id: int,
    metodo: str,
) -> CobroResultado:
    if metodo not in METODOS:
        raise CashierError("Método de pago inválido.")
    if db.in_transaction():
        raise CashierError(
            "La sesión de base de datos ya tiene una transacción abierta."
        )

    try:
        db.execute(text("BEGIN IMMEDIATE"))

        contexto = _contexto(
            db,
            sesion_id,
            alumno_id,
            accion="cobrar",
        )
        sesion = contexto.sesion
        grupo = contexto.grupo
        sucursal = contexto.sucursal
        alumno = contexto.alumno
        monto = grupo.precio_centavos
        try:
            folio = siguiente_folio(db, sucursal.id)
        except FolioError as exc:
            raise CashierError(str(exc)) from exc

        fecha = _ahora_local()
        pago = Pago(
            folio=folio,
            alumno_id=alumno.id,
            sucursal_id=sucursal.id,
            tipo="sesion",
            monto_centavos=monto,
            metodo=metodo,
            fecha=fecha,
            estado="vigente",
        )
        db.add(pago)
        db.flush()

        db.add(
            Asistencia(
                sesion_id=sesion.id,
                alumno_id=alumno.id,
                estado="asistio",
                es_reposicion=0,
                pago_id=pago.id,
                precio_aplicado_centavos=monto,
            )
        )
        db.flush()

        resultado = CobroResultado(
            pago_id=pago.id,
            folio=folio,
            alumno_id=alumno.id,
            alumno=alumno.nombre,
            grupo_id=grupo.id,
            grupo=grupo.nombre,
            sucursal_id=sucursal.id,
            sucursal=sucursal.nombre,
            sesion_id=sesion.id,
            sesion_fecha=sesion.fecha,
            monto_centavos=monto,
            metodo=metodo,
            fecha=fecha,
        )

        db.commit()
        return resultado
    except CashierError:
        db.rollback()
        raise
    except IntegrityError as exc:
        db.rollback()
        raise CashierError(
            "No se pudo registrar el cobro. Intenta de nuevo."
        ) from exc
    except Exception:
        db.rollback()
        raise


def deshacer_asistencia(
    db: Session,
    *,
    sesion_id: int,
    alumno_id: int,
) -> DeshacerResultado:
    if db.in_transaction():
        raise CashierError(
            "La sesión de base de datos ya tiene una transacción abierta."
        )

    try:
        db.execute(text("BEGIN IMMEDIATE"))

        sesion = db.get(Sesion, sesion_id)
        if sesion is None:
            raise CashierError("La sesión no existe.")
        if sesion.estado == "cancelada":
            raise CashierError(
                "No se puede deshacer una asistencia en una sesión cancelada."
            )

        grupo = db.get(Grupo, sesion.grupo_id)
        if grupo is None:
            raise CashierError("El grupo no existe.")

        sucursal = db.get(Sucursal, grupo.sucursal_id)
        if sucursal is None:
            raise CashierError("La sucursal no existe.")

        alumno = db.get(Alumno, alumno_id)
        if alumno is None:
            raise CashierError("El alumno no existe.")

        asistencia = db.scalar(
            select(Asistencia).where(
                Asistencia.sesion_id == sesion.id,
                Asistencia.alumno_id == alumno.id,
                Asistencia.es_reposicion == 0,
            )
        )
        if asistencia is None:
            raise CashierError(
                "El alumno no tiene asistencia registrada en esta sesión."
            )
        if asistencia.estado != "asistio":
            raise CashierError("Solo se puede deshacer una asistencia.")

        pago = None
        if asistencia.pago_id is not None:
            pago = db.get(Pago, asistencia.pago_id)
            if pago is None:
                raise CashierError("El pago de la asistencia no existe.")
            if pago.estado == "cancelado":
                raise CashierError("La asistencia ya fue deshecha.")
            pago.estado = "cancelado"
            pago.cancelado_en = _ahora_local()
            pago.motivo_cancelacion = MOTIVO_DESHACER

        monto = asistencia.precio_aplicado_centavos
        if monto is None:
            monto = grupo.precio_centavos

        resultado = DeshacerResultado(
            tipo="pago" if pago is not None else "deuda",
            pago_id=pago.id if pago is not None else None,
            folio=pago.folio if pago is not None else None,
            alumno_id=alumno.id,
            alumno=alumno.nombre,
            grupo_id=grupo.id,
            grupo=grupo.nombre,
            sucursal_id=sucursal.id,
            sucursal=sucursal.nombre,
            sesion_id=sesion.id,
            sesion_fecha=sesion.fecha,
            monto_centavos=monto,
        )

        db.delete(asistencia)
        db.flush()
        db.commit()
        return resultado
    except CashierError:
        db.rollback()
        raise
    except IntegrityError as exc:
        db.rollback()
        raise CashierError(
            "No se pudo deshacer la asistencia. Intenta de nuevo."
        ) from exc
    except Exception:
        db.rollback()
        raise


def registrar_deuda(
    db: Session,
    *,
    sesion_id: int,
    alumno_id: int,
) -> DeudaResultado:
    if db.in_transaction():
        raise CashierError(
            "La sesión de base de datos ya tiene una transacción abierta."
        )

    try:
        db.execute(text("BEGIN IMMEDIATE"))

        contexto = _contexto(
            db,
            sesion_id,
            alumno_id,
            accion="registrar una deuda en",
        )
        sesion = contexto.sesion
        grupo = contexto.grupo
        sucursal = contexto.sucursal
        alumno = contexto.alumno
        monto = grupo.precio_centavos

        asistencia = Asistencia(
            sesion_id=sesion.id,
            alumno_id=alumno.id,
            estado="asistio",
            es_reposicion=0,
            pago_id=None,
            precio_aplicado_centavos=monto,
        )
        db.add(asistencia)
        db.flush()

        resultado = DeudaResultado(
            asistencia_id=asistencia.id,
            alumno_id=alumno.id,
            alumno=alumno.nombre,
            grupo_id=grupo.id,
            grupo=grupo.nombre,
            sucursal_id=sucursal.id,
            sucursal=sucursal.nombre,
            sesion_id=sesion.id,
            sesion_fecha=sesion.fecha,
            monto_centavos=monto,
        )

        db.commit()
        return resultado
    except CashierError:
        db.rollback()
        raise
    except IntegrityError as exc:
        db.rollback()
        raise CashierError(
            "No se pudo registrar la deuda. Intenta de nuevo."
        ) from exc
    except Exception:
        db.rollback()
        raise
