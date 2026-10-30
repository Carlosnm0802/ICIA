from pathlib import Path
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.config import APP_NAME
from app.core.database import get_db
from app.core.format import (
    formato_fecha,
    formato_fecha_corta,
    formato_fecha_hora,
    formato_fecha_larga,
    formato_mxn,
)
from app.services import cashier as cashier_service
from app.services import pos as pos_service
from app.services import thermal_printer

TEMPLATES_DIR = Path(__file__).resolve().parents[1] / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
templates.env.filters["mxn"] = formato_mxn
templates.env.filters["fecha"] = formato_fecha
templates.env.filters["fecha_hora"] = formato_fecha_hora
templates.env.filters["fecha_corta"] = formato_fecha_corta
templates.env.filters["fecha_larga"] = formato_fecha_larga
templates.env.globals["app_name"] = APP_NAME

router = APIRouter(prefix="/pos", tags=["pos"])


class CobroRequest(BaseModel):
    sesion_id: int = Field(gt=0)
    alumno_id: int = Field(gt=0)
    metodo: Literal["efectivo", "transferencia"] = "efectivo"


class DeudaRequest(BaseModel):
    sesion_id: int = Field(gt=0)
    alumno_id: int = Field(gt=0)


class DeshacerRequest(BaseModel):
    sesion_id: int = Field(gt=0)
    alumno_id: int = Field(gt=0)


@router.get("", response_class=HTMLResponse)
def mostrar_pos(
    request: Request,
    sucursal_id: Annotated[int | None, Query(ge=1)] = None,
    grupo_id: Annotated[int | None, Query(ge=1)] = None,
    sesion_id: Annotated[int | None, Query(ge=1)] = None,
    db: Session = Depends(get_db),
) -> HTMLResponse:
    sucursales = pos_service.listar_sucursales(db)
    sucursal = (
        pos_service.obtener_sucursal(db, sucursal_id)
        if sucursal_id is not None
        else None
    )
    grupos: list = []
    grupo = None
    sesiones: list = []
    sesion = None
    alumnos: list = []
    resumen = None

    if sucursal is not None:
        grupos = pos_service.listar_grupos(db, sucursal.id)
        if grupo_id is not None:
            grupo = pos_service.obtener_grupo(db, grupo_id, sucursal.id)
        if grupo is not None:
            sesiones = pos_service.listar_sesiones(db, grupo.id)
            if sesion_id is not None:
                sesion = pos_service.obtener_sesion(db, sesion_id, grupo.id)
            if sesion is None:
                sesion = pos_service.sesion_de_hoy(db, grupo.id)
            if sesion is not None:
                alumnos, resumen = pos_service.listar_roster(
                    db,
                    grupo.id,
                    sesion.id,
                )

    return templates.TemplateResponse(
        request=request,
        name="pos.html",
        context={
            "sucursales": sucursales,
            "sucursal": sucursal,
            "grupos": grupos,
            "grupo": grupo,
            "sesiones": sesiones,
            "sesion": sesion,
            "alumnos": alumnos,
            "resumen": resumen,
        },
    )


def _respuesta_ticket(
    request: Request,
    ticket: thermal_printer.TicketData,
    auto: bool,
) -> HTMLResponse:
    response = templates.TemplateResponse(
        request=request,
        name="ticket.html",
        context={"ticket": ticket, "auto": auto},
    )
    response.headers["Cache-Control"] = "no-store"
    return response


@router.get("/tickets/folio", response_class=HTMLResponse)
def mostrar_ticket_por_folio(
    request: Request,
    folio: Annotated[str, Query(min_length=1, max_length=32)],
    auto: Annotated[bool, Query()] = False,
    db: Session = Depends(get_db),
) -> HTMLResponse:
    ticket = thermal_printer.obtener_ticket_por_folio(db, folio)
    if ticket is None:
        raise HTTPException(status_code=404, detail="Ticket no encontrado.")
    return _respuesta_ticket(request, ticket, auto)


@router.get("/tickets/{pago_id}", response_class=HTMLResponse)
def mostrar_ticket(
    pago_id: int,
    request: Request,
    auto: Annotated[bool, Query()] = False,
    db: Session = Depends(get_db),
) -> HTMLResponse:
    ticket = thermal_printer.obtener_ticket(db, pago_id)
    if ticket is None:
        raise HTTPException(status_code=404, detail="Ticket no encontrado.")
    return _respuesta_ticket(request, ticket, auto)


@router.post("/sesiones")
def abrir_sesion_hoy(
    grupo_id: Annotated[int, Query(ge=1)],
    db: Session = Depends(get_db),
) -> RedirectResponse:
    grupo = pos_service.obtener_grupo_activo(db, grupo_id)
    if grupo is None:
        return RedirectResponse(url="/pos", status_code=303)

    sesion = pos_service.abrir_sesion_hoy(db, grupo)
    return RedirectResponse(
        url=(
            f"/pos?sucursal_id={grupo.sucursal_id}"
            f"&grupo_id={grupo.id}"
            f"&sesion_id={sesion.id}"
        ),
        status_code=303,
    )


@router.post("/cobrar")
def cobrar_sesion(
    payload: CobroRequest,
    db: Session = Depends(get_db),
) -> dict:
    try:
        resultado = cashier_service.cobrar_sesion(
            db,
            sesion_id=payload.sesion_id,
            alumno_id=payload.alumno_id,
            metodo=payload.metodo,
        )
    except cashier_service.CashierError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    alumnos, resumen = pos_service.listar_roster(
        db,
        resultado.grupo_id,
        resultado.sesion_id,
    )
    alumno = next(
        (item for item in alumnos if item.id == resultado.alumno_id),
        None,
    )

    return {
        "ok": True,
        "pago": {
            "id": resultado.pago_id,
            "folio": resultado.folio,
            "alumno_id": resultado.alumno_id,
            "alumno": resultado.alumno,
            "grupo_id": resultado.grupo_id,
            "grupo": resultado.grupo,
            "sucursal_id": resultado.sucursal_id,
            "sucursal": resultado.sucursal,
            "sesion_id": resultado.sesion_id,
            "sesion_fecha": resultado.sesion_fecha,
            "monto_centavos": resultado.monto_centavos,
            "monto": formato_mxn(resultado.monto_centavos),
            "metodo": resultado.metodo,
            "fecha": resultado.fecha,
        },
        "alumno": (
            {
                "id": alumno.id,
                "estado": alumno.estado,
                "etiqueta": alumno.etiqueta,
            }
            if alumno is not None
            else None
        ),
        "resumen": {
            "total": resumen.total,
            "pendientes": resumen.pendientes,
            "pagados": resumen.pagados,
            "deudas": resumen.deudas,
            "faltas": resumen.faltas,
        },
    }


@router.post("/asistio-sin-pagar")
def registrar_deuda(
    payload: DeudaRequest,
    db: Session = Depends(get_db),
) -> dict:
    try:
        resultado = cashier_service.registrar_deuda(
            db,
            sesion_id=payload.sesion_id,
            alumno_id=payload.alumno_id,
        )
    except cashier_service.CashierError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    alumnos, resumen = pos_service.listar_roster(
        db,
        resultado.grupo_id,
        resultado.sesion_id,
    )
    alumno = next(
        (item for item in alumnos if item.id == resultado.alumno_id),
        None,
    )

    return {
        "ok": True,
        "deuda": {
            "asistencia_id": resultado.asistencia_id,
            "alumno_id": resultado.alumno_id,
            "alumno": resultado.alumno,
            "grupo_id": resultado.grupo_id,
            "grupo": resultado.grupo,
            "sucursal_id": resultado.sucursal_id,
            "sucursal": resultado.sucursal,
            "sesion_id": resultado.sesion_id,
            "sesion_fecha": resultado.sesion_fecha,
            "monto_centavos": resultado.monto_centavos,
            "monto": formato_mxn(resultado.monto_centavos),
        },
        "alumno": (
            {
                "id": alumno.id,
                "estado": alumno.estado,
                "etiqueta": alumno.etiqueta,
            }
            if alumno is not None
            else None
        ),
        "resumen": {
            "total": resumen.total,
            "pendientes": resumen.pendientes,
            "pagados": resumen.pagados,
            "deudas": resumen.deudas,
            "faltas": resumen.faltas,
        },
    }


@router.post("/deshacer-asistencia")
def deshacer_asistencia(
    payload: DeshacerRequest,
    db: Session = Depends(get_db),
) -> dict:
    try:
        resultado = cashier_service.deshacer_asistencia(
            db,
            sesion_id=payload.sesion_id,
            alumno_id=payload.alumno_id,
        )
    except cashier_service.CashierError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    alumnos, resumen = pos_service.listar_roster(
        db,
        resultado.grupo_id,
        resultado.sesion_id,
    )
    alumno = next(
        (item for item in alumnos if item.id == resultado.alumno_id),
        None,
    )

    return {
        "ok": True,
        "deshecho": {
            "tipo": resultado.tipo,
            "pago_id": resultado.pago_id,
            "folio": resultado.folio,
            "alumno_id": resultado.alumno_id,
            "alumno": resultado.alumno,
            "grupo_id": resultado.grupo_id,
            "grupo": resultado.grupo,
            "sucursal_id": resultado.sucursal_id,
            "sucursal": resultado.sucursal,
            "sesion_id": resultado.sesion_id,
            "sesion_fecha": resultado.sesion_fecha,
            "monto_centavos": resultado.monto_centavos,
            "monto": formato_mxn(resultado.monto_centavos),
        },
        "alumno": (
            {
                "id": alumno.id,
                "estado": alumno.estado,
                "etiqueta": alumno.etiqueta,
            }
            if alumno is not None
            else None
        ),
        "resumen": {
            "total": resumen.total,
            "pendientes": resumen.pendientes,
            "pagados": resumen.pagados,
            "deudas": resumen.deudas,
            "faltas": resumen.faltas,
        },
    }
